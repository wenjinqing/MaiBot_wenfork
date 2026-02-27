"""
Core - 多机器人核心模块

提供多机器人部署的核心功能：
- BotInstance: 单个机器人实例
- MessageRouter: 消息路由器
- BotScopedDB: 带 bot_id 作用域的数据库访问层
- BotContext: 机器人上下文管理
"""

from .bot_instance import BotInstance, BotStatus
from .message_router import MessageRouter, get_message_router
from .bot_scoped_db import BotScopedDB
from .bot_context import (
    set_current_bot_id,
    get_current_bot_id,
    clear_current_bot_id,
    BotContextManager,
    with_bot_context,
    get_current_bot_db,
)

__all__ = [
    "BotInstance",
    "BotStatus",
    "MessageRouter",
    "get_message_router",
    "BotScopedDB",
    "set_current_bot_id",
    "get_current_bot_id",
    "clear_current_bot_id",
    "BotContextManager",
    "with_bot_context",
    "get_current_bot_db",
]
