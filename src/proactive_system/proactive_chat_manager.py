"""
主动对话管理器 - 定期检查聊天流，主动发起话题或问候
"""
import asyncio
import os
import json
import toml
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.common.logger import get_logger
from src.manager.async_task_manager import AsyncTask
from src.chat.message_receive.chat_stream import get_chat_manager
from src.common.database.database_model import Messages, ChatHistory
from src.plugin_system.apis import send_api
from src.config.config import global_config
from src.person_info.person_info import Person
from src.llm_models.utils_model import LLMRequest
from src.config.config import model_config

logger = get_logger("主动对话管理器")


class ProactiveChatManager(AsyncTask):
    """主动对话管理器"""

    def __init__(self):
        # 从配置读取参数
        proactive_config = getattr(global_config, 'proactive_chat', None)
        if not proactive_config:
            # 如果没有配置，使用默认值
            self.enabled = False
            check_interval = 15
            self.min_idle_minutes = 45
            self.min_idle_minutes_night = 180
            self.max_daily_proactive = 8
            self.max_daily_proactive_night = 2
            self.night_start_hour = 0
            self.night_end_hour = 7
            self.silent_hours = "02:00-06:00"
            self.enable_in_groups = True
            self.enable_in_private = True
        else:
            self.enabled = getattr(proactive_config, 'enable', True)
            check_interval = getattr(proactive_config, 'check_interval_minutes', 15)
            self.min_idle_minutes = getattr(proactive_config, 'min_idle_minutes', 45)
            self.min_idle_minutes_night = getattr(proactive_config, 'min_idle_minutes_night', 180)
            self.max_daily_proactive = getattr(proactive_config, 'max_daily_proactive', 8)
            self.max_daily_proactive_night = getattr(proactive_config, 'max_daily_proactive_night', 2)
            self.night_start_hour = getattr(proactive_config, 'night_start_hour', 0)
            self.night_end_hour = getattr(proactive_config, 'night_end_hour', 7)
            self.silent_hours = getattr(proactive_config, 'silent_hours', "02:00-06:00")
            self.enable_in_groups = getattr(proactive_config, 'enable_in_groups', True)
            self.enable_in_private = getattr(proactive_config, 'enable_in_private', True)

        super().__init__(
            task_name="ProactiveChatManager",
            wait_before_start=60,  # 启动后等待1分钟
            run_interval=check_interval * 60,  # 转换为秒
        )

        # 记录今天已主动发起的次数（按stream_id）
        self.daily_proactive_count: Dict[str, int] = {}
        self.last_reset_date: Optional[str] = None

        # 记录每个 stream 最近发过的话题（用于去重），持久化到文件
        self.recent_proactive_topics: Dict[str, List[str]] = {}
        self.max_topic_history = 10  # 每个 stream 保留最近10条话题记录
        self._topics_file = os.path.join(os.path.dirname(__file__), "proactive_topics.json")
        self._load_topic_history()

        # 初始化LLM请求器（生成话题内容）
        self.llm_request = LLMRequest(
            model_set=model_config.model_task_config.utils_small,
            request_type="proactive_chat.topic"
        )

        # 初始化LLM判断器（判断是否应该发送）
        self.llm_judge = LLMRequest(
            model_set=model_config.model_task_config.utils_small,
            request_type="proactive_chat.judge"
        )

        # 加载 Napcat-Adapter 配置
        self.napcat_config = self._load_napcat_config()

    def _load_napcat_config(self) -> Optional[dict]:
        """加载 Napcat-Adapter 的配置文件"""
        try:
            # 尝试多个可能的路径
            possible_paths = [
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "MaiBot-Napcat-Adapter", "config.toml"),
                os.path.join(os.path.dirname(__file__), "..", "..", "MaiBot-Napcat-Adapter", "config.toml"),
                "E:/MaiM/MaiM-with-u/MaiBot-Napcat-Adapter/config.toml",
            ]

            for path in possible_paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    with open(abs_path, 'r', encoding='utf-8-sig') as f:
                        config = toml.load(f)
                        logger.info(f"成功加载 Napcat-Adapter 配置: {abs_path}")
                        return config

            logger.warning("未找到 Napcat-Adapter 配置文件，主动对话将对所有用户启用")
            return None
        except Exception as e:
            logger.error(f"加载 Napcat-Adapter 配置失败: {e}")
            return None

    def _is_in_napcat_whitelist(self, user_id: Optional[str], group_id: Optional[str]) -> bool:
        """检查用户/群组是否在 Napcat-Adapter 的白名单中"""
        if not self.napcat_config:
            # 如果没有配置文件，默认允许所有用户
            return True

        try:
            chat_config = self.napcat_config.get('chat', {})

            # 检查全局禁止名单
            ban_user_id = chat_config.get('ban_user_id', [])
            if user_id and int(user_id) in ban_user_id:
                return False

            # 如果是群聊
            if group_id:
                group_list_type = chat_config.get('group_list_type', 'whitelist')
                group_list = chat_config.get('group_list', [])

                if group_list_type == 'whitelist':
                    # 白名单模式：只有在列表中的群组才允许
                    return int(group_id) in group_list
                else:
                    # 黑名单模式：不在列表中的群组才允许
                    return int(group_id) not in group_list

            # 如果是私聊
            else:
                private_list_type = chat_config.get('private_list_type', 'whitelist')
                private_list = chat_config.get('private_list', [])

                if private_list_type == 'whitelist':
                    # 白名单模式：只有在列表中的用户才允许
                    return user_id and int(user_id) in private_list
                else:
                    # 黑名单模式：不在列表中的用户才允许
                    return user_id and int(user_id) not in private_list

        except Exception as e:
            logger.error(f"检查 Napcat 白名单失败: {e}")
            return False

    async def run(self):
        """定期检查聊天流，决定是否主动发起对话"""
        try:
            # 检查是否启用
            if not self.enabled:
                return

            # 检查是否在静默时间段
            if self._is_in_silent_hours():
                logger.debug("当前在静默时间段，跳过主动对话检查")
                return

            # 重置每日计数器
            self._reset_daily_count_if_needed()

            # 获取所有活跃的聊天流
            chat_manager = get_chat_manager()
            await chat_manager.load_all_streams()
            all_streams = list(chat_manager.streams.values())

            logger.debug(f"开始检查 {len(all_streams)} 个聊天流")

            for stream in all_streams:
                try:
                    # 检查是否应该主动发起对话
                    if await self._should_initiate_chat(stream):
                        await self._initiate_proactive_chat(stream)
                except Exception as e:
                    logger.error(f"检查聊天流 {stream.stream_id} 时出错: {e}")
                    continue

        except Exception as e:
            logger.error(f"主动对话检查失败: {e}")
            import traceback
            traceback.print_exc()

    def _is_in_silent_hours(self) -> bool:
        """检查当前是否在静默时间段"""
        try:
            if not self.silent_hours:
                return False

            now = datetime.now()
            current_time = now.strftime("%H:%M")

            # 解析静默时间段（如 "23:00-07:00"）
            start_str, end_str = self.silent_hours.split("-")
            start_hour, start_min = map(int, start_str.split(":"))
            end_hour, end_min = map(int, end_str.split(":"))

            current_minutes = now.hour * 60 + now.minute
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min

            # 处理跨天的情况（如 23:00-07:00）
            if start_minutes > end_minutes:
                return current_minutes >= start_minutes or current_minutes < end_minutes
            else:
                return start_minutes <= current_minutes < end_minutes

        except Exception as e:
            logger.error(f"解析静默时间段失败: {e}")
            return False

    def _reset_daily_count_if_needed(self):
        """如果日期变化，重置每日计数器"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.last_reset_date != today:
            self.daily_proactive_count.clear()
            self.last_reset_date = today
            logger.debug(f"已重置每日主动对话计数器（日期：{today}）")

    def _is_night_time(self) -> bool:
        """检查当前是否是深夜时段"""
        now = datetime.now()
        current_hour = now.hour

        # 处理跨天的情况（如 0点-7点）
        if self.night_start_hour > self.night_end_hour:
            # 跨天：如 23点-7点
            return current_hour >= self.night_start_hour or current_hour < self.night_end_hour
        else:
            # 不跨天：如 0点-7点
            return self.night_start_hour <= current_hour < self.night_end_hour

    def _get_current_limits(self) -> tuple[int, int]:
        """获取当前时段的限制参数

        Returns:
            (min_idle_minutes, max_daily_proactive)
        """
        if self._is_night_time():
            return self.min_idle_minutes_night, self.max_daily_proactive_night
        else:
            return self.min_idle_minutes, self.max_daily_proactive

    async def _should_initiate_chat(self, stream) -> bool:
        """判断是否应该主动发起对话"""
        try:
            stream_id = stream.stream_id

            # 过滤 WebUI 用户（user_id 以 "webui_" 开头）
            if stream.user_info and stream.user_info.user_id.startswith("webui_"):
                logger.debug(f"[{stream_id}] 跳过：WebUI 用户")
                return False

            # 检查是否在 Napcat-Adapter 的白名单中
            user_id = stream.user_info.user_id if stream.user_info else None
            group_id = stream.group_info.group_id if stream.group_info else None

            if not self._is_in_napcat_whitelist(user_id, group_id):
                logger.debug(f"[{stream_id}] 跳过：不在 Napcat 白名单（user={user_id}, group={group_id}）")
                return False

            # 检查是否启用了对应类型的主动对话
            is_group = stream.group_info is not None
            if is_group and not self.enable_in_groups:
                logger.debug(f"[{stream_id}] 跳过：群聊主动对话未启用")
                return False
            if not is_group and not self.enable_in_private:
                logger.debug(f"[{stream_id}] 跳过：私聊主动对话未启用")
                return False

            # 获取当前时段的限制参数
            min_idle, max_daily = self._get_current_limits()

            # 检查今天是否已达到最大主动次数
            today_count = self.daily_proactive_count.get(stream_id, 0)
            if today_count >= max_daily:
                logger.debug(f"[{stream_id}] 跳过：今日已达上限（{today_count}/{max_daily}）")
                return False

            # 检查最后活跃时间 - 使用数据库中最后一条消息的时间
            recent_messages = (
                Messages.select()
                .where(Messages.chat_id == stream_id)
                .order_by(Messages.time.desc())
                .limit(5)
            )

            if not recent_messages:
                logger.debug(f"[{stream_id}] 跳过：无消息记录")
                return False

            # 使用最后一条消息的时间计算空闲时间
            last_message = list(recent_messages)[0]
            last_message_time = last_message.time
            now = datetime.now().timestamp()
            idle_minutes = (now - last_message_time) / 60

            # 如果空闲时间不足，不主动发起
            if idle_minutes < min_idle:
                logger.debug(f"[{stream_id}] 跳过：空闲时间不足（{idle_minutes:.1f}/{min_idle} 分钟）")
                return False

            # 检查最后一条消息是否是机器人发的
            bot_qq = global_config.bot.qq_account
            recent_list = list(recent_messages)

            # 检查连续未回复：如果最近 N 条消息都是机器人发的，停止主动发言
            consecutive_bot_messages = 0
            for msg in recent_list:
                if msg.user_id == bot_qq:
                    consecutive_bot_messages += 1
                else:
                    break  # 遇到用户消息就停止计数

            if consecutive_bot_messages >= 3:
                logger.info(f"[{stream_id}] 跳过：用户已连续 {consecutive_bot_messages} 条未回复，暂停主动发言")
                return False

            if last_message.user_id == bot_qq:
                # 如果最后一条是机器人发的，需要更长的空闲时间才能再次主动发起
                # 避免机器人自说自话
                min_idle_after_bot = min_idle * 3  # 需要 3 倍的空闲时间
                if idle_minutes < min_idle_after_bot:
                    logger.debug(f"[{stream_id}] 跳过：最后一条是机器人消息，需要更长空闲时间（{idle_minutes:.1f}/{min_idle_after_bot:.1f} 分钟）")
                    return False
                else:
                    logger.debug(f"[{stream_id}] 最后一条是机器人消息，但已空闲足够久（{idle_minutes:.1f} 分钟），可以主动发起")

            time_desc = "深夜" if self._is_night_time() else "白天"
            logger.info(f"[{stream_id}] ✅ 符合主动对话条件（{time_desc}，空闲 {idle_minutes:.1f} 分钟，今日第 {today_count+1} 次）")
            return True

        except Exception as e:
            logger.error(f"判断是否主动发起对话时出错: {e}", exc_info=True)
            return False

    async def _select_group_member_by_intimacy(self, stream_id: str, platform: str) -> Optional[tuple]:
        """根据好感度选择群成员

        Returns:
            (user_id, nickname, relationship_value) 或 None
        """
        try:
            # 从数据库获取该群所有成员的好感度信息
            from src.common.database.database_model import PersonInfo, Messages

            # 获取最近在该群发言的用户（排除机器人自己）
            bot_qq = global_config.bot.qq_account
            recent_users = (
                Messages.select(Messages.user_id)
                .where(
                    (Messages.chat_id == stream_id) &
                    (Messages.user_id != bot_qq)
                )
                .order_by(Messages.time.desc())
                .limit(50)
                .distinct()
            )

            user_ids = [msg.user_id for msg in recent_users]
            if not user_ids:
                return None

            # 获取这些用户的好感度信息
            users_with_intimacy = (
                PersonInfo.select()
                .where(
                    (PersonInfo.platform == platform) &
                    (PersonInfo.user_id.in_(user_ids))
                )
                .order_by(PersonInfo.relationship_value.desc())
            )

            if not users_with_intimacy:
                return None

            # 根据好感度加权随机选择
            # 好感度越高，被选中的概率越大
            import random
            candidates = []
            weights = []

            for user in users_with_intimacy:
                # 权重 = 好感度 + 10（避免0权重）
                weight = user.relationship_value + 10
                candidates.append((user.user_id, user.nickname or user.user_id, user.relationship_value))
                weights.append(weight)

            if not candidates:
                return None

            # 加权随机选择
            selected = random.choices(candidates, weights=weights, k=1)[0]
            logger.info(f"根据好感度选择群成员: {selected[1]} (好感度: {selected[2]:.1f})")
            return selected

        except Exception as e:
            logger.error(f"选择群成员失败: {e}", exc_info=True)
            return None

    def _load_topic_history(self):
        """从文件加载话题历史"""
        try:
            if os.path.exists(self._topics_file):
                with open(self._topics_file, 'r', encoding='utf-8') as f:
                    self.recent_proactive_topics = json.load(f)
                logger.info(f"加载主动对话话题历史，共 {len(self.recent_proactive_topics)} 个会话")
        except Exception as e:
            logger.error(f"加载话题历史失败: {e}")
            self.recent_proactive_topics = {}

    def _save_topic_history(self):
        """保存话题历史到文件"""
        try:
            with open(self._topics_file, 'w', encoding='utf-8') as f:
                json.dump(self.recent_proactive_topics, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存话题历史失败: {e}")

    def _is_topic_duplicate(self, stream_id: str, new_message: str) -> bool:
        """快速检查：只过滤完全相同的消息"""
        history = self.recent_proactive_topics.get(stream_id, [])
        if not history:
            return False
        # 只做完全相同的检查，语义去重交给 LLM 判断器
        return new_message.strip() in history

    def _record_proactive_topic(self, stream_id: str, message: str):
        """记录已发送的主动对话话题"""
        if stream_id not in self.recent_proactive_topics:
            self.recent_proactive_topics[stream_id] = []
        self.recent_proactive_topics[stream_id].append(message)
        if len(self.recent_proactive_topics[stream_id]) > self.max_topic_history:
            self.recent_proactive_topics[stream_id].pop(0)
        self._save_topic_history()

    async def _judge_should_send(self, stream_id: str, message: str, person_name: str,
                                  recent_history: str, idle_minutes: float, is_group: bool) -> bool:
        """使用 LLM 判断是否应该发送这条主动消息"""
        try:
            now = datetime.now()
            time_str = now.strftime("%H:%M")
            chat_type = "群聊" if is_group else "私聊"

            # 获取最近发过的话题
            recent_topics = self.recent_proactive_topics.get(stream_id, [])
            recent_topics_str = "\n".join([f"- {t}" for t in recent_topics[-5:]]) if recent_topics else "（暂无记录）"

            prompt = f"""你是一个严格的判断助手，决定是否应该主动向用户发送一条消息。

