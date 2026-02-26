"""群聊回复器模块 - 向后兼容的导入接口"""

# 导入工具函数
from .utils.helpers import weighted_sample_no_replacement

# 导入主类（从原文件）
import sys
from pathlib import Path

# 添加原文件路径以保持兼容性
parent_path = Path(__file__).parent.parent
if str(parent_path) not in sys.path:
    sys.path.insert(0, str(parent_path))

try:
    from group_generator import DefaultReplyer
except ImportError:
    # 如果导入失败，提供占位符
    class DefaultReplyer:
        """占位符 - 需要从原文件迁移"""
        pass

__all__ = [
    "DefaultReplyer",
    "weighted_sample_no_replacement",
]
