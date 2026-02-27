"""
记忆检索工具模块
提供统一的工具注册和管理系统
"""

from .tool_registry import (
    MemoryRetrievalTool,
    MemoryRetrievalToolRegistry,
    register_memory_retrieval_tool,
    get_tool_registry,
)

# 导入所有工具的注册函数
from .query_chat_history import register_tool as register_query_chat_history
from .query_lpmm_knowledge import register_tool as register_lpmm_knowledge
from .query_person_info import register_tool as register_query_person_info
from .found_answer import register_tool as register_found_answer
from .query_chat_history_by_type import search_chat_history_by_type  # 新增
from .query_cross_scene_chat import query_cross_scene_chat  # 跨场景查询工具
from src.config.config import global_config


def init_all_tools():
    """初始化并注册所有记忆检索工具"""
    register_query_chat_history()
    register_query_person_info()
    register_found_answer()  # 注册found_answer工具

    # 注册按聊天类型查询工具（已在模块中自动注册）
    # query_chat_history_by_type 工具在导入时自动注册

    # 跨场景查询工具在导入时自动注册
    # query_cross_scene_chat 工具在导入时自动注册

    if global_config.lpmm_knowledge.lpmm_mode == "agent":
        register_lpmm_knowledge()


__all__ = [
    "MemoryRetrievalTool",
    "MemoryRetrievalToolRegistry",
    "register_memory_retrieval_tool",
    "get_tool_registry",
    "init_all_tools",
]
