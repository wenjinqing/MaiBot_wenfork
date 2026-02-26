"""
数据库查询辅助工具

提供便捷的数据库查询方法，自动添加 bot_id 过滤。
用于逐步迁移现有代码到多机器人模式。
"""

from typing import Optional
from src.common.database.database_model import PersonInfo, db
from src.core.bot_context import get_current_bot_id
from src.common.logger import get_logger

logger = get_logger("db_helpers")


def get_person_info_with_bot_id(platform: str, user_id: str, bot_id: Optional[str] = None) -> Optional[PersonInfo]:
    """
    获取用户信息（自动添加 bot_id 过滤）

    Args:
        platform: 平台
        user_id: 用户ID
        bot_id: 机器人ID（如果不提供，则使用当前上下文的 bot_id）

    Returns:
        PersonInfo 对象，如果不存在则返回 None
    """
    if bot_id is None:
        bot_id = get_current_bot_id()

    return PersonInfo.get_or_none(
        PersonInfo.bot_id == bot_id,
        PersonInfo.platform == platform,
        PersonInfo.user_id == user_id
    )


def create_person_info_with_bot_id(
    platform: str,
    user_id: str,
    bot_id: Optional[str] = None,
    **kwargs
) -> PersonInfo:
    """
    创建用户信息（自动添加 bot_id）

    Args:
        platform: 平台
        user_id: 用户ID
        bot_id: 机器人ID（如果不提供，则使用当前上下文的 bot_id）
        **kwargs: 其他字段

    Returns:
        创建的 PersonInfo 对象
    """
    if bot_id is None:
        bot_id = get_current_bot_id()

    # 生成 person_id
    person_id = f"{bot_id}_{platform}_{user_id}"

    with db:
        person = PersonInfo.create(
            bot_id=bot_id,
            platform=platform,
            user_id=user_id,
            person_id=person_id,
            **kwargs
        )

    logger.debug(f"创建用户信息: {person_id} (bot_id: {bot_id})")
    return person


def get_or_create_person_info_with_bot_id(
    platform: str,
    user_id: str,
    bot_id: Optional[str] = None,
    **kwargs
) -> tuple[PersonInfo, bool]:
    """
    获取或创建用户信息（自动添加 bot_id）

    Args:
        platform: 平台
        user_id: 用户ID
        bot_id: 机器人ID（如果不提供，则使用当前上下文的 bot_id）
        **kwargs: 创建时的其他字段

    Returns:
        (PersonInfo 对象, 是否新创建)
    """
    if bot_id is None:
        bot_id = get_current_bot_id()

    person = get_person_info_with_bot_id(platform, user_id, bot_id)
    if person:
        return person, False

    person = create_person_info_with_bot_id(platform, user_id, bot_id, **kwargs)
    return person, True


# 便捷函数：用于替换现有代码中的 PersonInfo.get_or_none
def safe_get_person_info(platform: str, user_id: str) -> Optional[PersonInfo]:
    """
    安全地获取用户信息（兼容旧代码）

    这个函数会自动使用当前上下文的 bot_id。
    如果没有设置上下文，则使用默认值 "maimai_main"。

    Args:
        platform: 平台
        user_id: 用户ID

    Returns:
        PersonInfo 对象，如果不存在则返回 None
    """
    return get_person_info_with_bot_id(platform, user_id)


# 便捷函数：用于替换现有代码中的 PersonInfo.get
def safe_get_person_info_required(platform: str, user_id: str) -> PersonInfo:
    """
    安全地获取用户信息（必须存在，兼容旧代码）

    Args:
        platform: 平台
        user_id: 用户ID

    Returns:
        PersonInfo 对象

    Raises:
        DoesNotExist: 如果用户不存在
    """
    bot_id = get_current_bot_id()
    return PersonInfo.get(
        PersonInfo.bot_id == bot_id,
        PersonInfo.platform == platform,
        PersonInfo.user_id == user_id
    )
