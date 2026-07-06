"""
新闻插件（从 music_plugin 拆分独立，故障隔离）

每天60秒读懂世界 + 历史上的今天。提供 Tool（LLM 调用）和 Command（/news、/history）。
"""

from typing import List, Tuple, Type
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
    ConfigField,
)
from src.common.logger import get_logger

from .modules.news_module import (
    News60sTool,
    TodayInHistoryTool,
    NewsCommand,
    HistoryCommand,
)

logger = get_logger("news_plugin")


@register_plugin
class NewsPlugin(BasePlugin):
    """新闻插件"""

    plugin_name = "news_plugin"
    plugin_description = "每天60秒读懂世界 + 历史上的今天"
    plugin_version = "1.0.0"
    plugin_author = "JunJun"
    enable_plugin = True
    config_file_name = "config.toml"
    dependencies = []
    python_dependencies = ["aiohttp"]

    config_section_descriptions = {
        "plugin": "插件基本配置",
        "news": "新闻功能配置",
    }

    config_schema = {
        "plugin": {
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
            "name": ConfigField(type=str, default="news_plugin", description="插件名称"),
            "version": ConfigField(type=str, default="1.0.0", description="插件版本"),
        },
        "news": {
            "api_url": ConfigField(type=str, default="https://60s.viki.moe/v2/60s", description="60秒新闻API地址"),
            "history_api_url": ConfigField(type=str, default="https://60s.viki.moe/v2/today-in-history", description="历史上的今天API地址"),
            "send_image": ConfigField(type=bool, default=True, description="是否发送新闻图片"),
            "send_text": ConfigField(type=bool, default=True, description="是否发送新闻文本"),
            "max_history_events": ConfigField(type=int, default=10, description="历史事件最大显示数量"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回新闻组件：60秒新闻 Tool + 历史上的今天 Tool + /news、/history 命令"""
        return [
            (News60sTool.get_tool_info(), News60sTool),
            (TodayInHistoryTool.get_tool_info(), TodayInHistoryTool),
            (NewsCommand.get_command_info(), NewsCommand),
            (HistoryCommand.get_command_info(), HistoryCommand),
        ]
