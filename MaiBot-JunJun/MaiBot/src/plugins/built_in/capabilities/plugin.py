"""能力查询工具插件

将 GetCapabilitiesTool 注册到插件系统。
此前该目录缺少 plugin.py，导致插件加载器（仅扫描 plugin.py）跳过本插件，
GetCapabilitiesTool 始终未注册、对 LLM 不可用。
"""
from typing import List, Tuple, Type

from src.plugin_system import BasePlugin, register_plugin, ComponentInfo
from .get_capabilities import GetCapabilitiesTool


@register_plugin
class CapabilitiesPlugin(BasePlugin):
    """能力查询工具插件"""

    plugin_name: str = "capabilities"
    enable_plugin: bool = True
    dependencies: list[str] = []
    python_dependencies: list[str] = []
    config_file_name: str = ""  # 无需配置文件
    config_schema: dict = {}

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return [(GetCapabilitiesTool.get_tool_info(), GetCapabilitiesTool)]
