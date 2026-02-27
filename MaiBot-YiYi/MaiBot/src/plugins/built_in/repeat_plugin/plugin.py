"""
复读插件主文件
"""
from typing import List, Tuple, Type
from src.plugin_system import BasePlugin, register_plugin, ComponentInfo
from .repeat_action import RepeatAction


@register_plugin
class RepeatPlugin(BasePlugin):
    """复读插件"""

    plugin_name: str = "repeat_plugin"
    enable_plugin: bool = True

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """获取插件组件"""
        components = []

        # 注册复读 Action
        if self.get_config("components.enable_repeat_action", True):
            components.append((RepeatAction.get_action_info(), RepeatAction))

        return components
