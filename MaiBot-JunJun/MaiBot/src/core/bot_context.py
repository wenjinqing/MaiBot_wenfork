"""
BotContext - 机器人上下文管理

提供线程安全的 bot_id 上下文，让现有代码可以无缝支持多机器人。
使用 contextvars 实现，确保异步安全。
"""

from contextvars import ContextVar
from typing import Optional
from src.common.logger import get_logger

logger = get_logger("BotContext")

# 当前机器人 ID 的上下文变量
_current_bot_id: ContextVar[Optional[str]] = ContextVar('current_bot_id', default=None)


def set_current_bot_id(bot_id: str):
    """
    设置当前机器人 ID

    Args:
        bot_id: 机器人 ID
    """
    _current_bot_id.set(bot_id)
    logger.debug(f"设置当前 bot_id: {bot_id}")


def get_current_bot_id() -> str:
    """
    获取当前机器人 ID

    Returns:
        当前机器人 ID，如果未设置则返回默认值 "maimai_main"
    """
    bot_id = _current_bot_id.get()
    if bot_id is None:
        # 默认返回 maimai_main（向后兼容）
        logger.debug("未设置 bot_id，使用默认值: maimai_main")
        return "maimai_main"
    return bot_id


def clear_current_bot_id():
    """清除当前机器人 ID"""
    _current_bot_id.set(None)
    logger.debug("清除当前 bot_id")


class BotContextManager:
    """机器人上下文管理器（用于 with 语句）"""

    def __init__(self, bot_id: str):
        """
        初始化上下文管理器

        Args:
            bot_id: 机器人 ID
        """
        self.bot_id = bot_id
        self.previous_bot_id = None

    def __enter__(self):
        """进入上下文"""
        self.previous_bot_id = _current_bot_id.get()
        set_current_bot_id(self.bot_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        if self.previous_bot_id is not None:
            _current_bot_id.set(self.previous_bot_id)
        else:
            clear_current_bot_id()
        return False


def with_bot_context(bot_id: str):
    """
    装饰器：为函数设置机器人上下文

    Args:
        bot_id: 机器人 ID

    Example:
        @with_bot_context("maimai_main")
        async def process_message(message):
            # 在这个函数内，get_current_bot_id() 会返回 "maimai_main"
            pass
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            with BotContextManager(bot_id):
                return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            with BotContextManager(bot_id):
                return func(*args, **kwargs)

        # 判断是否是异步函数
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# 便捷函数：获取当前机器人的数据库访问层
def get_current_bot_db():
    """
    获取当前机器人的数据库访问层

    Returns:
        BotScopedDB 实例
    """
    from src.core.bot_scoped_db import BotScopedDB
    bot_id = get_current_bot_id()
    return BotScopedDB(bot_id)