【当前时间】{time_str}
【聊天类型】{chat_type}
【对话对象】{person_name}
【已空闲时间】{idle_minutes:.0f} 分钟

【最近聊天话题摘要】
{recent_history}

【最近已主动发过的消息（按时间从早到晚）】
{recent_topics_str}

【准备发送的消息】
{message}

【判断要求】
你需要从语义层面判断这条消息是否值得发送，重点检查：

1. 【语义重复】不看字面，看意思。以下都算重复：
   - 同类问候：已发"晚上好+问吃饭"，再发"晚上好+肚子饿"= 重复
   - 同类关心：已发"在做什么"，再发"最近怎么样"= 重复
   - 同类分享：已发"推荐动漫"，再发"聊游戏"不算重复，但再发"推荐番剧"= 重复
   - 同类撒娇：已发"想你了"，再发"好想聊天"= 重复

2. 【时段重复】同一时段（早/中/晚）的问候只发一次

3. 【新意判断】如果最近3条都是同类话题，必须换方向

回答格式：YES/NO - 一句话理由（不超过20字）"""

            response, _ = await self.llm_judge.generate_response_async(
                prompt=prompt,
                temperature=0.3,
                max_tokens=100,
            )

            if not response:
                return True  # 判断失败时默认发送

            response = response.strip().upper()
            should_send = response.startswith("YES")
            logger.info(f"[{stream_id}] LLM 判断结果: {response[:80]}")
            return should_send

        except Exception as e:
            logger.error(f"LLM 判断失败: {e}")
            return True  # 判断失败时默认发送

    async def _initiate_proactive_chat(self, stream):
        """主动发起对话"""
        try:
            stream_id = stream.stream_id
            logger.info(f"准备向 {stream_id} 主动发起对话")

            is_group = stream.group_info is not None

            # 如果是群聊，根据好感度选择要 @ 的成员
            target_user_id = stream.user_info.user_id
            target_nickname = stream.user_info.user_nickname
            relationship_value = 0.0

            if is_group:
                selected = await self._select_group_member_by_intimacy(stream_id, stream.platform)
                if selected:
                    target_user_id, target_nickname, relationship_value = selected
                    logger.info(f"群聊主动对话选择 @ {target_nickname} (好感度: {relationship_value:.1f})")

            # 获取用户信息
            person = Person(platform=stream.platform, user_id=target_user_id)
            person_name = person.person_name or target_nickname

            # 获取最近的聊天历史
            recent_history = await self._get_recent_chat_context(stream_id)

            # 构建prompt（包含好感度信息）
            prompt = self._build_proactive_chat_prompt(
                person_name,
                recent_history,
                is_group,
                relationship_value
            )

            # 调用大模型生成话题
            response, (reasoning, model_name, _) = await self.llm_request.generate_response_async(
                prompt=prompt,
                temperature=0.8,
                max_tokens=200,
            )

            if not response or not response.strip():
                logger.warning(f"大模型未生成有效的主动对话内容")
                return

            message_text = response.strip()

            # 检查话题是否与最近发过的重复
            if self._is_topic_duplicate(stream_id, message_text):
                logger.info(f"[{stream_id}] 跳过：话题与最近发过的内容重复")
                return

            # 获取空闲时间用于判断
            recent_messages = (
                Messages.select()
                .where(Messages.chat_id == stream_id)
                .order_by(Messages.time.desc())
                .limit(1)
            )
            idle_minutes = 0.0
            if recent_messages:
                idle_minutes = (datetime.now().timestamp() - list(recent_messages)[0].time) / 60

            # LLM 判断是否应该发送
            should_send = await self._judge_should_send(
                stream_id=stream_id,
                message=message_text,
                person_name=person_name,
                recent_history=recent_history,
                idle_minutes=idle_minutes,
                is_group=is_group,
            )

            if not should_send:
                logger.info(f"[{stream_id}] LLM 判断不应发送此消息，跳过")
                return

            if is_group:
                # 主动对话时总是 @ 选中的用户
                logger.info(f"准备 @ 用户: {target_nickname} (ID: {target_user_id})")

                # 使用混合消息发送，包含 @ 和文本
                from maim_message import Seg
                segments = [
                    Seg(type="at", data={"qq": target_user_id}),
                    Seg(type="text", data=" " + message_text),
                ]

                # 发送混合消息
                success = await send_api.hybrid_to_stream(
                    segments=segments,
                    stream_id=stream_id,
                    typing=True,
                    storage_message=True,
                )
            else:
                # 私聊直接发送文本
                success = await send_api.text_to_stream(
                    text=message_text,
                    stream_id=stream_id,
                    typing=True,
                    storage_message=True,
                )

            if success:
                # 增加今日主动对话计数
                self.daily_proactive_count[stream_id] = self.daily_proactive_count.get(stream_id, 0) + 1
                # 记录已发送的话题，用于去重
                self._record_proactive_topic(stream_id, message_text)
                logger.info(f"成功向 {stream_id} 发送主动对话（今日第 {self.daily_proactive_count[stream_id]} 次）")
            else:
                logger.error(f"向 {stream_id} 发送主动对话失败")

        except Exception as e:
            logger.error(f"主动发起对话时出错: {e}")
            import traceback
            traceback.print_exc()

    async def _get_recent_chat_context(self, stream_id: str) -> str:
        """获取最近的聊天上下文"""
        try:
            # 获取最近的聊天历史概括
            recent_chats = (
                ChatHistory.select()
                .where(ChatHistory.chat_id == stream_id)
                .order_by(ChatHistory.start_time.desc())
                .limit(3)
            )

            if not recent_chats:
                return "（暂无聊天历史）"

            context = "最近的聊天话题：\n"
            for chat in recent_chats:
                context += f"- {chat.theme}：{chat.summary[:100]}\n"

            return context

        except Exception as e:
            logger.error(f"获取聊天上下文失败: {e}")
            return "（暂无聊天历史）"

    def _build_proactive_chat_prompt(self, person_name: str, recent_history: str, is_group: bool, relationship_value: float = 0.0) -> str:
        """构建主动对话的prompt"""
        chat_type = "群聊" if is_group else "私聊"

        # 获取当前时间信息
        now = datetime.now()
        hour = now.hour
        weekday = now.strftime("%A")
        date_str = now.strftime("%Y年%m月%d日")
        time_str = now.strftime("%H:%M")

        # 判断是否是深夜
        is_night = self._is_night_time()

        # 根据时间段设置上下文和话题
        if 6 <= hour < 11:
            time_context = "早上"
            time_topics = ["早餐吃了什么", "今天有什么计划", "昨晚睡得好吗"]
            energy_level = "元气满满"
        elif 11 <= hour < 14:
            time_context = "中午"
            time_topics = ["午饭吃了什么", "中午有没有休息", "下午有什么安排"]
            energy_level = "活力充沛"
        elif 14 <= hour < 18:
            time_context = "下午"
            time_topics = ["下午在忙什么", "有没有什么有趣的事", "要不要一起玩游戏"]
            energy_level = "精神不错"
        elif 18 <= hour < 22:
            time_context = "晚上"
            time_topics = ["晚饭吃了什么", "今天过得怎么样", "晚上有什么安排"]
            energy_level = "轻松愉快"
        elif 22 <= hour < 24:
            time_context = "深夜"
            time_topics = ["还没睡吗", "在做什么呢", "要不要聊聊天"]
            energy_level = "有点困了但还想聊天"
        else:
            time_context = "凌晨"
            time_topics = ["还没睡吗", "熬夜了呀", "早点休息吧"]
            energy_level = "很困但还醒着"

        # 根据好感度生成关系描述
        from src.common.relationship_updater import RelationshipUpdater
        relationship_level = RelationshipUpdater.get_relationship_level(relationship_value)

        # 好感度相关的提示
        intimacy_hint = ""
        if relationship_value >= 80:
            intimacy_hint = f"你和{person_name}是挚友，关系非常亲密，可以更随意、更亲昵地聊天"
        elif relationship_value >= 60:
            intimacy_hint = f"你和{person_name}是好友，关系不错，可以聊得比较轻松自在"
        elif relationship_value >= 40:
            intimacy_hint = f"你和{person_name}是熟人，可以聊一些日常话题"
        elif relationship_value >= 20:
            intimacy_hint = f"你和{person_name}刚认识不久，可以主动一些增进了解"
        else:
            intimacy_hint = f"你和{person_name}还不太熟，可以友好地打个招呼"

        prompt = f"""你是{global_config.bot.nickname}，{global_config.personality.personality}

