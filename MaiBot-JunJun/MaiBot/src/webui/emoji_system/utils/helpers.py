"""表情包系统工具函数"""
from src.common.database.database_model import Emoji
from ..models.emoji_models import EmojiResponse


def emoji_to_response(emoji: Emoji) -> EmojiResponse:
    """
    将数据库 Emoji 模型转换为响应模型

    Args:
        emoji: 数据库 Emoji 对象

    Returns:
        EmojiResponse 对象
    """
    return EmojiResponse(
        id=emoji.id,
        full_path=emoji.full_path,
        format=emoji.format,
        emoji_hash=emoji.emoji_hash,
        description=emoji.description,
        query_count=emoji.query_count,
        is_registered=emoji.is_registered,
        is_banned=emoji.is_banned,
        emotion=emoji.emotion,
        record_time=emoji.record_time,
        register_time=emoji.register_time,
        usage_count=emoji.usage_count,
        last_used_time=emoji.last_used_time,
    )
