"""
统一聊天 Agent：单次 LLM 调用完成决策、工具调用、回复生成
"""

import time
from typing import Optional, List, Dict, Any, Tuple
from src.common.logger import get_logger
from src.chat_v2.models import AgentContext, ExecutionResult, ExecutionStatus, ToolCall
from src.chat_v2.executor import ToolExecutor
from src.plugin_system.apis import llm_api
from src.config.config import model_config, global_config


class UnifiedChatAgent:
    """统一聊天 Agent"""

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

        # 缓存系统
        from src.chat_v2.utils.cache import cache_manager
        self.relationship_cache = cache_manager.get_cache("relationship", max_size=200, ttl=300.0)  # 5分钟
        self.memory_cache = cache_manager.get_cache("memory", max_size=100, ttl=600.0)  # 10分钟
        self.tool_cache = cache_manager.get_cache("tools", max_size=50, ttl=1800.0)  # 30分钟

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
            # 0. 消息预处理（集成旧架构功能）
            message = await self._preprocess_message(message)
            preprocess_time = time.time() - step_start_time

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
            else:
                # 不需要工具，直接使用第一次的回复
                context.final_response = context.initial_response
                context.timers["tool_execution"] = 0.0
                context.timers["llm_final_reply"] = 0.0

            # 5. 更新状态
            context.status = ExecutionStatus.COMPLETED
            context.total_time = time.time() - start_time

            # 6. 更新关系和心情值
            if global_config.bot.enable_relationship and context.final_response:
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

    async def _build_context(self, message) -> AgentContext:
        """构建 Agent 上下文"""
        # 获取聊天历史
        chat_history = await self.chat_stream.get_raw_msg_before_timestamp_with_chat(
            timestamp=time.time(),
            limit=20
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
        bot_config = {
            "name": global_config.bot.nickname,
            "personality": global_config.bot.plan_style,
            "reply_style": global_config.bot.reply_style,
        }

        # 获取用户关系和心情信息（使用缓存）
        relationship_info = None
        mood_info = None

        if global_config.bot.enable_relationship:
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

                # 构建聊天历史文本
                chat_history_text = ""
                for msg in chat_history[-10:]:
                    chat_history_text += f"{msg.sender}: {msg.content}\n"

                # 构建缓存键（基于最近消息内容）
                memory_cache_key = f"memory_{self.chat_stream.stream_id}_{hash(message.content)}"

                # 尝试从缓存获取
                memory_info = self.memory_cache.get(memory_cache_key)

                if memory_info is None:
                    # 调用记忆检索
                    memory_info = await build_memory_retrieval_prompt(
                        message=chat_history_text,
                        sender=message.sender,
                        target=message.content,
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

        return AgentContext(
            message=message,
            chat_history=chat_history,
            available_tools=available_tools,
            bot_config=bot_config,
            relationship_info=relationship_info,
            mood_info=mood_info,
            memory_info=memory_info
        )

    async def _llm_decision(self, context: AgentContext) -> AgentContext:
        """
        LLM 决策：判断是否需要工具、是否需要回复

        使用 Function Calling 模式，让 LLM 自己决定是否调用工具
        """
        context.status = ExecutionStatus.GENERATING

        # 构建系统提示词
        system_prompt = self._build_system_prompt(context)

        # 构建用户提示词
        user_prompt = self._build_user_prompt(context)

        # 调用 LLM（带工具定义）
        self.logger.info(f"第一次 LLM 调用，可用工具数: {len(context.available_tools)}")
        if context.available_tools:
            tool_names = [tool.get('name', 'unknown') for tool in context.available_tools]
            self.logger.info(f"可用工具列表: {tool_names}")

        success, response, reasoning, model_name, tool_calls = await llm_api.generate_with_model_with_tools(
            prompt=user_prompt,
            model_config=model_config.model_task_config.replyer,
            tool_options=context.available_tools if context.available_tools else None,
            request_type="unified_agent.decision",
            temperature=0.8
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
        context.tool_results = await self.tool_executor.execute_tools(
            context.tool_calls,
            timeout=30.0
        )
        context.tool_execution_time = time.time() - start_time

        self.logger.info(
            f"工具执行完成，耗时 {context.tool_execution_time:.2f}s，"
            f"成功 {sum(1 for r in context.tool_results if r.success)}/{len(context.tool_results)}"
        )

        return context

    async def _llm_final_reply(self, context: AgentContext) -> AgentContext:
        """基于工具结果生成最终回复"""
        context.status = ExecutionStatus.GENERATING

        # 格式化工具结果
        tool_context = self.tool_executor.format_tool_results(context.tool_results)

        # 构建提示词
        system_prompt = f"""你是 {context.bot_config['name']}。

{context.bot_config['reply_style']}

你刚调用了工具并获得以下信息：

{tool_context}

请基于这些信息自然回复用户，不要提及"搜索"、"查询"等过程性词汇。"""

        user_prompt = f"用户问：{context.message.content}"

        # 第二次 LLM 调用
        self.logger.debug("第二次 LLM 调用，基于工具结果生成回复")

        success, response, reasoning, model_name, _ = await llm_api.generate_with_model_with_tools(
            prompt=user_prompt,
            model_config=model_config.model_task_config.replyer,
            tool_options=None,  # 不再需要工具
            request_type="unified_agent.final_reply",
            temperature=0.8
        )

        context.llm_calls += 1

        if success:
            context.final_response = response
            self.logger.info(f"最终回复生成成功: {response[:50]}...")
        else:
            # 如果失败，使用第一次的回复
            context.final_response = context.initial_response
            self.logger.warning("最终回复生成失败，使用初始回复")

        return context

    def _build_system_prompt(self, context: AgentContext) -> str:
        """构建系统提示词"""
        from datetime import datetime

        # 判断是否是群聊
        is_group = context.message.message_info.group_info is not None if hasattr(context.message, 'message_info') else False
        scene_text = "QQ群聊" if is_group else "私聊对话"

        prompt = f"""**场景：{scene_text}**
当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        # 添加关系和心情信息
        if context.relationship_info:
            prompt += f"与用户关系：{context.relationship_info['level']}（{context.relationship_info['status']}）\n"

        if context.mood_info:
            prompt += f"当前心情：{context.mood_info['description']}\n"

        # 添加记忆信息
        if context.memory_info:
            prompt += f"\n相关记忆：\n{context.memory_info}\n"

        prompt += f"""
**你的身份：**
{context.bot_config['personality']}

**工具使用：**
- **重要：当遇到以下情况时，必须使用 web_search 工具搜索，不要猜测或编造答案：**
  1. 用户询问实时信息（天气、新闻、股票、比赛结果等）
  2. 用户询问最新资讯（新番、游戏更新、热点事件等）
  3. 用户询问具体事实（人物信息、地点、日期、数据等）
  4. 你不确定答案的准确性时
  5. 用户明确要求"搜索"、"查一下"、"帮我找"等
- 直接调用工具，不要说"我搜搜看"、"让我查一下"等过程性话语
- 使用搜索后，基于搜索结果回答，不要说"我搜索到了..."，直接自然地给出答案
- 如果���索失败或没有结果，诚实告知用户，不要编造信息
"""

        # 只在有工具时才添加工具列表
        if context.available_tools:
            prompt += "\n可用工具：\n"
            prompt += self._format_tools(context.available_tools)
            prompt += "\n"

        prompt += f"""
**回复要求：**
- 阅读聊天记录，理解上下文
- 给出自然、口语化的回复
- 保持平淡真实的语气{f"，{context.mood_info['description']}" if context.mood_info else ""}
- 回复要简短，不要过于冗长
- 可以有个性，不必过于有条理
- 根据你与对方的关系调整回复风格（恋人要更亲密温柔，亲密的朋友可以更随意，陌生人要更礼貌）
- {context.bot_config['reply_style']}

**输出规范：**
- 只输出回复内容本身
- 不要添加前后缀、冒号、引号、括号
- 不要添加"很遗憾"、"建议您"等客服式用语
- 不要列举1、2、3等条目，要自然地说话
- 直接说出你想说的话

现在，你说："""

        return prompt

    def _build_user_prompt(self, context: AgentContext) -> str:
        """构建用户提示词"""
        # 格式化聊天历史（只取最近5条相关对话）
        history_text = ""
        recent_messages = context.chat_history[-5:] if len(context.chat_history) > 5 else context.chat_history

        for msg in recent_messages:
            history_text += f"{msg.sender}: {msg.content}\n"

        # 当前消息
        history_text += f"{context.message.sender}: {context.message.content}"

        return history_text

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
            message_content = context.message.content

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

    async def _send_text_response(self, context: AgentContext):
        """
        发送文本回复消息

        Args:
            context: Agent 上下文
        """
        try:
            from src.plugin_system.apis import send_api
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

            # 发送所有处理后的回复
            for response_text in processed_responses:
                success = await send_api.text_to_stream(
                    text=response_text,
                    stream_id=self.chat_stream.stream_id,
                    set_reply=True if db_message else False,  # 只有找到数据库消息时才设置回复
                    reply_message=db_message,
                    storage_message=True  # 存储到数据库
                )

                if success:
                    self.logger.info(f"成功发送文本回复: {response_text[:50]}...")
                    context.metadata['text_sent'] = True
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
                    messages_text += f"{msg.sender}: {msg.content}\n"

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
            from src.common.database.database_model import Images, PersonInfo
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
            person_info = PersonInfo.get_or_none(
                (PersonInfo.user_id == user_id) & (PersonInfo.platform == platform)
            )

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

                    # 发送查询结果
                    from src.plugin_system.apis import send_api
                    await send_api.text_to_stream(
                        text=query_message,
                        stream_id=self.chat_stream.stream_id,
                        set_reply=True,
                        reply_message=message,
                        storage_message=True
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

