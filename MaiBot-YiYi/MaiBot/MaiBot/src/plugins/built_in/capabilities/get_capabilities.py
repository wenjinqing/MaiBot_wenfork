"""获取 MaiBot 功能列表的工具"""

from typing import Dict, Any, List

from src.common.logger import get_logger
from src.plugin_system import BaseTool, ToolParamType
from src.plugin_system.core.component_registry import component_registry
from src.plugin_system.apis.component_manage_api import get_enabled_components_info_by_type
from src.plugin_system.base.component_types import ComponentType

logger = get_logger("get_capabilities_tool")


class GetCapabilitiesTool(BaseTool):
    """获取 MaiBot 已启用功能列表的工具"""

    name = "get_capabilities"
    description = "查询 MaiBot 当前已启用的所有功能（插件、动作、命令、工具等）。当用户询问'你有什么功能'、'你能做什么'、'你会什么'等问题时使用此工具。"
    parameters = [
        ("type", ToolParamType.STRING, "查询类型：'all'(所有功能)、'plugins'(插件列表)、'actions'(动作列表)、'commands'(命令列表)、'tools'(工具列表)。默认为'all'", False, ["all", "plugins", "actions", "commands", "tools"]),
    ]
    available_for_llm = True

    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行功能查询

        Args:
            function_args: 工具参数

        Returns:
            Dict: 工具执行结果
        """
        try:
            query_type = function_args.get("type", "all")

            result_parts = []

            # 获取所有启用的插件
            all_plugins = component_registry.get_all_plugins()
            enabled_plugins = {name: info for name, info in all_plugins.items() if info.enabled}

            if query_type in ["all", "plugins"]:
                if enabled_plugins:
                    result_parts.append("## 已启用的插件：")
                    for plugin_name, plugin_info in enabled_plugins.items():
                        components_count = len(plugin_info.components)
                        result_parts.append(f"- **{plugin_name}**: {components_count} 个组件")
                else:
                    result_parts.append("## 已启用的插件：无")

            if query_type in ["all", "actions"]:
                # 获取启用的动作
                enabled_actions = get_enabled_components_info_by_type(ComponentType.ACTION)
                if enabled_actions:
                    result_parts.append("\n## 可用的动作：")
                    for action_name, action_info in enabled_actions.items():
                        # 跳过系统内置动作
                        if action_name in ["emoji", "build_memory", "build_relation", "reply"]:
                            continue
                        description = action_info.description or "无描述"
                        result_parts.append(f"- **{action_name}**: {description}")
                else:
                    result_parts.append("\n## 可用的动作：无")

            if query_type in ["all", "commands"]:
                # 获取启用的命令
                enabled_commands = get_enabled_components_info_by_type(ComponentType.COMMAND)
                if enabled_commands:
                    result_parts.append("\n## 可用的命令：")
                    for cmd_name, cmd_info in enabled_commands.items():
                        description = cmd_info.description or "无描述"
                        result_parts.append(f"- **{cmd_name}**: {description}")
                else:
                    result_parts.append("\n## 可用的命令：无")

            if query_type in ["all", "tools"]:
                # 获取启用的工具
                enabled_tools = get_enabled_components_info_by_type(ComponentType.TOOL)
                if enabled_tools:
                    result_parts.append("\n## 可用的工具：")
                    for tool_name, tool_info in enabled_tools.items():
                        description = tool_info.tool_description or "无描述"
                        result_parts.append(f"- **{tool_name}**: {description}")
                else:
                    result_parts.append("\n## 可用的工具：无")

            result_text = "\n".join(result_parts)

            if not result_text.strip():
                result_text = "未找到任何已启用的功能。"

            logger.info(f"查询功能列表成功，类型: {query_type}")

            return {
                "content": result_text,
                "success": True,
            }

        except Exception as e:
            logger.error(f"查询功能列表失败: {e}", exc_info=True)
            return {
                "content": f"查询功能列表时发生错误: {str(e)}",
                "success": False,
            }








