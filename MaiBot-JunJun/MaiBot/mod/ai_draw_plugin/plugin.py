"""
AI绘图插件（从 music_plugin 拆分独立，故障隔离）

提供 AI 文生图功能（ModelScope）：
- AIDrawAction：planner 可见，LLM 决策轮可直接选「画图」
- AIDrawCommand：/draw、/绘图、/画图 命令
- AIDrawTool：LLM tool-call 通道（备用）
均共用 prompt 扩写 + 四级模型路由 + ModelScope 生图。
"""

from typing import List, Tuple, Type
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
    ConfigField,
)
from src.common.logger import get_logger

from .modules.ai_draw_module import AIDrawCommand, AIDrawAction
from .modules.auto_image_tool import AIDrawTool

logger = get_logger("ai_draw_plugin")


@register_plugin
class AIDrawPlugin(BasePlugin):
    """AI绘图插件"""

    plugin_name = "ai_draw_plugin"
    plugin_description = "AI 文生图（ModelScope），支持 /draw 命令、自然语言画图、prompt 扩写"
    plugin_version = "1.0.0"
    plugin_author = "JunJun"
    enable_plugin = True
    config_file_name = "config.toml"
    dependencies = []
    python_dependencies = ["aiohttp"]

    config_section_descriptions = {
        "plugin": "插件基本配置",
        "ai_draw": "AI绘图配置（ModelScope 文生图）",
    }

    config_schema = {
        "plugin": {
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
            "name": ConfigField(type=str, default="ai_draw_plugin", description="插件名称"),
            "version": ConfigField(type=str, default="1.0.0", description="插件版本"),
        },
        "ai_draw": {
            "api_key": ConfigField(type=str, default="", description="ModelScope Token（文生图用）"),
            "image_model": ConfigField(type=str, default="Tongyi-MAI/Z-Image-Turbo", description="默认生图模型 ID（普通内容）"),
            "image_model_nsfw": ConfigField(type=str, default="", description="软色情内容路由到的微调模型 ID（留空则不启用）"),
            "image_model_anime": ConfigField(type=str, default="", description="二次元/动漫角色路由到的特化模型 ID（留空则不启用）"),
            "poll_interval": ConfigField(type=float, default=1.0, description="轮询任务间隔(秒)，越小出图越快，建议 1"),
            "default_prompt": ConfigField(type=str, default="jk", description="默认描述词(当用户未提供时使用)"),
            "timeout": ConfigField(type=int, default=60, description="API请求超时时间(秒)"),
            "selection_mode": ConfigField(type=str, default="best", description="图片选择模式(best=智能最佳匹配, random=随机选择, all=发送全部)"),
            "self_prompt": ConfigField(type=str, default="猫娘 猫耳 白发 日系二次元 插画风格 少女 可爱 萌", description="人设描述词(画\"你自己\"时使用)"),
            "auto_image_enabled": ConfigField(type=bool, default=True, description="是否启用自动配图检测"),
            "prompt_expand_enabled": ConfigField(type=bool, default=True, description="是否启用 prompt 扩写（LLM 把简短描述扩写成高质量生图提示词）"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回 AI绘图组件：Action（planner 可见）+ Command（/draw）+ Tool（LLM 调用）"""
        # 启动图片缓存清理任务（换风格/下一张用）
        try:
            from .modules.ai_draw_module import start_image_cache_cleanup
            start_image_cache_cleanup()
        except Exception as e:
            logger.warning(f"启动图片缓存清理任务失败: {e}")

        return [
            (AIDrawAction.get_action_info(), AIDrawAction),
            (AIDrawCommand.get_command_info(), AIDrawCommand),
            (AIDrawTool.get_tool_info(), AIDrawTool),
        ]
