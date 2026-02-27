"""日志系统模块 - 向后兼容的导入接口

注意：logger.py 是核心系统文件，已在任务3中进行了线程安全修复。
完整重构需要谨慎处理，建议保持当前结构。
"""

# 从原 logger.py 导入所有内容以保持兼容性
from ..logger import *

__all__ = ["get_logger"]
