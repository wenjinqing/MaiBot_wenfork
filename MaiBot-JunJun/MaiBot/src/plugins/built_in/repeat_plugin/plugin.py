"""
复读插件主文件
"""
from typing import List, Tuple, Type
from src.plugin_system import BasePlugin, register_plugin, ComponentInfo
from src.plugin_system.base.config_types import ConfigField
from .repeat_action import RepeatAction


@register_plugin
class RepeatPlugin(BasePlugin):
    """复读插件"""

    plugin_name: str = "repeat_plugin"
    enable_plugin: bool = True
    dependencies: list[str] = []
    python_dependencies: list[str] = []
    config_file_name: str = "config.toml"

    config_section_descriptions = {
        "plugin": "插件启用配置",
        "components": "复读 Action 开关",
    }

    config_schema: dict = {
        "plugin": {
            "enable": ConfigField(type=bool, default=True, description="是否启用复读插件"),
        },
        "components": {
            "enable_repeat_action": ConfigField(type=bool, default=True, description="是否注册复读 Action"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """获取插件组件"""
        components = []

        # 注册复读 Action
        if self.get_config("components.enable_repeat_action", True):
            components.append((RepeatAction.get_action_info(), RepeatAction))

        return components
