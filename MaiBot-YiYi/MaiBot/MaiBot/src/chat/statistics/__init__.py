"""统计模块 - 向后兼容的导入接口

此文件保持与原 statistic.py 的兼容性，同时将实现拆分到子模块中。
"""

# 导入常量
from .constants import (
    TOTAL_REQ_CNT,
    TOTAL_COST,
    REQ_CNT_BY_TYPE,
    REQ_CNT_BY_USER,
    REQ_CNT_BY_MODEL,
    REQ_CNT_BY_MODULE,
    IN_TOK_BY_TYPE,
    IN_TOK_BY_USER,
    IN_TOK_BY_MODEL,
    IN_TOK_BY_MODULE,
    OUT_TOK_BY_TYPE,
    OUT_TOK_BY_USER,
    OUT_TOK_BY_MODEL,
    OUT_TOK_BY_MODULE,
    TOTAL_TOK_BY_TYPE,
    TOTAL_TOK_BY_USER,
    TOTAL_TOK_BY_MODEL,
    TOTAL_TOK_BY_MODULE,
    COST_BY_TYPE,
    COST_BY_USER,
    COST_BY_MODEL,
    COST_BY_MODULE,
    TIME_COST_BY_TYPE,
    TIME_COST_BY_USER,
    TIME_COST_BY_MODEL,
    TIME_COST_BY_MODULE,
    AVG_TIME_COST_BY_TYPE,
    AVG_TIME_COST_BY_USER,
    AVG_TIME_COST_BY_MODEL,
    AVG_TIME_COST_BY_MODULE,
    STD_TIME_COST_BY_TYPE,
    STD_TIME_COST_BY_USER,
    STD_TIME_COST_BY_MODEL,
    STD_TIME_COST_BY_MODULE,
    ONLINE_TIME,
    TOTAL_MSG_CNT,
    MSG_CNT_BY_CHAT,
    TOTAL_REPLY_CNT,
)

# 导入工具函数（保持私有函数名以兼容）
from .utils import format_online_time as _format_online_time
from .utils import format_large_number as _format_large_number

# 导入主要类（这些需要从原文件中提取）
# 暂时从原文件导入以保持兼容性
import sys
from pathlib import Path

# 添加原文件路径
old_utils_path = Path(__file__).parent.parent / "utils"
if str(old_utils_path) not in sys.path:
    sys.path.insert(0, str(old_utils_path))

try:
    from statistic import OnlineTimeRecordTask, StatisticOutputTask, AsyncStatisticOutputTask
except ImportError:
    # 如果导入失败，提供占位符
    from src.manager.async_task_manager import AsyncTask

    class OnlineTimeRecordTask(AsyncTask):
        """占位符 - 需要从原文件迁移"""
        pass

    class StatisticOutputTask(AsyncTask):
        """占位符 - 需要从原文件迁移"""
        pass

    class AsyncStatisticOutputTask(AsyncTask):
        """占位符 - 需要从原文件迁移"""
        pass

__all__ = [
    # 常量
    "TOTAL_REQ_CNT",
    "TOTAL_COST",
    "REQ_CNT_BY_TYPE",
    "REQ_CNT_BY_USER",
    "REQ_CNT_BY_MODEL",
    "REQ_CNT_BY_MODULE",
    "IN_TOK_BY_TYPE",
    "IN_TOK_BY_USER",
    "IN_TOK_BY_MODEL",
    "IN_TOK_BY_MODULE",
    "OUT_TOK_BY_TYPE",
    "OUT_TOK_BY_USER",
    "OUT_TOK_BY_MODEL",
    "OUT_TOK_BY_MODULE",
    "TOTAL_TOK_BY_TYPE",
    "TOTAL_TOK_BY_USER",
    "TOTAL_TOK_BY_MODEL",
    "TOTAL_TOK_BY_MODULE",
    "COST_BY_TYPE",
    "COST_BY_USER",
    "COST_BY_MODEL",
    "COST_BY_MODULE",
    "TIME_COST_BY_TYPE",
    "TIME_COST_BY_USER",
    "TIME_COST_BY_MODEL",
    "TIME_COST_BY_MODULE",
    "AVG_TIME_COST_BY_TYPE",
    "AVG_TIME_COST_BY_USER",
    "AVG_TIME_COST_BY_MODEL",
    "AVG_TIME_COST_BY_MODULE",
    "STD_TIME_COST_BY_TYPE",
    "STD_TIME_COST_BY_USER",
    "STD_TIME_COST_BY_MODEL",
    "STD_TIME_COST_BY_MODULE",
    "ONLINE_TIME",
    "TOTAL_MSG_CNT",
    "MSG_CNT_BY_CHAT",
    "TOTAL_REPLY_CNT",
    # 工具函数
    "_format_online_time",
    "_format_large_number",
    # 类
    "OnlineTimeRecordTask",
    "StatisticOutputTask",
    "AsyncStatisticOutputTask",
]
