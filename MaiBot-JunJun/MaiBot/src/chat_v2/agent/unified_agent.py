"""
统一聊天 Agent：单次 LLM 调用完成决策、工具调用、回复生成
"""

import asyncio
import os
import re
import time
from contextlib import asynccontextmanager
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Any, Tuple
from src.common.logger import get_logger
from src.chat_v2.models import AgentContext, ExecutionResult, ExecutionStatus, ToolCall
from src.chat_v2.executor import ToolExecutor
from src.plugin_system.apis import llm_api
from src.config.config import model_config, global_config
from src.chat.utils.chat_message_builder import (
    get_raw_msg_before_timestamp_with_chat,
    history_cutoff_for_inbound_message,
)
from src.chat_v2.legacy_persona_planner_prepare import prepare_legacy_persona_and_action_planning


class UnifiedChatAgent:
    """统一聊天 Agent"""

    _PROMPT_EMOJI_RE = re.compile(
        r"[\U0001F1E0-\U0001FAFF\U00002600-\U000027BF\U0001F300-\U0001F6FF"
        r"\U0001F900-\U0001F9FF\U00002700-\U000027BF\uFE0F\u200d\u20e3]+"
    )

    @classmethod
    def _strip_emoji_for_system_prompt(cls, text: Optional[str]) -> str:
        if not text:
            return ""
        t = cls._PROMPT_EMOJI_RE.sub("", str(text))
        return re.sub(r"[ \t]{2,}", " ", t).strip()

    def __init__(self, chat_stream):
        self.chat_stream = chat_stream
        self.tool_executor = ToolExecutor(chat_id=chat_stream.stream_id)
        self.logger = get_logger("unified_agent")

        # 频率控制
        from src.chat.frequency_control.frequency_control import frequency_control_manager
        self.frequency_control = frequency_control_manager.get_or_create_frequency_control(chat_stream.stream_id)

        # 连续不回复计数器
        self.consecutive_no_reply_count = 0

        # 沉默模式标志
        self.no_reply_until_call = False

        # 缓存系统（全局单例：所有群/私聊共用同一块 LRU，非「每个 Agent 一份」）
        # relationship：键为 user，大群活跃发言者多时宜放大；memory：键为 stream+内容哈希；tools：键为 stream_id
        from src.chat_v2.utils.cache import cache_manager
        self.relationship_cache = cache_manager.get_cache("relationship", max_size=2500, ttl=300.0)  # 5 分钟
        self.memory_cache = cache_manager.get_cache("memory", max_size=512, ttl=600.0)  # 10 分钟
        self.tool_cache = cache_manager.get_cache("tools", max_size=128, ttl=1800.0)  # 30 分钟

        # 旧 Planner 摘要注入 v2 提示（每轮 process 开头清空）
        self._legacy_planner_summary_text: Optional[str] = None
        # 与 chat.include_planner_reasoning 对齐的单段「规划想法」文案（未开摘要注入时使用）
        self._legacy_planner_reasoning_block: str = ""
        # prepare_legacy_persona_and_action_planning 产出的人设 metadata，在 _build_context 合并
        self._v2_pending_persona_meta: Dict[str, Any] = {}
        # 群聊 @ 判断：与心流一致用「距上次发出回复」窗口统计新消息数
        self._last_v2_reply_sent_at: float = 0.0

    async def process(self, message) -> ExecutionResult:
        """
        处理消息并返回执行结果

        Args:
            message: 消息对象 (DatabaseMessages)

        Returns:
            ExecutionResult: 执行结果
        """
        start_time = time.time()
        step_start_time = start_time

        try:
            self._legacy_planner_summary_text = None
            self._legacy_planner_reasoning_block = ""
            self._v2_pending_persona_meta = {}

            # 0. 消息预处理：若已由 HeartFCMessageReceiver 完成入站层，则跳过避免重复更新关系/心情
            if getattr(message, "_mai_preprocess_complete", False):
                preprocess_time = time.time() - step_start_time
            else:
                message = await self._preprocess_message(message)
                preprocess_time = time.time() - step_start_time

            # 0.25 可选：旧 observe / 反思侧后台任务（合并为单次 create_task，减轻高并发下任务风暴）
            _inner = global_config.inner
            if getattr(_inner, "v2_run_legacy_observe_side_tasks", False) or getattr(
                _inner, "v2_run_legacy_reflect_side_tasks", False
            ):

                async def _v2_background_observe_bundle() -> None:
                    coros = []
                    if getattr(_inner, "v2_run_legacy_observe_side_tasks", False):
                        from src.express.expression_learner import expression_learner_manager
                        from src.jargon import extract_and_store_jargon

                        sid = self.chat_stream.stream_id
                        _el = expression_learner_manager.get_expression_learner(sid)
                        coros.append(_el.trigger_learning_for_chat())
                        coros.append(extract_and_store_jargon(sid))

                    async def _reflect_once() -> None:
                        try:
                            from src.express.expression_reflector import expression_reflector_manager
                            from src.express.reflect_tracker import reflect_tracker_manager

                            sid = self.chat_stream.stream_id
                            reflector = expression_reflector_manager.get_or_create_reflector(sid)
                            await reflector.check_and_ask()
                            tracker = reflect_tracker_manager.get_tracker(sid)
                            if tracker:
                                resolved = await tracker.trigger_tracker()
                                if resolved:
                                    reflect_tracker_manager.remove_tracker(sid)
                        except Exception as e:
                            self.logger.debug(f"v2 legacy reflect 侧任务: {e}")

                    if getattr(_inner, "v2_run_legacy_reflect_side_tasks", False):
                        coros.append(_reflect_once())

                    if coros:
                        for r in await asyncio.gather(*coros, return_exceptions=True):
                            if isinstance(r, Exception):
                                self.logger.debug(f"v2 observe bundle: {r}")

                asyncio.create_task(_v2_background_observe_bundle())

            # 0.5. 回复意愿判断（频率控制）
            step_start_time = time.time()
            should_reply = await self._should_reply(message)
            should_reply_time = time.time() - step_start_time

            if not should_reply:
                self.consecutive_no_reply_count += 1
                self.logger.info(f"根据频率控制，本次不回复（连续不回复: {self.consecutive_no_reply_count}次）")

                # 触发频率调整
                await self.frequency_control.trigger_frequency_adjust()

                return ExecutionResult(
                    success=True,
                    response=None,
                    no_reply=True,
                    total_time=time.time() - start_time
                )

            # 重置连续不回复计数器
            self.consecutive_no_reply_count = 0

            # 0.7. 旧架构对齐：完整人设素材 + 可选 ActionPlanner/BrainPlanner（单入口）
            _align = await prepare_legacy_persona_and_action_planning(
                self.chat_stream, message, log=self.logger
            )
            self._v2_pending_persona_meta = _align.persona_meta
            self._legacy_planner_summary_text = _align.legacy_planner_summary_text

            _phase = _align.planner_phase
            if _phase is not None:
                if _phase.short_circuit_no_reply and _phase.set_no_reply_until_call:
                    self.no_reply_until_call = True
                    self.logger.info("旧 Planner 短路沉默且含 no_reply_until_call，已标记沉默至被@/提及")
                if _phase.short_circuit_no_reply:
                    self.consecutive_no_reply_count += 1
                    self.logger.info(
                        f"旧 Planner 判定沉默，跳过 v2 主 LLM（连续不回复: {self.consecutive_no_reply_count}次）"
                    )
                    await self.frequency_control.trigger_frequency_adjust()
                    return ExecutionResult(
                        success=True,
                        response=None,
                        no_reply=True,
                        total_time=time.time() - start_time,
                    )
                if (
                    getattr(global_config.inner, "v2_execute_legacy_planner_side_actions", False)
                    and _phase.custom_actions
                ):
                    await self._execute_legacy_planner_custom_actions(_phase.action_manager, _phase.custom_actions)
                if getattr(global_config.inner, "v2_execute_legacy_planner_wait_time", False):
                    _waits = [a for a in _phase.planned_actions if a.action_type == "wait_time"]
                    if _waits:
                        await self._execute_legacy_planner_custom_actions(_phase.action_manager, _waits)

            self._legacy_planner_reasoning_block = ""
            if _phase is not None and _phase.planned_actions:
                if getattr(global_config.chat, "include_planner_reasoning", False):
                    if not (self._legacy_planner_summary_text or "").strip():
                        self._legacy_planner_reasoning_block = self._format_legacy_planner_reasoning_line(
                            _phase.planned_actions
                        )

            # 1. 构建上下文
            step_start_time = time.time()
            context = await self._build_context_with_retry(message)
            context.timers["preprocess"] = preprocess_time
            context.timers["should_reply"] = should_reply_time
            context.timers["build_context"] = time.time() - step_start_time

            # 2. 第一次 LLM 调用：决策 + 可能的工具调用
            step_start_time = time.time()
            context = await self._llm_decision_with_retry(context)
            context.timers["llm_decision"] = time.time() - step_start_time

            # 3. 如果需要工具，执行工具
            if context.need_tools and context.tool_calls:
                step_start_time = time.time()
                context = await self._execute_tools_with_retry(context)
                context.timers["tool_execution"] = time.time() - step_start_time

                # 4. 第二次 LLM 调用：基于工具结果生成最终回复
                step_start_time = time.time()
                context = await self._llm_final_reply_with_retry(context)
                context.timers["llm_final_reply"] = time.time() - step_start_time
                self._maybe_clear_final_text_after_only_tts(context)
            else:
                # 不需要工具，直接使用第一次的回复
                context.final_response = context.initial_response
                context.timers["tool_execution"] = 0.0
                context.timers["llm_final_reply"] = 0.0

            # 5. 更新状态
            context.status = ExecutionStatus.COMPLETED
            context.total_time = time.time() - start_time

            # 5.5 复读强化：与近期本人发言高度雷同时追加一次改写 LLM（在关系更新与发送之前）
            if context.final_response:
                step_start_time = time.time()
                await self._rewrite_final_response_if_parroting(context)
                context.timers["v2_anti_repeat_rewrite"] = time.time() - step_start_time

            # 6. 更新关系和心情值
            if global_config.relationship and global_config.relationship.enable_relationship and context.final_response:
                step_start_time = time.time()
                await self._update_relationship_and_mood(context)
                context.timers["update_relationship"] = time.time() - step_start_time

            # 7. 发送文本回复（新增）
            if context.final_response:
                step_start_time = time.time()
                await self._send_text_response(context)
                context.timers["send_response"] = time.time() - step_start_time

            # 8. 表情包后处理
            if global_config.emoji.emoji_chance > 0 and context.final_response:
                step_start_time = time.time()
                await self._process_emoji(context)
                context.timers["process_emoji"] = time.time() - step_start_time

            # 生成性能报告
            timer_strings = []
            for name, elapsed in context.timers.items():
                timer_strings.append(f"{name}: {elapsed:.2f}s")

            self.logger.info(
                f"消息处理完成，总耗时 {context.total_time:.2f}s | "
                f"LLM调用 {context.llm_calls} 次 | "
                f"工具调用 {len(context.tool_results)} 次 | "
                f"详细: {', '.join(timer_strings)}"
            )

            return ExecutionResult(
                success=True,
                response=context.final_response,
                context=context,
                llm_calls=context.llm_calls,
                tool_calls=len(context.tool_results),
                total_time=context.total_time
            )

        except Exception as e:
            self.logger.error(f"消息处理失败: {e}", exc_info=True)

            # 错误分类和处理
            from src.chat_v2.utils.error_handler import ErrorHandler
            error_info = ErrorHandler.classify_error(e, context={"message_id": getattr(message, 'message_id', 'unknown')})
            ErrorHandler.handle_error(error_info)

            return ExecutionResult(
                success=False,
                error=str(e),
                total_time=time.time() - start_time
            )

    def _maybe_clear_final_text_after_only_tts(self, context: AgentContext) -> None:
        """语音已通过 unified_tts 发出时，去掉终局文字，避免与语音内容重复。"""
        if not getattr(global_config.inner, "v2_skip_text_when_only_unified_tts_success", True):
            return
        if not context.tool_results:
            return
        if any(not r.success for r in context.tool_results):
            return
        ok = [r for r in context.tool_results if r.success]
        if not ok or not all(r.tool_name == "unified_tts" for r in ok):
            return
        if not (context.final_response or "").strip():
            return
        self.logger.info(
            "v2：本轮仅 unified_tts 且均已成功，清空终局文字，不再跟发说明/表情包"
        )
        context.final_response = ""

    async def _build_context(self, message) -> AgentContext:
        """构建 Agent 上下文"""
        _hist_cut = history_cutoff_for_inbound_message(message)
        chat_history = get_raw_msg_before_timestamp_with_chat(
            chat_id=self.chat_stream.stream_id,
            timestamp=_hist_cut,
            limit=global_config.chat.max_context_size,
            filter_no_read_command=True,
        )

        # 获取可用工具（使用缓存）
        tools_cache_key = f"tools_{self.chat_stream.stream_id}"
        available_tools = self.tool_cache.get(tools_cache_key)
        if available_tools is None:
            available_tools = self._get_available_tools()
            self.tool_cache.set(tools_cache_key, available_tools)
            self.logger.debug(f"工具列表已缓存")
        else:
            self.logger.debug(f"使用缓存的工具列表")

        # 获取机器人配置
        _bot = global_config.bot
        bot_config = {
            "name": _bot.nickname if _bot else "",
            "personality": global_config.personality.personality if global_config.personality else "",
            "reply_style": global_config.personality.reply_style if global_config.personality else "",
            "qq_account": str(_bot.qq_account) if _bot and getattr(_bot, "qq_account", None) is not None else None,
        }

        # 获取用户关系和心情信息（使用缓存）
        relationship_info = None
        mood_info = None

        if global_config.relationship and global_config.relationship.enable_relationship:
            try:
                from src.common.relationship_query import RelationshipQuery
                user_id = message.message_info.user_info.user_id
                platform = message.message_info.user_info.platform

                # 尝试从缓存获取
                relationship_cache_key = f"relationship_{user_id}_{platform}"
                cached_data = self.relationship_cache.get(relationship_cache_key)

                if cached_data is not None:
                    relationship_info = cached_data.get("relationship_info")
                    mood_info = cached_data.get("mood_info")
                    self.logger.debug(f"使用缓存的关系信息")
                else:
                    # 从数据库查询
                    relationship_data = RelationshipQuery.query_relationship(user_id, platform)
                    if relationship_data:
                        relationship_info = {
                            "level": relationship_data.get("relationship_level", "陌生人"),
                            "value": relationship_data.get("relationship_value", 0),
                            "status": relationship_data.get("relationship_status", "👥 陌生人"),
                        }
                        mood_info = {
                            "value": relationship_data.get("mood_value", 50),
                            "description": relationship_data.get("mood_description", "😐 心情一般"),
                        }

                        # 缓存结果
                        self.relationship_cache.set(relationship_cache_key, {
                            "relationship_info": relationship_info,
                            "mood_info": mood_info
                        })
                        self.logger.debug(f"关系信息已缓存")
            except Exception as e:
                self.logger.warning(f"获取关系信息失败: {e}")

        # 获取记忆检索信息（使用缓存）
        memory_info = None

        if global_config.memory.enable_detailed_memory:
            try:
                from src.memory_system.memory_retrieval import build_memory_retrieval_prompt
                from src.chat.utils.chat_message_builder import build_readable_messages

                message_list_short = get_raw_msg_before_timestamp_with_chat(
                    chat_id=self.chat_stream.stream_id,
                    timestamp=_hist_cut,
                    limit=max(1, int(global_config.chat.max_context_size * 0.33)),
                    filter_no_read_command=True,
                )
                chat_history_text = build_readable_messages(
                    message_list_short,
                    replace_bot_name=True,
                    timestamp_mode="relative",
                    read_mark=0.0,
                    show_actions=True,
                )

                # 构建缓存键（基于最近消息内容）
                current_content = message.processed_plain_text or message.display_message or ""
                memory_cache_key = f"memory_{self.chat_stream.stream_id}_{hash(current_content)}"

                # 尝试从缓存获取
                memory_info = self.memory_cache.get(memory_cache_key)

                if memory_info is None:
                    # 调用记忆检索
                    current_sender = message.user_info.user_nickname if hasattr(message, 'user_info') else "未知"

                    memory_info = await build_memory_retrieval_prompt(
                        message=chat_history_text,
                        sender=current_sender,
                        target=current_content,
                        chat_stream=self.chat_stream,
                        tool_executor=None  # 新架构不需要旧的 tool_executor
                    )

                    if memory_info:
                        # 缓存结果
                        self.memory_cache.set(memory_cache_key, memory_info)
                        self.logger.debug(f"记忆检索成功并已缓存，长度: {len(memory_info)}")
                else:
                    self.logger.debug(f"使用缓存的记忆信息")
            except Exception as e:
                self.logger.warning(f"记忆检索失败: {e}")

        context = AgentContext(
            message=message,
            chat_history=chat_history,
            available_tools=available_tools,
            bot_config=bot_config,
            relationship_info=relationship_info,
            mood_info=mood_info,
            memory_info=memory_info,
        )
        if self._v2_pending_persona_meta:
            context.metadata.update(self._v2_pending_persona_meta)
        return context

    @staticmethod
    def _full_unified_prompt_logging_enabled() -> bool:
        if os.environ.get("MAI_LOG_FULL_V2_PROMPT", "").strip().lower() in ("1", "true", "yes", "on"):
            return True
        return bool(
            getattr(global_config.inner, "v2_log_full_unified_prompt", False)
            or getattr(global_config.debug, "show_prompt", False)
        )

    def _maybe_log_full_unified_prompt(self, phase: str, prompt_text: str) -> None:
        """由 inner.v2_log_full_unified_prompt、debug.show_prompt 或 MAI_LOG_FULL_V2_PROMPT=1 开启；正文按块多行 INFO 输出以免控制台截断。"""
        if not self._full_unified_prompt_logging_enabled():
            return
        sid = getattr(self.chat_stream, "stream_id", "") or ""
        body = prompt_text or ""
        # structlog 的 info 不会按 stdlib 规则展开 % 占位符，须用单条已格式化字符串
        self.logger.info(
            f"[unified_agent][完整提示词] 开始 phase={phase} stream_id={sid} 总长={len(body)}（正文分块输出）"
        )
        if not body:
            self.logger.info("[unified_agent][完整提示词][正文] （空）")
            return
        chunk_size = 3500
        n = (len(body) + chunk_size - 1) // chunk_size
        sep = "\n" + "─" * 76 + "\n"
        for i in range(n):
            chunk = body[i * chunk_size : (i + 1) * chunk_size]
            tag = f"[unified_agent][完整提示词][{phase}][{i + 1}/{n}]"
            self.logger.info(f"{tag}{sep}{chunk}")
        self.logger.info(f"[unified_agent][完整提示词] 结束 phase={phase}")

    async def _llm_decision(self, context: AgentContext) -> AgentContext:
        """
        LLM 决策：判断是否需要工具、是否需要回复

        使用 Function Calling 模式，让 LLM 自己决定是否调用工具
        """
        context.status = ExecutionStatus.GENERATING

        # 构建系统提示词（已包含聊天记录）；完整内容作为单条 user 文本发给 LLM（与 MessageBuilder 行为一致）
        system_prompt = self._build_system_prompt(context)
        self._maybe_log_full_unified_prompt("decision", system_prompt)

        # 调用 LLM（带工具定义）
        self.logger.info(f"第一次 LLM 调用，可用工具数: {len(context.available_tools)}")
        if context.available_tools:
            tool_names = [tool.get('name', 'unknown') for tool in context.available_tools]
            self.logger.info(f"可用工具列表: {tool_names}")

        # 有工具时必须用 tool_use 任务模型：replyer 常含 think 模型，易导致 function calling 异常或无法解析
        decision_task = (
            model_config.model_task_config.tool_use
            if context.available_tools
            else model_config.model_task_config.replyer
        )

        async with self._maybe_legacy_prompt_scope():
            success, response, reasoning, model_name, tool_calls = await llm_api.generate_with_model_with_tools(
                prompt=system_prompt,
                model_config=decision_task,
                tool_options=context.available_tools if context.available_tools else None,
                request_type="unified_agent.decision",
                temperature=decision_task.temperature,
            )

        context.llm_calls += 1

        if not success:
            self.logger.error(f"LLM 调用失败: {response}")
            context.initial_response = "抱歉，我现在有点累了，稍后再聊吧~"
            return context

        # 解析结果
        context.initial_response = response
        context.reasoning = reasoning

        # 检查是否有工具调用
        if tool_calls and len(tool_calls) > 0:
            context.need_tools = True
            context.tool_calls = [
                ToolCall(
                    tool_name=tc.func_name,
                    arguments=tc.args if tc.args else {},
                    call_id=tc.call_id
                )
                for tc in tool_calls
            ]
            self.logger.info(
                f"LLM 决定调用 {len(context.tool_calls)} 个工具: "
                f"{[tc.tool_name for tc in context.tool_calls]}"
            )
        else:
            context.need_tools = False
            self.logger.info("LLM 决定不需要工具，直接回复")

        return context

    async def _execute_tools(self, context: AgentContext) -> AgentContext:
        """执行工具"""
        context.status = ExecutionStatus.TOOL_EXECUTION

        start_time = time.time()
        tool_timeout = float(
            getattr(global_config.inner, "v2_tool_execution_timeout_seconds", 120.0) or 120.0
        )
        tool_timeout = max(30.0, tool_timeout)

        context.tool_results = await self.tool_executor.execute_tools(
            context.tool_calls,
            timeout=tool_timeout,
        )
        context.tool_execution_time = time.time() - start_time

        self.logger.info(
            f"工具执行完成，耗时 {context.tool_execution_time:.2f}s，"
            f"成功 {sum(1 for r in context.tool_results if r.success)}/{len(context.tool_results)}"
        )

        return context

    def _persona_reminder_for_tool_followup(self, context: AgentContext) -> str:
        """工具后二次回复沿用本轮已构建的人设要点（与决策轮一致）。"""
        if not getattr(global_config.inner, "v2_use_replyer_aligned_persona", True):
            return ""
        meta = context.metadata
        chunks: List[str] = []
        ident = (meta.get("v2_replyer_identity") or "").strip()
        if ident:
            chunks.append(ident)
        if global_config.personality:
            intr = (global_config.personality.interest or "").strip()
            if intr:
                chunks.append(f"你感兴趣的话题倾向：{intr}")
        kw = (meta.get("v2_keywords_reaction") or "").strip()
        if kw:
            chunks.append(f"关键词/语气触发提示：{kw}")
        if not chunks:
            return ""
        return "\n".join(chunks) + "\n\n"

    async def _llm_final_reply(self, context: AgentContext) -> AgentContext:
        """基于工具结果生成最终回复（与 MaiM-with-u / 旧 replyer 全量模板一致）。"""
        context.status = ExecutionStatus.GENERATING

        system_prompt = self._build_full_replyer_prompt(context, phase="final")
        user_prompt = (
            f"用户当前说的话：{context.message.processed_plain_text or context.message.display_message or ''}\n"
            "请只输出一条符合上文「输出规范」的纯文字回复，勿使用 Emoji、颜文字或符号表情。"
        )
        full_prompt = f"{system_prompt.rstrip()}\n\n{user_prompt}"
        self._maybe_log_full_unified_prompt("final_reply", full_prompt)

        self.logger.debug("第二次 LLM 调用，基于工具结果生成回复（全量 replyer 对齐提示）")

        _reply_task = model_config.model_task_config.replyer
        async with self._maybe_legacy_prompt_scope():
            success, response, reasoning, model_name, _ = await llm_api.generate_with_model_with_tools(
                prompt=full_prompt,
                model_config=_reply_task,
                tool_options=None,
                request_type="unified_agent.final_reply",
                temperature=_reply_task.temperature,
            )

        context.llm_calls += 1

        if success:
            context.final_response = response
            self.logger.info(f"最终回复生成成功: {response[:50]}...")
        else:
            context.final_response = context.initial_response
            self.logger.warning("最终回复生成失败，使用初始回复")

        return context

    def _build_reply_target_block(self, context: AgentContext) -> str:
        """与 private_generator / group_generator 的 reply_target_block 一致（含纯图/图文分支，文案用「对方」）。"""
        from src.chat.utils.chat_message_builder import replace_user_references
        from src.chat.replyer.replyer_manager import replyer_manager

        platform = self.chat_stream.platform
        raw = context.message.processed_plain_text or context.message.display_message or ""
        target = replace_user_references(raw, platform, replace_bot_name=True)

        replyer = replyer_manager.get_replyer(self.chat_stream, request_type="unified_agent.reply_target")
        if replyer is None:
            return f"现在对方说的：{target}。引起了你的注意"

        try:
            has_only_pics, has_text, pic_part, text_part = replyer._analyze_target_content(target)
            target_resolved = replyer._replace_picids_with_descriptions(target)
            if has_only_pics and not has_text:
                return f"现在对方发送的图片：{pic_part}。引起了你的注意"
            if has_text and pic_part:
                return f"现在对方发送了图片：{pic_part}，并说：{text_part}。引起了你的注意"
            if has_text:
                return f"现在对方说的：{text_part}。引起了你的注意"
            return f"现在对方说的:{target_resolved}。引起了你的注意"
        except Exception as e:
            self.logger.debug(f"reply_target 构建回退: {e}")
            return f"现在对方说的：{target}。引起了你的注意"

    def _planner_reasoning_mid_block(self, context: AgentContext) -> str:
        """对应 replyer 模板里 {planner_reasoning}，放在「当前任务」下，避免与文末重复注入。"""
        if not getattr(global_config.chat, "include_planner_reasoning", False):
            return ""
        legacy = (getattr(self, "_legacy_planner_reasoning_block", None) or "").strip()
        if legacy:
            return f"\n{legacy}\n"
        cr = (context.reasoning or "").strip()
        if cr:
            return f"\n你的想法是：{cr}\n"
        return ""

    def _format_executed_tool_results_old_style(self, context: AgentContext) -> str:
        """与旧 PrivateReplyer.build_tool_info 输出格式一致（replyer_prompt 的 tool_info_block）。"""
        if not context.tool_results:
            return ""
        lines = ["以下是你通过工具获取到的实时信息：\n"]
        for r in context.tool_results:
            if r.success:
                content = (r.content or "").strip()
                lines.append(f"- 【{r.tool_name}】function: {content}\n")
            else:
                err = (r.error or "失败").strip()
                lines.append(f"- 【{r.tool_name}】执行失败: {err}\n")
        lines.append("\n以上是你获取到的实时信息，请在回复时参考这些信息。\n\n")
        return "".join(lines)

    def _build_static_tool_usage_section(self, context: AgentContext) -> str:
        """旧模板「注意」之后的 **工具使用：** 正文。"""
        parts = [
            "用户要求\"查看/调用记录\"或\"你和XX聊了什么\"时，调用相应工具（如query_cross_scene_chat），"
            "不要说\"没有权限\"。\n"
        ]
        if context.available_tools:
            _tnames = {t.get("name") for t in context.available_tools if isinstance(t, dict)}
            if "unified_tts" in _tnames:
                parts.append(
                    "\n- 用户要求**发语音、朗读、念出来、TTS、voice、用语音说、调用语音工具**等时，"
                    "必须调用 **unified_tts** 工具完成真实语音发送；禁止仅用文字假装已发语音。\n"
                )
            parts.append(
                "\n- **重要：当遇到以下情况时，必须使用 web_search 工具搜索，不要猜测或编造答案：**\n"
                "  1. 用户询问实时信息（天气、新闻、股票、比赛结果等）\n"
                "  2. 用户询问最新资讯（新番、游戏更新、热点事件等）\n"
                "  3. 用户询问具体事实（人物信息、地点、日期、数据等）\n"
                "  4. 你不确定答案的准确性时\n"
                "  5. 用户明确要求\"搜索\"、\"查一下\"、\"帮我找\"等\n"
                "- 使用搜索后，基于搜索结果回答，不要说\"我搜索到了...\"，直接自然地给出答案\n"
                "- 如果搜索失败或没有结果，诚实告知用户，不要编造信息\n"
            )
        return "".join(parts)

    def _build_full_replyer_prompt(self, context: AgentContext, *, phase: str) -> str:
        """与 `replyer_prompt.py` 顺序对齐；收紧事实/工具约束；注入段去 Emoji（聊天记录与当前任务原文保留）。"""
        from datetime import datetime

        if phase not in ("decision", "final"):
            raise ValueError(f"unknown phase: {phase}")

        meta = context.metadata
        use_rp = getattr(global_config.inner, "v2_use_replyer_aligned_persona", True)

        is_group = context.message.message_info.group_info is not None if hasattr(context.message, "message_info") else False

        sender_name = "用户"
        if hasattr(context.message, "message_info") and hasattr(context.message.message_info, "user_info"):
            sender_name = context.message.message_info.user_info.user_nickname or "用户"

        _nm = context.bot_config["name"]
        bot_nm = self._strip_emoji_for_system_prompt(_nm) or _nm
        time_block = f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        relation_info_block = ""
        if context.relationship_info:
            lvl = self._strip_emoji_for_system_prompt(str(context.relationship_info.get("level", "")))
            st = self._strip_emoji_for_system_prompt(str(context.relationship_info.get("status", "")))
            relation_info_block = f"\n**你与 {sender_name} 的关系：**\n{lvl}（{st}）"

        mood_state = ""
        if context.mood_info:
            md = self._strip_emoji_for_system_prompt(str(context.mood_info.get("description", "")))
            if md:
                mood_state = f"，{md}"

        memory_retrieval = ""
        if context.memory_info:
            mem = self._strip_emoji_for_system_prompt(str(context.memory_info))
            memory_retrieval = f"\n**相关记忆：**\n{mem}\n"

        expr_h = (meta.get("v2_expression_habits") or "").strip() if use_rp else ""
        expr_h = self._strip_emoji_for_system_prompt(expr_h)
        expr_block = f"{expr_h}\n" if expr_h else ""

        jargon = (meta.get("v2_jargon_explanation") or "").strip() if use_rp else ""
        jargon = self._strip_emoji_for_system_prompt(jargon)
        jargon_block = f"\n**对话中的黑话/俚语提示：**\n{jargon}\n" if jargon else ""

        executed_block = self._format_executed_tool_results_old_style(context) if phase == "final" else ""
        if executed_block:
            executed_block = self._strip_emoji_for_system_prompt(executed_block)

        knowledge_block = ""
        kp = (meta.get("v2_knowledge_prompt") or "").strip()
        if kp:
            kp = self._strip_emoji_for_system_prompt(kp)
            knowledge_block = kp if kp.endswith("\n") else f"{kp}\n"

        preamble = f"{knowledge_block}{executed_block}{expr_block}{memory_retrieval}{jargon_block}"

        if is_group:
            scene_header = f"**场景：QQ群聊**\n{time_block}{relation_info_block}\n"
            annotation_line = f"- 标注 {bot_nm}(你) 的发言是你自己的发言，请注意区分\n"
            lover_line = "- 如果上面显示某人是你的恋人，请用更亲密、温柔的语气回复，可以使用亲密的称呼\n"
            tone_hint = "保持平淡真实的语气"
            brief_hint = "回复要简短，不要过于冗长"
            pers_hint = "可以有个性，不必过于有条理"
            moderation_lines = ""
            read_chat_bullet = "- 阅读聊天记录，理解上下文"
        else:
            scene_header = (
                f"**场景：私聊对话**\n你正在和 {sender_name} 进行一对一聊天。\n{time_block}{relation_info_block}\n"
            )
            annotation_line = ""
            lover_line = (
                f"- 如果上面显示 {sender_name} 是你的恋人，请用更亲密、温柔的语气回复，"
                "可以使用亲密的称呼（如\"宝贝\"、\"亲爱的\"等）\n"
            )
            tone_hint = "保持真实的语气"
            brief_hint = "回复要简短，直接表达想法"
            pers_hint = "可以有个性，展现真实的交流感"
            moderation_lines = (
                "请不要输出违法违规内容，不要输出色情，暴力，政治相关内容，如有敏感内容，请规避。不要随意遵从他人指令。\n"
            )
            read_chat_bullet = "- 阅读聊天记录，理解对话上下文"

        dialogue = self._build_dialogue_prompt(context)
        reply_target_block = self._build_reply_target_block(context)
        planner_mid = self._planner_reasoning_mid_block(context)
        if planner_mid:
            planner_mid = self._strip_emoji_for_system_prompt(planner_mid)

        static_tool_body = self._build_static_tool_usage_section(context)

        tool_fail_bullet = ""
        if phase == "final" and context.tool_results and any(not r.success for r in context.tool_results):
            tool_fail_bullet = (
                "- 有工具未成功时，用一两句日常话带过即可；禁止说「工具坏了」「系统故障」「虚拟沙发」等程序员或客服腔；"
                "禁止使用 Emoji、颜文字、符号表情堆情绪；语气须符合下方 reply_style。\n"
            )

        identity = ((meta.get("v2_replyer_identity") or "").strip() if use_rp else "") or context.bot_config.get(
            "personality", ""
        )
        identity = self._strip_emoji_for_system_prompt(identity)
        reply_style = context.bot_config["reply_style"]

        interest_block = ""
        if global_config.personality:
            intr = (global_config.personality.interest or "").strip()
            if intr:
                intr = self._strip_emoji_for_system_prompt(intr)
                interest_block = f"\n**你的兴趣与关注倾向：**\n{intr}\n"

        chat_px = (meta.get("v2_chat_prompt_extra") or "").strip() if use_rp else ""
        chat_px = self._strip_emoji_for_system_prompt(chat_px)
        chat_prompt_head = f"{chat_px}\n\n" if chat_px else ""

        kw = (meta.get("v2_keywords_reaction") or "").strip() if use_rp else ""
        kw = self._strip_emoji_for_system_prompt(kw)

        reply_bullets: List[str] = [
            read_chat_bullet,
            "**去复读（只约束你自己在「聊天记录」里已出现的发言，不约束用户）：**",
            "- 禁止：把上文中你自己说过的整句/整段几乎原样再说一遍；禁止只靠删改标点、换语气词、调换分句顺序冒充新内容。",
            "- 必须：用户意图与上次相近时，先换切入点再写——事实与结论可与上次一致，但**句式、用词、信息展开方式**须明显不同；可自然承认「上次说过」、补充新细节、给替代方案或换种语气，像真人续聊而非背台词。",
            "- 例外：仅当用户明确要求你「重复一遍」「引用你刚才说的」等时，才允许复述原话；无此要求则一律换新说法。",
            "- 示例（同意图、说法要换）：用户再次索要同类内容时，反面——把上次说明限制/拒答的长段几乎原样再说一遍；正面——先用半句承认「刚才说过类似意思」，再换一套比喻、补充一条新条件或换一个安抚/推进角度。",
            "- 严格依据上文「聊天记录」「当前任务」与（若有）工具结果作答，不得编造未出现的经历或事实，不得与已成功工具返回内容矛盾",
            "- 回答「在干嘛」「忙什么」等时，活动描述须与上文「你的身份」一致，勿套用人设里未出现的万能梗（例如身份未提贴吧/知乎则不要说在刷贴吧；猫娘/奇幻设定用同一世界观内的日常说法）",
            "- 给出自然、口语化的回复",
            f"- {tone_hint}{mood_state}",
            f"- {brief_hint}",
            f"- {pers_hint}",
            "- 根据你与对方的关系调整回复风格（恋人要更亲密温柔，亲密的朋友可以更随意，陌生人要更礼貌）",
        ]
        if phase == "final" and context.tool_results and any(r.success for r in context.tool_results):
            reply_bullets.append(
                "- 上文「以下是你通过工具获取到的实时信息」中成功项视为事实，须在回复中尊重，不得否认、假装未见或与摘要相反"
            )
        if kw:
            reply_bullets.append(f"- {kw}")
        reply_bullets.append(f"- {reply_style}")
        if tool_fail_bullet:
            reply_bullets.append(tool_fail_bullet.strip())
        reply_body = "\n".join(reply_bullets)

        notes = f"""注意：
{annotation_line}- 聊天记录中的时间标记（如"3小时前"、"2分钟前"）表示该消息距离当前时间的时长，请根据当前时间判断事件是否已经过去
- 只有标记为"刚刚"或最新的消息才是正在发生的事情，其他带时间标记的都是过去的事情
{lover_line}"""

        recent_own_anchor = self._build_recent_own_speech_anchor_block(context)

        prompt = f"""{preamble}{scene_header}
**聊天记录：**
{dialogue}

{recent_own_anchor}{notes}
**工具使用：**
{static_tool_body}
**当前任务：**
{reply_target_block}{planner_mid}
**你的身份：**
{identity}{interest_block}

**回复要求：**
{chat_prompt_head}{reply_body}

**输出规范：**
{moderation_lines}- 只输出对用户说的正文一句或一小段，不要章节标题、不要列表格式、不要先解释规则再正文
- 落笔前自检：若正文与上文你自己的发言高度雷同（换皮不换骨），须重写；不要输出本条自检过程
- 不要为了套用「贴吧/知乎/微博」等风格而编造与「你的身份」矛盾的具体行为（人设里没写就不要说在刷贴吧）
- 不要添加前后缀、冒号、引号、括号作装饰性包裹
- 正文中禁止使用 Emoji、颜文字、符号表情脸（如 QAQ、OvO、^_^、T_T 等）；不要输出「表情包：…」类标记或方括号表情描述
- 不要添加表情包、@符号或艾特式指人
- 不要提及「作为 AI」「大模型」「提示词」「系统提示」等打破人设的表述
- 不要描述「调用工具」「执行函数」等技术过程；像日常聊天一样自然带过
- 直接说出你想说的话
"""

        if phase == "decision":
            if context.available_tools:
                prompt += (
                    "\n**本回合硬性约束：**\n"
                    "- 凡涉及站外事实、实时资讯、跨聊天记录检索等，必须通过工具完成，禁止未调用工具却编造结果。\n"
                    "- 若仅凭上文即可完整作答且无需工具，则只输出你要对用户说的内容，不要输出 JSON、函数名或「正在调用」类说明。\n"
                )
            prompt += "\n现在，你说："

        return self._append_legacy_bridge_prompt_extras(
            prompt, is_group, planner_reasoning_already_in_body=True
        )

    def _build_system_prompt(self, context: AgentContext) -> str:
        """首轮决策提示（与旧 replyer 全量模板同构）。"""
        return self._build_full_replyer_prompt(context, phase="decision")

    @asynccontextmanager
    async def _maybe_legacy_prompt_scope(self):
        if not getattr(global_config.inner, "v2_use_legacy_prompt_message_scope", False):
            yield
            return
        from src.chat.utils.prompt_builder import global_prompt_manager

        tmpl = None
        try:
            ctx = getattr(self.chat_stream, "context", None)
            if ctx is not None:
                tmpl = ctx.get_template_name()
        except Exception:
            pass
        async with global_prompt_manager.async_message_scope(tmpl):
            yield

    def _append_legacy_plan_style_if_enabled(self, base: str, is_group: bool) -> str:
        if not getattr(global_config.inner, "v2_append_legacy_plan_style_to_system_prompt", False):
            return base
        pc = global_config.personality
        if not pc:
            return base
        plan_text = (pc.private_plan_style if not is_group else pc.plan_style) or ""
        if not plan_text.strip():
            return base
        return base + f"\n\n**规划与发言约束（与旧架构 planner 对齐）：**\n{plan_text}\n"

    def _append_legacy_planner_summary_if_enabled(self, base: str) -> str:
        if not getattr(global_config.inner, "v2_inject_legacy_planner_summary_into_prompt", False):
            return base
        extra = getattr(self, "_legacy_planner_summary_text", None) or ""
        if not extra.strip():
            return base
        return base + "\n\n" + extra

    def _append_legacy_planner_reasoning_if_enabled(self, base: str) -> str:
        if not getattr(global_config.chat, "include_planner_reasoning", False):
            return base
        block = (getattr(self, "_legacy_planner_reasoning_block", None) or "").strip()
        if not block:
            return base
        return base + "\n\n" + block + "\n"

    def _append_legacy_bridge_prompt_extras(
        self, base: str, is_group: bool, *, planner_reasoning_already_in_body: bool = False
    ) -> str:
        base = self._append_legacy_plan_style_if_enabled(base, is_group)
        if not planner_reasoning_already_in_body:
            base = self._append_legacy_planner_reasoning_if_enabled(base)
        base = self._append_legacy_planner_summary_if_enabled(base)
        return base

    @staticmethod
    def _format_legacy_planner_reasoning_line(planned_actions) -> str:
        """与旧 replyer 的 planner_reasoning 字段对齐：优先 reply 动作的 action_reasoning / reasoning。"""
        if not planned_actions:
            return ""
        for a in planned_actions:
            if a.action_type == "reply":
                r = (a.action_reasoning or a.reasoning or "").strip()
                if r:
                    return f"你的想法是：{r}"
        for a in planned_actions:
            r = (a.reasoning or "").strip()
            if r:
                return f"你的想法是：{r}"
        return ""

    @staticmethod
    def _v2_mention_target_from_message(db_message) -> Optional[Tuple[str, str]]:
        """从 DatabaseMessages 取 @ 目标，行为对齐 MentionHelper.get_mention_target。"""
        if db_message is None:
            return None
        try:
            ui = getattr(db_message, "user_info", None)
            if ui is None:
                return None
            uid = getattr(ui, "user_id", None) or getattr(db_message, "user_id", None)
            if not uid:
                return None
            nn = getattr(ui, "user_nickname", None) or str(uid)
            bot_id = str(getattr(global_config.bot, "qq_account", "") or "")
            if bot_id and str(uid) == bot_id:
                return None
            return (str(uid), str(nn))
        except Exception:
            return None

    async def _execute_legacy_planner_custom_actions(self, action_manager, custom_actions) -> None:
        """执行旧 Planner 返回的插件类 action（与 HeartF 非 reply 分支一致，使用 ActionManager.create_action）。"""
        import uuid

        from src.chat.message_receive.chat_stream import get_chat_manager

        if not custom_actions:
            return
        thinking_id = str(uuid.uuid4())
        cycle_timers: Dict[str, float] = {}
        stream_id = self.chat_stream.stream_id
        log_prefix = f"[{get_chat_manager().get_stream_name(stream_id) or stream_id}]"

        async def _run_one(action) -> None:
            try:
                inst = action_manager.create_action(
                    action_name=action.action_type,
                    action_data=action.action_data or {},
                    action_reasoning=action.action_reasoning or action.reasoning or "",
                    cycle_timers=cycle_timers,
                    thinking_id=thinking_id,
                    chat_stream=self.chat_stream,
                    log_prefix=log_prefix,
                    action_message=action.action_message,
                )
                if inst:
                    await inst.execute()
            except Exception as e:
                self.logger.error(f"legacy planner 插件 action {action.action_type} 失败: {e}", exc_info=True)

        for a in custom_actions:
            await _run_one(a)

    def _build_dialogue_prompt_simple(self, context: AgentContext) -> str:
        """与旧链路一致的简略行格式（回退用）；当前用户句仅在 **当前任务**。"""
        dialogue_lines: List[str] = []
        recent_messages = context.chat_history[-global_config.chat.max_context_size :]
        for msg in recent_messages:
            sender = msg.user_info.user_nickname if hasattr(msg, "user_info") else "未知"
            content = msg.processed_plain_text or msg.display_message or ""
            _bid = context.bot_config.get("qq_account")
            if _bid is not None and hasattr(msg, "user_info"):
                if str(msg.user_info.user_id) == str(_bid):
                    sender = f"{context.bot_config['name']}(你)"
            dialogue_lines.append(f"{sender}: {content}")
        return "\n".join(dialogue_lines)

    def _build_dialogue_prompt(self, context: AgentContext) -> str:
        """与 private_generator / group_generator：不含未入库当前条；群聊用 normal_no_YMD + truncate。"""
        try:
            from src.chat.utils.chat_message_builder import build_readable_messages

            is_group = (
                context.message.message_info.group_info is not None
                if hasattr(context.message, "message_info") and context.message.message_info
                else False
            )
            mlist = list(context.chat_history)
            return build_readable_messages(
                mlist,
                replace_bot_name=True,
                timestamp_mode="normal_no_YMD" if is_group else "relative",
                read_mark=0.0,
                show_actions=True,
                truncate=bool(is_group),
            )
        except Exception as e:
            self.logger.debug(f"v2 聊天记录改用简略格式: {e}")
            return self._build_dialogue_prompt_simple(context)

    @staticmethod
    def _normalize_plain_for_dedup(text: str) -> str:
        """与 uni_message_sender 一致：去标点空格后比较，用于复读检测。"""
        if not text:
            return ""
        return re.sub(r"[^\w\u4e00-\u9fff]", "", text).lower()

    def _collect_recent_bot_plain_texts(self, context: AgentContext) -> List[str]:
        """从新到旧收集聊天记录中机器人自己发过的正文（用于锚点注入与改写检测）。"""
        bid = context.bot_config.get("qq_account")
        if bid is None:
            return []
        bid_s = str(bid)
        _inner = global_config.inner
        max_items = int(getattr(_inner, "v2_anti_repeat_recent_own_max_items", 15))
        max_chars = int(getattr(_inner, "v2_anti_repeat_recent_own_max_chars_per_line", 500))
        out: List[str] = []
        for msg in reversed(context.chat_history or []):
            if len(out) >= max_items:
                break
            ui = getattr(msg, "user_info", None)
            if ui is None or str(getattr(ui, "user_id", "")) != bid_s:
                continue
            t = (
                getattr(msg, "processed_plain_text", None)
                or getattr(msg, "display_message", None)
                or ""
            ).strip()
            if not t:
                continue
            if len(t) > max_chars:
                t = t[: max_chars - 1] + "…"
            out.append(t)
        return out

    def _build_recent_own_speech_anchor_block(self, context: AgentContext) -> str:
        """注入「本人近期原文」锚点，强化与「聊天记录」区块的对照。"""
        if not getattr(global_config.inner, "v2_anti_repeat_inject_recent_own_speech", True):
            return ""
        lines = self._collect_recent_bot_plain_texts(context)
        if not lines:
            return ""
        numbered = "\n".join(f"{i}. {line}" for i, line in enumerate(lines, start=1))
        return (
            "**你近期在本对话中已发送过的原文（从新到旧编号；仅供对照，禁止对任一条整段复述或仅微调标点/语气词换皮）：**\n"
            f"{numbered}\n\n"
        )

    def _draft_parrots_own_recent(self, draft: str, own_lines: List[str]) -> bool:
        """草稿全文或分段是否与近期本人发言高度雷同。"""
        if not draft or not own_lines:
            return False
        th = float(getattr(global_config.inner, "v2_anti_repeat_similarity_threshold", 0.86))
        min_len = 10
        chunks: List[str] = []
        seen = set()
        for chunk in [draft.strip()] + [p.strip() for p in re.split(r"\n+", draft.strip()) if p.strip()]:
            if chunk not in seen:
                seen.add(chunk)
                chunks.append(chunk)
        for chunk in chunks:
            cn = self._normalize_plain_for_dedup(chunk)
            if len(cn) < min_len:
                continue
            for line in own_lines:
                ln = self._normalize_plain_for_dedup(line)
                if len(ln) < min_len:
                    continue
                if cn == ln:
                    return True
                if SequenceMatcher(None, cn, ln).ratio() >= th:
                    return True
                shorter, longer = (cn, ln) if len(cn) <= len(ln) else (ln, cn)
                if len(shorter) >= 15 and shorter in longer:
                    return True
        return False

    async def _rewrite_final_response_if_parroting(self, context: AgentContext) -> None:
        """若终稿与近期本人发言高度雷同，追加一次专用改写 LLM（不走路由、不调用工具）。"""
        if not getattr(global_config.inner, "v2_anti_repeat_llm_rewrite", True):
            return
        draft = (context.final_response or "").strip()
        if len(draft) < 8:
            return
        own_lines = self._collect_recent_bot_plain_texts(context)
        if not own_lines:
            return
        if not self._draft_parrots_own_recent(draft, own_lines):
            return

        listed = "\n".join(f"- {line}" for line in own_lines[:20])
        rewrite_prompt = (
            "你在同一会话里近期对用户说过的原文如下（从新到旧）：\n"
            f"{listed}\n\n"
            "下面是你本轮打算发送给用户的「草稿」：\n"
            f"{draft}\n\n"
            "任务：若草稿与上列任一条在含义与措辞上高度雷同（仅删改标点、语气词、调换分句顺序不算重写），"
            "请重写为一条全新的口语回复：事实与态度可与草稿一致，但句式、用词、切入角度必须明显不同；"
            "可自然承认「刚才说过类似的」。\n"
            "若草稿与上列均已明显不同，则原样输出草稿正文，不要加任何说明。\n"
            "只输出最终给用户看的一条正文，不要标题、不要列表、不要解释规则。"
        )

        models = llm_api.get_available_models()
        task = models.get("utils") or model_config.model_task_config.replyer

        async with self._maybe_legacy_prompt_scope():
            ok, new_text, _, model_name = await llm_api.generate_with_model(
                rewrite_prompt,
                model_config=task,
                request_type="unified_agent.anti_repeat_rewrite",
                temperature=min(0.8, getattr(task, "temperature", 0.7) or 0.7),
            )

        context.llm_calls += 1
        if ok and (new_text or "").strip():
            new_s = new_text.strip()
            if len(new_s) > 4000:
                new_s = new_s[:4000]
            context.final_response = new_s
            self.logger.info(
                f"复读改写已应用 model={model_name} 原稿约 {len(draft)} 字 -> 新规约 {len(new_s)} 字"
            )
        else:
            self.logger.warning("复读改写 LLM 失败或未返回正文，保留原终稿")

    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具定义"""
        try:
            from src.plugin_system.apis.tool_api import get_llm_available_tool_definitions
            all_tools = get_llm_available_tool_definitions()

            # 直接返回工具定义列表（不需要转换格式）
            # all_tools 格式: [(name, definition), ...]
            # definition 格式: {"name": "...", "description": "...", "parameters": [...]}
            tools = [definition for name, definition in all_tools]

            return tools
        except Exception as e:
            self.logger.error(f"获取工具定义失败: {e}", exc_info=True)
            return []

    def _format_tools(self, tools: List[Dict[str, Any]]) -> str:
        """格式化工具列表"""
        if not tools:
            return "无可用工具"

        result = ""
        for tool in tools:
            result += f"- {tool.get('name', 'unknown')}: {tool.get('description', '')}\n"
        return result

    async def _update_relationship_and_mood(self, context: AgentContext):
        """更新用户的关系和心情值"""
        try:
            from src.common.relationship_updater import RelationshipUpdater

            user_id = context.message.message_info.user_info.user_id
            platform = context.message.message_info.user_info.platform
            message_content = context.message.processed_plain_text or context.message.display_message or ""

            # 分析消息特征
            message_length = len(message_content)
            has_emoji = any(char in message_content for char in ['[', ']'])  # 简单判断
            has_image = hasattr(context.message, 'images') and context.message.images
            is_at_bot = f"@{global_config.bot.nickname}" in message_content
            is_reply_bot = True  # 因为机器人回复了，说明是在对话中

            # 更新关系值
            RelationshipUpdater.update_on_message(
                user_id=user_id,
                platform=platform,
                message_length=message_length,
                message_text=message_content,
                has_emoji=has_emoji,
                has_image=has_image,
                is_at_bot=is_at_bot,
                is_reply_bot=is_reply_bot
            )

            self.logger.debug(f"已更新用户 {user_id} 的关系和心情值")

        except Exception as e:
            self.logger.warning(f"更新关系和心情值失败: {e}")

    async def _should_use_reply_quote_llm(self, db_message, bot_reply_preview: str) -> bool:
        """由小模型判断本次回复是否适合带「引用回复」。"""
        try:
            from src.plugin_system.apis import llm_api as _llm_api

            user_text = (getattr(db_message, "processed_plain_text", None) or "")[:600]
            reply_prev = (bot_reply_preview or "")[:600]
            prompt = (
                "判断机器人在群聊/私聊中发送下一条回复时，是否应使用「引用回复」指向用户上一条触发消息。\n"
                "适合引用：明确在回答该用户的问题、直接接该用户的话、针对该用户纠错或补充。\n"
                "不适合引用：泛泛闲聊、接梗、随口一句、明显在对整群说话、回复很短且无明确指向。\n"
                "只输出 yes 或 no，不要其它内容。\n\n"
                f"【用户消息】\n{user_text}\n\n【机器人将发送】\n{reply_prev}\n"
            )
            models = _llm_api.get_available_models()
            small = models.get("utils_small") or models.get("utils")
            if not small:
                return False
            ok, out, _, _ = await _llm_api.generate_with_model(
                prompt, model_config=small, request_type="v2.reply_quote_decide"
            )
            if not ok or not out:
                return False
            t = out.strip().lower()
            return t.startswith("y") or t.startswith("yes") or t == "是"
        except Exception as e:
            self.logger.debug(f"引用回复 LLM 判断失败，默认不引用: {e}")
            return False

    async def _resolve_reply_quote(
        self, db_message, first_reply_text: str
    ) -> tuple[bool, Optional[Any]]:
        """
        根据 chat.reply_message_quote 决定是否引用。
        Returns:
            (set_reply, reply_message_for_send)  # 不引用时 reply 为 None
        """
        if not db_message:
            return False, None
        mode = getattr(global_config.chat, "reply_message_quote", "always")
        if mode == "never":
            return False, None
        if mode == "always":
            return True, db_message
        if mode == "llm":
            use = await self._should_use_reply_quote_llm(db_message, first_reply_text)
            return (use, db_message if use else None)
        return True, db_message

    async def _send_text_response(self, context: AgentContext):
        """
        发送文本回复消息

        Args:
            context: Agent 上下文
        """
        try:
            from src.plugin_system.apis import message_api, send_api
            from src.common.message_repository import find_messages

            if not context.final_response:
                self.logger.debug("没有文本回复，跳过发送")
                return

            # 使用旧架构的消息后处理逻辑
            from src.chat_v2.utils.response_processor import ResponseProcessor
            processor = ResponseProcessor()
            processed_responses = await processor.process(
                raw_response=context.final_response,
                message=context.message,
                bot_config=context.bot_config
            )

            # 获取数据库中的消息对象（用于回复引用）
            db_message = None
            if hasattr(context.message, 'message_info') and hasattr(context.message.message_info, 'message_id'):
                # context.message 是 MessageRecv 对象
                message_id = context.message.message_info.message_id
                # 使用 find_messages 查询数据库
                messages = find_messages(message_filter={"message_id": message_id}, limit=1)
                if messages:
                    db_message = messages[0]

            from src.chat.utils.mention_helper import MentionHelper

            is_group = self.chat_stream.group_info is not None
            recent_count = 0
            if is_group:
                start_t = (
                    self._last_v2_reply_sent_at
                    if getattr(self, "_last_v2_reply_sent_at", 0) > 0
                    else (time.time() - 300.0)
                )
                try:
                    recent_count = message_api.count_new_messages(
                        self.chat_stream.stream_id, start_t, time.time()
                    )
                except Exception as e:
                    self.logger.debug(f"v2 群聊新消息计数失败，回退 chat_history 长度: {e}")
                    recent_count = len(context.chat_history)

            should_mention = False
            if is_group and db_message:
                should_mention = MentionHelper.should_mention_user(
                    reply_message=db_message,
                    is_proactive=False,
                    is_group=True,
                    recent_message_count=recent_count,
                )

            first_out = processed_responses[0] if processed_responses else ""
            set_reply_flag, reply_for_send = await self._resolve_reply_quote(db_message, first_out)

            # 发送所有处理后的回复
            for seg_i, response_text in enumerate(processed_responses):
                text_out = response_text
                if seg_i == 0 and should_mention and db_message:
                    mt = self._v2_mention_target_from_message(db_message)
                    if mt:
                        uid, nn = mt
                        text_out = MentionHelper.add_mention_to_text(text_out, uid, nn)

                # 拆分多段时仅第一段带平台「引用回复」，避免每条气泡都挂在同一条消息上
                quote_this_seg = set_reply_flag and seg_i == 0
                success = await send_api.text_to_stream(
                    text=text_out,
                    stream_id=self.chat_stream.stream_id,
                    set_reply=quote_this_seg,
                    reply_message=reply_for_send if quote_this_seg else None,
                    storage_message=True  # 存储到数据库
                )

                if success:
                    self.logger.info(f"成功发送文本回复: {text_out[:50]}...")
                    context.metadata['text_sent'] = True
                    self._last_v2_reply_sent_at = time.time()
                else:
                    self.logger.warning("文本回复发送失败")

        except Exception as e:
            self.logger.error(f"发送文本回复失败: {e}", exc_info=True)

    async def _process_emoji(self, context: AgentContext):
        """
        表情包后处理：根据概率决定是否发送表情包

        这是一个后处理步骤，不影响主流程
        """
        try:
            import random
            from src.plugin_system.apis import emoji_api

            # 检查是否应该发送表情包（根据配置的概率）
            if random.random() > global_config.emoji.emoji_chance:
                return

            # 获取随机表情包
            sampled_emojis = await emoji_api.get_random(30)
            if not sampled_emojis:
                self.logger.debug("无法获取随机表情包")
                return

            # 准备情感数据
            emotion_map = {}
            for b64, desc, emo in sampled_emojis:
                if emo not in emotion_map:
                    emotion_map[emo] = []
                emotion_map[emo].append((b64, desc))

            available_emotions = list(emotion_map.keys())

            if not available_emotions:
                # 没有情感标签，随机选择
                emoji_base64, emoji_description, _ = random.choice(sampled_emojis)
            else:
                # 使用 LLM 选择合适的情感
                available_emotions_str = "\n".join(available_emotions)

                # 获取最近的消息
                recent_messages = context.chat_history[-5:] if context.chat_history else []
                messages_text = ""
                for msg in recent_messages:
                    sender = msg.user_info.user_nickname if hasattr(msg, 'user_info') else "未知"
                    content = msg.processed_plain_text or msg.display_message or ""
                    messages_text += f"{sender}: {content}\n"

                # 构建提示词
                prompt = f"""你正在进行聊天，需要选择一个合适的表情包情感标签。

