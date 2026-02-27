"""功能模块"""

from .image_module import RandomImageAction, RandomImageCommand
from .body_part_module import BodyPartImageAction, BodyPartImageCommand, JKImageAction, JKImageCommand
from .news_module import News60sTool, TodayInHistoryTool, NewsCommand, HistoryCommand
from .music_module import MusicCommand, ChooseCommand, QuickChooseCommand
from .ai_draw_module import AIDrawCommand
from .auto_image_tool import AIDrawTool

__all__ = [
    # 图片模块
    'RandomImageAction',
    'RandomImageCommand',
    # 身体部位模块
    'BodyPartImageAction',
    'BodyPartImageCommand',
    # JK模块
    'JKImageAction',
    'JKImageCommand',
    # 新闻模块
    'News60sTool',
    'TodayInHistoryTool',
    'NewsCommand',
    'HistoryCommand',
    # 音乐模块
    'MusicCommand',
    'ChooseCommand',
    'QuickChooseCommand',
    # AI绘图模块
    'AIDrawCommand',
    'AIDrawTool',
]
