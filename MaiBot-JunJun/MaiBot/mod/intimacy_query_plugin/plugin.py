"""
好感度查询插件
提供好感度查询功能
"""

from typing import List, Tuple, Type
from src.plugin_system import BasePlugin, register_plugin, ComponentInfo
from src.common.intimacy_query_action import IntimacyQueryAction


@register_plugin
class IntimacyQueryPlugin(BasePlugin):
    """好感度查询插件"""

    plugin_name = "IntimacyQueryPlugin"
    plugin_description = "提供好感度查询功能，用户可以通过关键词查询自己的好感度"
    plugin_author = "MaiBot Team"
    enable_plugin = True
    config_file_name = None  # 不需要配置文件
    dependencies = []
    python_dependencies = []

    # 添加必需的 config_schema
    config_schema = {}

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件提供的组件"""
        return [
            (IntimacyQueryAction.get_action_info(), IntimacyQueryAction),
        ]

