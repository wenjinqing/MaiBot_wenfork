"""
聊天循环模块

支持持续运行的聊天循环、主动发言、定时任务等功能
"""

from src.chat_v2.loop.chat_loop import (
    ChatLoop,
    ScheduledTask,
    ChatLoopManager,
    chat_loop_manager,
)

__all__ = [
    "ChatLoop",
    "ScheduledTask",
    "ChatLoopManager",
    "chat_loop_manager",
]
