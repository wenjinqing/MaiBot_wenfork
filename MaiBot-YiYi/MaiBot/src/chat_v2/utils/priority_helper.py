"""
消息优先级判断工具
"""

from src.chat_v2.utils.message_queue import MessagePriority
from src.config.config import global_config


def get_message_priority(message) -> MessagePriority:
    """
    判断消息的优先级

    Args:
        message: 消息对象

    Returns:
        MessagePriority: 消息优先级
    """
    # 1. 私聊消息 = 高优先级
    if message.chat_type == "private":
        return MessagePriority.HIGH

    # 2. 管理员命令 = 紧急优先级
    if hasattr(message, 'sender_id'):
        admin_list = global_config.bot.admin_list or []
        if message.sender_id in admin_list:
            # 检查是否是命令
            text = getattr(message, 'text', '')
            if text and (text.startswith('/') or text.startswith('!')):
                return MessagePriority.URGENT

    # 3. @ 或提及 = 正常优先级
    if message.is_mentioned or message.is_at:
        return MessagePriority.NORMAL

    # 4. 普通消息 = 低优先级
    return MessagePriority.LOW
