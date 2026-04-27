"""
跨场景聊天查询插件
允许查询用户在其他场景（群聊/私聊）的聊天记录
"""

from typing import Any, Dict, List, Tuple, Type
from src.plugin_system import BasePlugin, BaseTool, ComponentInfo, register_plugin, ToolParamType
from src.common.logger import get_logger
from src.memory_system.retrieval_tools.query_cross_scene_chat import query_cross_scene_chat

logger = get_logger("cross_scene_chat_plugin")


class CrossSceneChatTool(BaseTool):
    """跨场景聊天查询工具 - 供LLM在回复时直接调用"""

    name = "query_cross_scene_chat"
    description = """【跨场景查询】查询用户在其他场景的聊天记录（不包括当前聊天）。

使用时机：
- 用户问"你还记得我们在私聊/群里聊过什么吗"
- 用户问"我之前在XX群和你说过什么"
- 用户说"查看/调用私聊工具"、"看看聊天记录"
- 用户要求查看与某人在其他地方的对话

功能：查询该用户在其他群聊或私聊中的历史对话，自动排除当前聊天。"""

    parameters: List[Tuple[str, ToolParamType, str, bool, None]] = [
        ("user_name", ToolParamType.STRING, "用户名称（昵称或person_name）", True, None),
        ("scene_type", ToolParamType.STRING, "场景类型：'private'(私聊)、'group'(群聊)、留空(所有场景)", False, None),
        ("keyword", ToolParamType.STRING, "关键词过滤（可选）", False, None),
        ("time_range_days", ToolParamType.INTEGER, "查询时间范围（天数），默认30天", False, None),
        ("limit", ToolParamType.INTEGER, "返回的最大消息数，默认20条", False, None),
    ]

    available_for_llm = True

    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行跨场景查询"""
        try:
            # 获取参数
            user_name = function_args.get("user_name", "")
            scene_type = function_args.get("scene_type")
            keyword = function_args.get("keyword")
            time_range_days = function_args.get("time_range_days", 30)
            limit = function_args.get("limit", 20)

            # 获取当前chat_id
            chat_id = self.chat_id
            if not chat_id:
                return {
                    "name": self.name,
                    "content": "无法获取当前聊天ID"
                }

            logger.info(f"跨场景查询: user_name={user_name}, scene_type={scene_type}, chat_id={chat_id}")

            # 调用查询函数
            result = await query_cross_scene_chat(
                user_name=user_name,
                scene_type=scene_type,
                keyword=keyword,
                time_range_days=time_range_days,
                limit=limit,
                chat_id=chat_id
            )

            return {
                "name": self.name,
                "content": result
            }

        except Exception as e:
            logger.error(f"跨场景查询失败: {e}", exc_info=True)
            return {
                "name": self.name,
                "content": f"查询失败: {str(e)}"
            }


@register_plugin
class CrossSceneChatPlugin(BasePlugin):
    """跨场景聊天查询插件"""

    plugin_name: str = "cross_scene_chat_plugin"
    plugin_version: str = "1.0.0"
    plugin_description: str = "允许查询用户在其他场景（群聊/私聊）的聊天记录"
    plugin_author: str = "MaiBot"

    enable_plugin: bool = True
    dependencies: List[str] = []
    python_dependencies: List = []
    config_file_name: str = "config.toml"
    config_schema: Dict[str, Any] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件提供的组件（Tool）"""
        return [
            (CrossSceneChatTool.get_tool_info(), CrossSceneChatTool),
        ]
