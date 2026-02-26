"""
提醒任务插件

提供提醒任务相关的功能：
- 设置提醒
- 查看提醒列表
- 取消提醒
"""

from typing import List, Tuple, Type

from src.plugin_system import BasePlugin, register_plugin, ComponentInfo
from src.plugin_system.base.config_types import ConfigField
from src.common.logger import get_logger

# 导入提醒任务Actions
from src.proactive_system.reminder_actions import SetReminderAction, ListRemindersAction, CancelReminderAction

logger = get_logger("reminder_plugin")


@register_plugin
class ReminderPlugin(BasePlugin):
    """提醒任务插件

    系统内置插件，提供提醒任务功能：
    - SetReminder: 设置提醒任务
    - ListReminders: 查看提醒列表
    - CancelReminder: 取消提醒任务

    注意：插件基本信息优先从_manifest.json文件中读取
    """

    # 插件基本信息
    plugin_name: str = "reminder_plugin"
    enable_plugin: bool = True
    dependencies: list[str] = []
    python_dependencies: list[str] = []
    config_file_name: str = "config.toml"

    # 配置节描述
    config_section_descriptions = {
        "plugin": "插件启用配置",
        "components": "提醒功能组件启用配置",
    }

    # 配置Schema定义
    config_schema: dict = {
        "plugin": {
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
            "config_version": ConfigField(type=str, default="1.0.0", description="配置文件版本"),
        },
        "components": {
            "enable_set_reminder": ConfigField(type=bool, default=True, description="是否启用设置提醒功能"),
            "enable_list_reminders": ConfigField(type=bool, default=True, description="是否启用查看提醒列表功能"),
            "enable_cancel_reminder": ConfigField(type=bool, default=True, description="是否启用取消提醒功能"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件包含的组件列表"""

        components = []

        if self.get_config("components.enable_set_reminder", True):
            components.append((SetReminderAction.get_action_info(), SetReminderAction))

        if self.get_config("components.enable_list_reminders", True):
            components.append((ListRemindersAction.get_action_info(), ListRemindersAction))

        if self.get_config("components.enable_cancel_reminder", True):
            components.append((CancelReminderAction.get_action_info(), CancelReminderAction))

        return components
