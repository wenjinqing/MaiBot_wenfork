"""
@ 提及功能辅助模块
智能判断何时需要 @ 群成员
"""
from typing import Optional
from src.common.logger import get_logger
from src.common.database.database_model import Messages
from src.config.config import global_config

logger = get_logger("mention_helper")


class MentionHelper:
    """@ 提及功能辅助类"""

    @staticmethod
    def should_mention_user(
        reply_message: Optional[Messages] = None,
        is_proactive: bool = False,
        is_group: bool = False,
        recent_message_count: int = 0,
    ) -> bool:
        """判断是否应该 @ 用户

        Args:
            reply_message: 回复的消息对象
            is_proactive: 是否是主动发起的对话
            is_group: 是否是群聊
            recent_message_count: 最近消息数量（用于判断群聊活跃度）

        Returns:
            bool: 是否应该 @
        """
        # 检查配置是否启用 @ 功能
        mention_config = getattr(global_config, 'mention', None)
        if not mention_config or not getattr(mention_config, 'enable', True):
            return False

        # 私聊不需要 @
        if not is_group:
            return False

        # 主动发起对话时，根据配置决定是否 @
        if is_proactive:
            return getattr(mention_config, 'proactive_mention', True)

        # 回复消息时，根据群聊活跃度判断
        if reply_message:
            threshold = getattr(mention_config, 'reply_mention_threshold', 5)
            # 如果最近消息很多（群聊活跃），则 @ 以明确回复对象
            if recent_message_count > threshold:
                return True

            # 其他情况不 @
            return False

        # 其他情况不 @
        return False

    @staticmethod
    def add_mention_to_text(text: str, user_id: str, user_nickname: str) -> str:
        """在文本开头添加 @ 提及

        Args:
            text: 原始文本
            user_id: 用户ID
            user_nickname: 用户昵称

        Returns:
            str: 添加了 @ 的文本
        """
        # 使用 [CQ:at,qq=用户ID] 格式（QQ 平台标准格式）
        mention = f"[CQ:at,qq={user_id}] "
        return mention + text

    @staticmethod
    def get_mention_target(reply_message: Optional[Messages]) -> Optional[tuple[str, str]]:
        """获取需要 @ 的目标用户信息

        Args:
            reply_message: 回复的消息对象

        Returns:
            Optional[tuple[str, str]]: (user_id, user_nickname) 或 None
        """
        if not reply_message:
            return None

        user_id = reply_message.user_id
        user_nickname = reply_message.user_info.user_nickname or user_id

        # 不 @ 机器人自己
        bot_id = str(global_config.bot.qq_account)
        if user_id == bot_id:
            return None

        return (user_id, user_nickname)
