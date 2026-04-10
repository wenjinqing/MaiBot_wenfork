"""
群聊复读检测器 - 检测群聊中的复读行为并加入复读
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from src.common.logger import get_logger
from src.common.message_repository import find_messages
from src.chat.message_receive.chat_stream import get_chat_manager
from src.chat.message_receive.uni_message_sender import get_universal_message_sender
from src.chat.message_receive.message import MessageSending
from maim_message import Seg
from src.config.config import global_config

logger = get_logger("复读检测器")


class RepeatDetector:
    """复读检测器"""

    def __init__(self):
        # 记录每个群最后一次复读的时间，避免频繁复读
        self._last_repeat_time: Dict[str, float] = {}
        # 记录每个群最后一次复读的内容，避免重复复读相同内容
        self._last_repeat_content: Dict[str, str] = {}

    async def check_and_repeat(self, stream_id: str, current_message_text: str) -> bool:
        """
        检查是否应该复读，如果应该则发送复读消息

        Args:
            stream_id: 聊天流ID
            current_message_text: 当前消息的文本内容

        Returns:
            bool: 是否发送了复读消息
        """
        try:
            # 检查是否启用复读功能
            if not getattr(global_config.repeat, 'enable', False):
                return False

            # 获取配置
            repeat_threshold = getattr(global_config.repeat, 'threshold', 4)  # 复读阈值（连续几条相同消息）
            min_interval_seconds = getattr(global_config.repeat, 'min_interval_seconds', 60)  # 最小复读间隔
            min_message_length = getattr(global_config.repeat, 'min_message_length', 1)  # 最小消息长度
            max_message_length = getattr(global_config.repeat, 'max_message_length', 50)  # 最大消息长度

            # 检查消息长度
            if not current_message_text or len(current_message_text) < min_message_length:
                return False

            if len(current_message_text) > max_message_length:
                return False

            # 检查是否是群聊
            chat_stream = get_chat_manager().get_stream(stream_id)
            if not chat_stream or not chat_stream.group_info:
                return False

            # 检查复读间隔
            now = datetime.now().timestamp()
            last_repeat_time = self._last_repeat_time.get(stream_id, 0)
            if now - last_repeat_time < min_interval_seconds:
                return False

            # 检查是否刚刚复读过相同内容
            last_repeat_content = self._last_repeat_content.get(stream_id, "")
            if last_repeat_content == current_message_text:
                return False

            # 获取最近的消息历史（不过滤机器人消息，需要检查是否在复读机器人自己的话）
            recent_messages = find_messages(
                message_filter={'chat_id': stream_id},
                limit=repeat_threshold + 5,  # 多获取几条，确保有足够的数据
                limit_mode='latest',
                filter_bot=False,  # 不过滤机器人消息，需要检查复读来源
                filter_command=True,  # 过滤掉命令消息
            )

            if len(recent_messages) < repeat_threshold:
                return False

            # 检查最近的N条消息是否都相同
            target_text = current_message_text.strip()
            repeat_count = 0
            is_bot_message = False  # 标记被复读的消息是否来自机器人

            # 获取机器人的user_id
            bot_user_id = str(global_config.bot.qq_account)

            # 从最新的消息开始检查
            for msg in reversed(recent_messages):
                msg_text = (msg.processed_plain_text or "").strip()
                if msg_text == target_text:
                    repeat_count += 1
                    # 检查这条消息是否是机器人发送的
                    if msg.user_id == bot_user_id:
                        is_bot_message = True
                else:
                    break

            # 如果被复读的消息是机器人自己发送的，不加入复读
            if is_bot_message:
                logger.debug(f"检测到群友在复读机器人自己的消息，不加入复读: {target_text}")
                return False

            # 如果达到复读阈值，发送复读消息
            if repeat_count >= repeat_threshold:
                logger.info(f"检测到复读 (群: {chat_stream.group_info.group_name}, 内容: {target_text}, 次数: {repeat_count})")

                # 发送复读消息
                success = await self._send_repeat_message(chat_stream, target_text)

                if success:
                    # 更新复读记录
                    self._last_repeat_time[stream_id] = now
                    self._last_repeat_content[stream_id] = target_text
                    logger.info(f"成功发送复读消息: {target_text}")
                    return True

            return False

        except Exception as e:
            logger.error(f"检查复读失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def _send_repeat_message(self, chat_stream, text: str) -> bool:
        """
        发送复读消息

        Args:
            chat_stream: ChatStream对象
            text: 要复读的文本

        Returns:
            bool: 是否成功
        """
        try:
            # 创建消息发送器
            sender = get_universal_message_sender()

            # 获取机器人用户信息
            bot_user_info = chat_stream.bot_user_info

            # 创建消息对象
            message = MessageSending(
                message_id=str(uuid.uuid4()),
                chat_stream=chat_stream,
                bot_user_info=bot_user_info,
                sender_info=None,
                message_segment=Seg(type="text", data=text),
                display_message=text,
                reply=None,
                is_head=False,
                is_emoji=False,
            )

            # 发送消息
            await sender.send_message(
                message=message,
                typing=False,  # 不模拟打字，快速发送
                set_reply=False,
                storage_message=True,  # 存储到数据库
                show_log=True,
            )

            return True

        except Exception as e:
            logger.error(f"发送复读消息失败: {e}")
            import traceback
            traceback.print_exc()
            return False


# 全局复读检测器实例
_repeat_detector: Optional[RepeatDetector] = None


def get_repeat_detector() -> RepeatDetector:
    """获取全局复读检测器实例"""
    global _repeat_detector
    if _repeat_detector is None:
        _repeat_detector = RepeatDetector()
    return _repeat_detector