你的说话风格：{global_config.personality.reply_style}

【当前时间信息】
- 日期：{date_str}（{weekday}）
- 时间：{time_str}
- 时段：{time_context}
- 你的状态：{energy_level}
{"- 注意：现在是深夜时段，语气要更温柔、更安静一些，不要太吵闹" if is_night else ""}

【聊天场景】
- 对象：{person_name}
- 场景：{chat_type}
- 关系等级：{relationship_level}
- 好感度：{relationship_value:.1f}/100
- 关系提示：{intimacy_hint}

【最近聊天历史】
{recent_history}

【任务】
你想主动和 {person_name} 聊聊天。请根据当前时间、你的状态、你们的关系和聊天历史，自然地发起一个话题。

【话题参考方向】（但不限于此）：
- 时间相关话题：{', '.join(time_topics)}
- 日常关心：问对方在做什么、最近怎么样、心情如何
- 分享内容：分享你看到的有趣事情、新番推荐、游戏话题、ACG相关
- 延续话题：根据之前的聊天历史，延续之前感兴趣的话题
- 猫娘特色：可以撒娇、卖萌、分享猫猫的日常想法

【要求】：
1. 自然、友好、符合你的猫娘性格特点
2. 适度使用猫娘语气词（如"喵"、"呜"、"嘤"等），但不要每句都用
3. 1-2句话即可，简短自然，不要太长
4. 不要说"我看到你..."或"我注意到..."这样的话，要像朋友一样自然聊天
5. 可以有点小傲娇，但要保持可爱
6. 根据时间段调整话题和语气（深夜要更温柔安静，白天可以更活泼）
7. 如果是群聊，语气可以更活泼一些；如果是私聊，可以更亲密一些
8. 根据星期几可以提及周末、工作日等相关话题
9. 根据好感度调整亲密程度：好感度高可以更随意亲昵，好感度低要更礼貌友好

直接输出你想说的话，不要有任何前缀、解释或引号："""

        return prompt
