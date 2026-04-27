"""
聊天类型选择插件
让大模型可以选择查看私聊或群聊的历史记忆
"""

from typing import List, Tuple, Type
from src.common.logger import get_logger
from src.plugin_system.base.base_plugin import BasePlugin
from src.plugin_system.apis.plugin_register_api import register_plugin
from src.plugin_system.base.base_action import BaseAction, ActionActivationType
from src.plugin_system.base.component_types import ComponentInfo, ChatMode
from src.plugin_system.base.config_types import ConfigField

logger = get_logger("chat_context_selector_plugin")


class ChatContextSelectorAction(BaseAction):
    """聊天上下文选择Action - 让大模型选择查看哪种类型的聊天记录"""

    action_name = "chat_context_selector_action"
    action_description = "选择查看私聊或群聊的历史记忆，用于区分不同场景的对话上下文"
    activation_type = ActionActivationType.LLM_JUDGE
    mode_enable = ChatMode.ALL
    parallel_action = False

    activation_keywords = ["私聊", "群聊", "单独", "群里", "私下", "一对一", "private", "group"]
    keyword_case_sensitive = False

    action_parameters = {
        "context_type": "上下文类型（必填）。private=查看私聊记录，group=查看群聊记录，all=查看所有记录",
        "reason": "选择原因（可选）。说明为什么选择这个上下文类型"
    }

    action_require = [
        "【适合使用的场景】",
        "1. 用户在群聊中提到私聊的内容（如：'我私下跟你说过'）",
        "2. 用户在私聊中提到群聊的内容（如：'我在群里说过'）",
        "3. 需要区分不同场景的对话上下文",
        "4. 用户明确要求查看特定类型的聊天记录",
        "",
        "【参数说明】",
        "1. context_type: 选择要查看的上下文类型",
        "   - private: 只查看私聊记录",
        "   - group: 只查看群聊记录",
        "   - all: 查看所有记录（默认）",
        "2. reason: 说明选择的原因，帮助理解上下文切换的意图",
        "",
        "【使用示例】",
        "1. 用户在群里说：'我私下跟你说过这件事'",
        "   → context_type='private', reason='用户提到私聊内容'",
        "2. 用户在私聊说：'我在群里说了什么？'",
        "   → context_type='group', reason='用户询问群聊内容'",
        "3. 用户说：'你还记得我们单独聊过的那件事吗？'",
        "   → context_type='private', reason='用户提到单独对话'",
        "",
        "【注意事项】",
        "1. 此Action主要用于设置上下文偏好，不直接返回聊天记录",
        "2. 后续的记忆检索会根据这个偏好筛选记录",
        "3. 如果不确定，使用 'all' 查看所有记录",
        "4. 这个Action会影响后续的对话理解和回复"
    ]

    associated_types = ["text"]

    async def execute(self) -> Tuple[bool, str]:
        """执行上下文选择"""
        try:
            context_type = self.action_data.get("context_type", "all").strip().lower()
            reason = self.action_data.get("reason", "").strip()

            if context_type not in ["private", "group", "all"]:
                await self.send_text(f"无效的上下文类型: {context_type}")
                return False, "无效的上下文类型"

            # 将上下文类型存储到会话中（可以用于后续的记忆检索）
            # 这里可以存储到 chat_stream 或其他地方
            # 暂时只记录日志

            context_type_cn = {
                "private": "私聊",
                "group": "群聊",
                "all": "所有"
            }.get(context_type, "所有")

            logger.info(f"{self.log_prefix} 切换上下文类型: {context_type_cn} - {reason}")

            # 存储到 action_info 中，供后续使用
            await self.store_action_info(
                action_build_into_prompt=True,
                action_prompt_display=f"切换到{context_type_cn}上下文{f'（{reason}）' if reason else ''}",
                action_done=True
            )

            # 不发送消息给用户，这是内部操作
            return True, f"已切换到{context_type_cn}上下文"

        except Exception as e:
            error_msg = str(e)
            logger.error(f"{self.log_prefix} 切换上下文失败: {error_msg}", exc_info=True)
            return False, error_msg


@register_plugin
class ChatContextSelectorPlugin(BasePlugin):
    """聊天上下文选择插件"""

    plugin_name = "chat_context_selector_plugin"
    plugin_description = "让大模型可以选择查看私聊或群聊的历史记忆"
    plugin_version = "1.0.0"
    plugin_author = "Assistant"
    enable_plugin = True
    config_file_name = "config.toml"
    dependencies = []
    python_dependencies = []

    config_section_descriptions = {
        "plugin": "插件基本配置",
        "components": "组件启用控制"
    }

    config_schema = {
        "plugin": {
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
            "config_version": ConfigField(type=str, default="1.0.0", description="配置文件版本")
        },
        "components": {
            "action_enabled": ConfigField(type=bool, default=True, description="是否启用Action组件")
        }
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件组件列表"""
        components = []

        try:
            action_enabled = self.get_config("components.action_enabled", True)
        except AttributeError:
            action_enabled = True

        if action_enabled:
            components.append((ChatContextSelectorAction.get_action_info(), ChatContextSelectorAction))

        return components
