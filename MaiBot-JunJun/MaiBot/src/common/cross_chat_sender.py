"""
跨会话消息发送工具
支持在群聊和私聊之间转发消息
"""

import time
from typing import Optional
from maim_message import UserInfo, GroupInfo, BaseMessageInfo
from src.common.logger import get_logger
from src.chat.message_receive.message import MessageSending
from src.chat.message_receive.uni_message_sender import _send_message
from src.common.database.database_model import ChatStreams, db

logger = get_logger("cross_chat_sender")


class CrossChatSender:
    """跨会话消息发送器"""

    @staticmethod
    async def send_to_private(
        platform: str,
        user_id: str,
        content: str,
        message_type: str = "text",
        content_path: str = None
    ) -> bool:
        """
        发送消息到私聊

        Args:
            platform: 平台（如qq）
            user_id: 用户ID
            content: 消息内容
            message_type: 消息类型（text/imageurl/voiceurl等）
            content_path: 内容路径（用于图片、语音等）

        Returns:
            bool: 是否发送成功
        """
        try:
            # 参数验证
            if not platform or not user_id:
                logger.error("跨会话发送失败：缺少必要参数 platform 或 user_id")
                return False

            # 查询私聊会话
            with db:
                chat_stream = ChatStreams.get_or_none(
                    (ChatStreams.platform == platform) &
                    (ChatStreams.user_platform == platform) &
                    (ChatStreams.user_id == user_id) &
                    (ChatStreams.group_id.is_null(True))
                )

                if not chat_stream:
                    logger.warning(f"未找到用户 {user_id}@{platform} 的私聊会话，可能该用户从未私聊过")
                    return False

                # 构建用户信息
                user_info = UserInfo(
                    user_platform=platform,
                    user_id=user_id,
                    user_nickname=chat_stream.user_nickname or "未知用户",
                    user_cardname=None
                )

                # 构建消息信息
                message_info = BaseMessageInfo(
                    platform=platform,
                    user_info=user_info,
                    group_info=None,  # 私聊没有群信息
                    message_id=f"cross_chat_{int(time.time() * 1000)}"
                )

                # 构建消息对象
                if message_type == "text":
                    processed_text = content
                    display_text = content
                elif message_type in ["imageurl", "voiceurl"] and content_path:
                    processed_text = content_path
                    display_text = f"[{message_type}]"
                else:
                    processed_text = f"[{message_type}]"
                    display_text = f"[{message_type}]"

                message = MessageSending(
                    message_info=message_info,
                    processed_plain_text=processed_text,
                    display_message=display_text,
                    raw_message=content if message_type == "text" else f"[{message_type}]"
                )

                # 发送消息
                await _send_message(message, show_log=True)
                logger.info(f"跨会话发送成功：{platform}/{user_id} (私聊)")
                return True

        except Exception as e:
            logger.error(f"跨会话发送到私聊失败: {e}", exc_info=True)
            return False

    @staticmethod
    async def send_to_group(
        platform: str,
        group_id: str,
        content: str,
        message_type: str = "text",
        content_path: str = None
    ) -> bool:
        """
        发送消息到群聊

        Args:
            platform: 平台（如qq）
            group_id: 群ID
            content: 消息内容
            message_type: 消息类型（text/imageurl/voiceurl等）
            content_path: 内容路径（用于图片、语音等）

        Returns:
            bool: 是否发送成功
        """
        try:
            # 参数验证
            if not platform or not group_id:
                logger.error("跨会话发送失败：缺少必要参数 platform 或 group_id")
                return False

            # 查询群聊会话
            with db:
                chat_stream = ChatStreams.get_or_none(
                    (ChatStreams.platform == platform) &
                    (ChatStreams.group_id == group_id)
                )

                if not chat_stream:
                    logger.warning(f"未找到群 {group_id}@{platform} 的会话")
                    return False

                # 构建用户信息（使用群的第一个用户）
                user_info = UserInfo(
                    user_platform=platform,
                    user_id=chat_stream.user_id,
                    user_nickname=chat_stream.user_nickname or "未知用户",
                    user_cardname=chat_stream.user_cardname
                )

                # 构建群信息
                group_info = GroupInfo(
                    group_platform=platform,
                    group_id=group_id,
                    group_name=chat_stream.group_name or "未知群"
                )

                # 构建消息信息
                message_info = MessageInfo(
                    platform=platform,
                    user_info=user_info,
                    group_info=group_info,
                    message_id=f"cross_chat_{int(time.time() * 1000)}"
                )

                # 构建消息对象
                if message_type == "text":
                    processed_text = content
                    display_text = content
                elif message_type in ["imageurl", "voiceurl"] and content_path:
                    processed_text = content_path
                    display_text = f"[{message_type}]"
                else:
                    processed_text = f"[{message_type}]"
                    display_text = f"[{message_type}]"

                message = MessageSending(
                    message_info=message_info,
                    processed_plain_text=processed_text,
                    display_message=display_text,
                    raw_message=content if message_type == "text" else f"[{message_type}]"
                )

                # 发送消息
                await _send_message(message, show_log=True)
                logger.info(f"跨会话发送成功：{platform}/{group_id} (群聊)")
                return True

        except Exception as e:
            logger.error(f"跨会话发送到群聊失败: {e}", exc_info=True)
            return False

    @staticmethod
    async def find_user_groups(platform: str, user_id: str) -> list:
        """
        查找用户所在的所有群

        Args:
            platform: 平台
            user_id: 用户ID

        Returns:
            list: 群ID列表
        """
        try:
            with db:
                groups = ChatStreams.select(ChatStreams.group_id).where(
                    (ChatStreams.platform == platform) &
                    (ChatStreams.user_id == user_id) &
                    (ChatStreams.group_id.is_null(False))
                ).distinct()

                return [g.group_id for g in groups if g.group_id]

        except Exception as e:
            logger.error(f"查找用户群组失败: {e}", exc_info=True)
            return []
