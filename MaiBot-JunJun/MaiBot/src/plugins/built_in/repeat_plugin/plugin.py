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
        "repeat": "复读行为参数",
    }

    config_schema: dict = {
        "plugin": {
            # 注意：框架读取的是 [plugin].enabled（不是 enable），此处必须为 enabled
            "enabled": ConfigField(type=bool, default=True, description="是否启用复读插件"),
        },
        "components": {
            # 默认关闭：仅当显式置为 true 时才注册复读 Action（避免无意义地占用 planner 选项）
            "enable_repeat_action": ConfigField(
                type=bool, default=False, description="是否注册复读 Action（开启后机器人会在群里跟着复读）"
            ),
        },
        "repeat": {
            "threshold": ConfigField(type=int, default=4, description="连续多少条相同消息后触发复读"),
            "min_interval_seconds": ConfigField(type=int, default=60, description="同一群两次复读的最小间隔(秒)"),
            "min_message_length": ConfigField(type=int, default=1, description="参与复读的最小消息长度"),
            "max_message_length": ConfigField(type=int, default=50, description="参与复读的最大消息长度"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """获取插件组件"""
        components = []

        # 注册复读 Action（默认关闭）
        if self.get_config("components.enable_repeat_action", False):
            components.append((RepeatAction.get_action_info(), RepeatAction))

        return components