聊天记录：
{messages_text}

你的回复：{context.final_response}

可用的情感标签：
{available_emotions_str}

请直接返回最匹配的那个情感标签，不要进行任何解释。"""

                # 调用 LLM 选择情感
                from src.plugin_system.apis import llm_api
                models = llm_api.get_available_models()
                utils_model = models.get("utils")

                if utils_model:
                    success, chosen_emotion, _, _ = await llm_api.generate_with_model(
                        prompt,
                        model_config=utils_model,
                        request_type="emoji.select_v2"
                    )

                    if success:
                        chosen_emotion = chosen_emotion.strip().replace('"', "").replace("'", "")

                        # 根据选择的情感匹配表情包
                        if chosen_emotion in emotion_map:
                            emoji_base64, emoji_description = random.choice(emotion_map[chosen_emotion])
                            self.logger.info(f"选择表情包情感: {chosen_emotion}")
                        else:
                            emoji_base64, emoji_description, _ = random.choice(sampled_emojis)
                    else:
                        emoji_base64, emoji_description, _ = random.choice(sampled_emojis)
                else:
                    emoji_base64, emoji_description, _ = random.choice(sampled_emojis)

            # 发送表情包
            from src.plugin_system.apis import send_api

            success = await send_api.emoji_to_stream(
                emoji_base64=emoji_base64,
                stream_id=self.chat_stream.stream_id,
                set_reply=False,
                reply_message=None,
                storage_message=True
            )

            if success:
                self.logger.info(f"成功发送表情包")
                # 将表情包信息添加到上下文元数据
                context.metadata['emoji_sent'] = True
            else:
                self.logger.debug("表情包发送失败")

        except Exception as e:
            self.logger.warning(f"表情包处理失败: {e}")

    async def _preprocess_message(self, message):
        """
        消息预处理（集成旧架构功能）

        1. 图片描述替换
        2. 用户引用格式替换
        3. 关系系统更新
        4. 丰富的日志输出
        """
        try:
            import re
            from src.common.database.database_model import Images
            from src.common.person_info_resolve import get_person_by_user_platform
            from src.chat.utils.chat_message_builder import replace_user_references
            from src.common.relationship_updater import RelationshipUpdater
            from src.common.mood_system import MoodSystem
            from src.common.relationship_query import RelationshipQuery

            # 初始化关系系统组件
            relationship_updater = RelationshipUpdater()
            mood_system = MoodSystem()

            # 1. 图片描述替换
            picid_pattern = r"\[picid:([^\]]+)\]"
            picid_list = re.findall(picid_pattern, message.processed_plain_text)

            processed_text = message.processed_plain_text
            if picid_list:
                for picid in picid_list:
                    image = Images.get_or_none(Images.image_id == picid)
                    if image and image.description:
                        processed_text = processed_text.replace(
                            f"[picid:{picid}]",
                            f"[图片：{image.description}]"
                        )
                    else:
                        processed_text = processed_text.replace(
                            f"[picid:{picid}]",
                            "[图片：网络不好，图片无法加载]"
                        )

            # 2. 用户引用格式替换
            processed_text = replace_user_references(
                processed_text,
                message.message_info.platform,
                replace_bot_name=True,
            )

            # 更新消息的处理文本
            message.processed_plain_text = processed_text

            # 3. 获取用户信息
            user_id = message.message_info.user_info.user_id
            platform = message.message_info.platform
            userinfo = message.message_info.user_info

            # 4. 关系系统更新
            # 检查并应用亲密度衰减
            relationship_updater.check_and_decay(user_id, platform)

            # 检测心情关键词并更新心情值
            mood_event = mood_system.detect_mood_keywords(processed_text)
            if mood_event:
                mood_change = mood_system.MOOD_RULES.get(mood_event, 0)
                mood_system.update_mood(
                    user_id=user_id,
                    platform=platform,
                    mood_change=mood_change,
                    reason=f"检测到{mood_event}关键词"
                )

            # 5. 丰富的日志输出（包含关系信息）
            person_info = get_person_by_user_platform(user_id, platform)

            chat_name = self.chat_stream.group_info.group_name if self.chat_stream.group_info else "私聊"

            if person_info:
                relationship_value = person_info.relationship_value
                relationship_level = relationship_updater.get_relationship_level(relationship_value)
                love_status = " 💕" if person_info.is_in_love else ""
                log_message = f"[{chat_name}]{userinfo.user_nickname}[{relationship_level}:{relationship_value}]{love_status}:{processed_text}"
            else:
                log_message = f"[{chat_name}]{userinfo.user_nickname}[新用户]:{processed_text}"

            self.logger.info(log_message)

            # 6. 检测关系查询请求
            if RelationshipQuery.check_query_keywords(processed_text):
                query_info = RelationshipQuery.query_relationship(user_id, platform)
                if query_info:
                    query_message = RelationshipQuery.format_relationship_info(query_info)

                    # 发送查询结果（never 模式不引用；llm 模式仍引用便于对照触发句）
                    from src.plugin_system.apis import send_api

                    _rq = getattr(global_config.chat, "reply_message_quote", "always")
                    _sr = _rq != "never"
                    await send_api.text_to_stream(
                        text=query_message,
                        stream_id=self.chat_stream.stream_id,
                        set_reply=_sr,
                        reply_message=message if _sr else None,
                        storage_message=True,
                    )

                    self.logger.info(f"已发送关系查询结果")

            return message

        except Exception as e:
            self.logger.warning(f"消息预处理失败: {e}", exc_info=True)
            return message

    async def _should_reply(self, message) -> bool:
        """
        判断是否应该回复消息（频率控制 + 意愿计算）

        Args:
            message: 消息对象

        Returns:
            bool: True 表示应该回复，False 表示不回复
        """
        try:
            import random

            # 1. 检查沉默模式
            if self.no_reply_until_call:
                # 如果被 @ 或提及，解除沉默模式
                if message.is_mentioned or message.is_at:
                    self.no_reply_until_call = False
                    self.logger.info("被 @ 或提及，解除沉默模式")
                else:
                    self.logger.debug("沉默模式中，不回复")
                    return False

            # 2. @ 或提及必定回复
            if (message.is_mentioned or message.is_at) and global_config.chat.mentioned_bot_reply:
                self.logger.info("被 @ 或提及，强制回复")
                return True

            # 3. 根据连续不回复次数动态调整阈值
            # 这里的阈值用于判断是否需要更积极地回复
            if self.consecutive_no_reply_count >= 5:
                # 连续 5 次不回复，提高回复概率
                reply_boost = 1.5
            elif self.consecutive_no_reply_count >= 3:
                # 连续 3 次不回复，适当提高回复概率
                reply_boost = 1.2
            else:
                reply_boost = 1.0

            # 4. 计算回复概率
            base_talk_value = global_config.chat.get_talk_value(self.chat_stream.stream_id)
            frequency_adjust = self.frequency_control.get_talk_frequency_adjust()
            final_probability = base_talk_value * frequency_adjust * reply_boost

            # 4b. 与入站层 is_mentioned_bot_in_message 一致：additional_config 等可带 reply_probability_boost
            boost = float(getattr(message, "reply_probability_boost", 0.0) or 0.0)
            if boost > 0:
                final_probability = min(1.0, final_probability * (1.0 + boost))

            # 5. 随机判断是否回复
            should_reply = random.random() < final_probability

            if should_reply:
                self.logger.debug(
                    f"回复意愿判断: 通过 "
                    f"(基础={base_talk_value:.2f}, "
                    f"频率调整={frequency_adjust:.2f}, "
                    f"连续不回复加成={reply_boost:.2f}, "
                    f"最终概率={final_probability:.2f})"
                )
            else:
                self.logger.debug(
                    f"回复意愿判断: 不通过 "
                    f"(基础={base_talk_value:.2f}, "
                    f"频率调整={frequency_adjust:.2f}, "
                    f"连续不回复加成={reply_boost:.2f}, "
                    f"最终概率={final_probability:.2f})"
                )

            return should_reply

        except Exception as e:
            self.logger.warning(f"回复意愿判断失败: {e}", exc_info=True)
            # 出错时默认回复
            return True

    async def _build_context_with_retry(self, message, max_retries: int = 3) -> AgentContext:
        """带重试的构建上下文"""
        from src.chat_v2.utils.error_handler import ErrorHandler

        for retry_count in range(max_retries):
            try:
                return await self._build_context(message)
            except Exception as e:
                error_info = ErrorHandler.classify_error(e, context={"step": "build_context", "retry": retry_count})

                if ErrorHandler.should_retry(error_info, retry_count, max_retries):
                    self.logger.warning(f"构建上下文失败，重试 {retry_count + 1}/{max_retries}: {e}")
                    await asyncio.sleep(1 * (retry_count + 1))  # 指数退避
                else:
                    ErrorHandler.handle_error(error_info)
                    raise

        raise Exception(f"构建上下文失败，已重试 {max_retries} 次")

    async def _llm_decision_with_retry(self, context: AgentContext, max_retries: int = 3) -> AgentContext:
        """带重试的 LLM 决策"""
        from src.chat_v2.utils.error_handler import ErrorHandler

        for retry_count in range(max_retries):
            try:
                return await self._llm_decision(context)
            except Exception as e:
                error_info = ErrorHandler.classify_error(e, context={"step": "llm_decision", "retry": retry_count})

                if ErrorHandler.should_retry(error_info, retry_count, max_retries):
                    self.logger.warning(f"LLM 决策失败，重试 {retry_count + 1}/{max_retries}: {e}")
                    await asyncio.sleep(2 * (retry_count + 1))  # 指数退避
                else:
                    ErrorHandler.handle_error(error_info)
                    raise

        raise Exception(f"LLM 决策失败，已重试 {max_retries} 次")

    async def _execute_tools_with_retry(self, context: AgentContext, max_retries: int = 2) -> AgentContext:
        """带重试的工具执行"""
        from src.chat_v2.utils.error_handler import ErrorHandler

        for retry_count in range(max_retries):
            try:
                return await self._execute_tools(context)
            except Exception as e:
                error_info = ErrorHandler.classify_error(e, context={"step": "execute_tools", "retry": retry_count})

                if ErrorHandler.should_retry(error_info, retry_count, max_retries):
                    self.logger.warning(f"工具执行失败，重试 {retry_count + 1}/{max_retries}: {e}")
                    await asyncio.sleep(1 * (retry_count + 1))
                else:
                    ErrorHandler.handle_error(error_info)
                    raise

        raise Exception(f"工具执行失败，已重试 {max_retries} 次")

    async def _llm_final_reply_with_retry(self, context: AgentContext, max_retries: int = 3) -> AgentContext:
        """带重试的 LLM 最终回复"""
        from src.chat_v2.utils.error_handler import ErrorHandler

        for retry_count in range(max_retries):
            try:
                return await self._llm_final_reply(context)
            except Exception as e:
                error_info = ErrorHandler.classify_error(e, context={"step": "llm_final_reply", "retry": retry_count})

                if ErrorHandler.should_retry(error_info, retry_count, max_retries):
                    self.logger.warning(f"LLM 最终回复失败，重试 {retry_count + 1}/{max_retries}: {e}")
                    await asyncio.sleep(2 * (retry_count + 1))
                else:
                    ErrorHandler.handle_error(error_info)
                    raise

        raise Exception(f"LLM 最终回复失败，已重试 {max_retries} 次")
