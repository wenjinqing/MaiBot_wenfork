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

    async def process(self, message) -> ExecutionResult:
        """
        处理消息并返回执行结果

        Args:
            message: 消息对象 (DatabaseMessages)

        Returns:
            ExecutionResult: 执行结果
        """
        start_time = time.time()

        try:
            # 1. 构建上下文
            context = await self._build_context(message)

            # 2. 第一次 LLM 调用：决策 + 可能的工具调用
            context = await self._llm_decision(context)

            # 3. 如果需要工具，执行工具
            if context.need_tools and context.tool_calls:
                context = await self._execute_tools(context)

                # 4. 第二次 LLM 调用：基于工具结果生成最终回复
                context = await self._llm_final_reply(context)
            else:
                # 不需要工具，直接使用第一次的回复
                context.final_response = context.initial_response

            # 5. 更新状态
            context.status = ExecutionStatus.COMPLETED
            context.total_time = time.time() - start_time

            # 6. 更新关系和心情值
            if global_config.bot.enable_relationship and context.final_response:
                await self._update_relationship_and_mood(context)

            # 7. 发送文本回复（新增）
            if context.final_response:
                await self._send_text_response(context)

            # 8. 表情包后处理
            if global_config.emoji.emoji_chance > 0 and context.final_response:
                await self._process_emoji(context)

            self.logger.info(
                f"消息处理完成，耗时 {context.total_time:.2f}s，"
                f"LLM调用 {context.llm_calls} 次，"
                f"工具调用 {len(context.tool_results)} 次"
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

        # 获取可用工具
        available_tools = self._get_available_tools()

        # 获取机器人配置
        bot_config = {
            "name": global_config.bot.nickname,
            "personality": global_config.bot.plan_style,
            "reply_style": global_config.bot.reply_style,
        }

        # 获取用户关系和心情信息
        relationship_info = None
        mood_info = None

        if global_config.bot.enable_relationship:
            try:
                from src.common.relationship_query import RelationshipQuery
                user_id = message.message_info.user_info.user_id
                platform = message.message_info.user_info.platform

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
            except Exception as e:
                self.logger.warning(f"获取关系信息失败: {e}")

        # 获取记忆检索信息（新增）
        memory_info = None

        if global_config.memory.enable_detailed_memory:
            try:
                from src.memory_system.memory_retrieval import build_memory_retrieval_prompt

                # 构建聊天历史文本
                chat_history_text = ""
                for msg in chat_history[-10:]:
                    chat_history_text += f"{msg.sender}: {msg.content}\n"

                # 调用记忆检索
                memory_info = await build_memory_retrieval_prompt(
                    message=chat_history_text,
                    sender=message.sender,
                    target=message.content,
                    chat_stream=self.chat_stream,
                    tool_executor=None  # 新架构不需要旧的 tool_executor
                )

                if memory_info:
                    self.logger.debug(f"记忆检索成功，长度: {len(memory_info)}")
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
                    arguments=tc.arguments,
                    call_id=tc.id
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
        prompt = f"""你是 {context.bot_config['name']}。

{context.bot_config['personality']}

{context.bot_config['reply_style']}
"""

        # 添加关系和心情信息
        if context.relationship_info:
            prompt += f"\n与用户关系：{context.relationship_info['level']}（{context.relationship_info['status']}）"

        if context.mood_info:
            prompt += f"\n当前心情：{context.mood_info['description']}"

        # 添加记忆信息
        if context.memory_info:
            prompt += f"\n\n相关记忆：\n{context.memory_info}"

        prompt += """

工具使用规则：
1. 当用户询问需要实时信息、搜索、查询的问题时（如"查一下"、"搜索"、"帮我找"），必须调用相应工具
2. 调用 web_search 工具的场景：用户明确要求搜索、查询实时信息、攻略、配队等
3. 直接调用工具，不要说"我搜搜看"等过程性话语
4. 基于工具结果自然回复，不要说"我搜索到了"
5. 如果不需要工具，可以直接回复
6. 无需回复时返回空字符串

"""
        # 只在有工具时才添加工具列表
        if context.available_tools:
            prompt += "可用工具：\n"
            prompt += self._format_tools(context.available_tools)

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

            if not context.final_response:
                self.logger.debug("没有文本回复，跳过发送")
                return

            # 发送文本消息
            success = await send_api.text_to_stream(
                text=context.final_response,
                stream_id=self.chat_stream.stream_id,
                set_reply=True,  # 设置为回复消息
                reply_message=context.message,
                storage_message=True  # 存储到数据库
            )

            if success:
                self.logger.info(f"成功发送文本回复: {context.final_response[:50]}...")
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
