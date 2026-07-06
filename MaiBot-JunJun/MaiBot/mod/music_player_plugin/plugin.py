"""
音乐插件（从 music_plugin 拆分独立，故障隔离）

点歌功能：搜索、播放、选择。支持网易云 / QQ音乐 / VIP音质 / 聚合点歌。
依赖 utils/（api_client + image_generator，生成歌单图片）。
"""

from typing import List, Tuple, Type
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
    ConfigField,
)
from src.common.logger import get_logger

from .modules.music_module import (
    PlayMusicTool,
    MusicCommand,
    ChooseCommand,
    QuickChooseCommand,
)

logger = get_logger("music_player_plugin")


@register_plugin
class MusicPlayerPlugin(BasePlugin):
    """音乐点歌插件"""

    plugin_name = "music_player_plugin"
    plugin_description = "音乐点歌：网易云/QQ音乐/VIP/聚合，支持搜索与数字快捷选择"
    plugin_version = "1.0.0"
    plugin_author = "JunJun"
    enable_plugin = True
    config_file_name = "config.toml"
    dependencies = []
    python_dependencies = ["aiohttp", "Pillow"]

    config_section_descriptions = {
        "plugin": "插件基本配置",
        "music": "音乐功能配置",
    }

    config_schema = {
        "plugin": {
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
            "name": ConfigField(type=str, default="music_player_plugin", description="插件名称"),
            "version": ConfigField(type=str, default="1.0.0", description="插件版本"),
        },
        "music": {
            "api_url": ConfigField(type=str, default="https://api.vkeys.cn", description="音乐API基础URL(普通音源)"),
            "vip_api_url": ConfigField(type=str, default="https://www.littleyouzi.com/api/v2", description="VIP音乐API基础URL"),
            "juhe_api_url": ConfigField(type=str, default="https://api.xcvts.cn/api/music/juhe", description="聚合点歌API地址"),
            "default_source": ConfigField(type=str, default="netease", description="默认音乐源(netease/qq/netease_vip/qq_vip/juhe)"),
            "timeout": ConfigField(type=int, default=10, description="API请求超时时间(秒)"),
            "max_search_results": ConfigField(type=int, default=10, description="最大搜索结果数"),
            "show_cover": ConfigField(type=bool, default=True, description="是否显示专辑封面"),
            "show_info_text": ConfigField(type=bool, default=True, description="是否显示音乐信息文本"),
            "send_as_voice": ConfigField(type=bool, default=False, description="是否以语音消息发送音乐"),
            "enable_quick_choose": ConfigField(type=bool, default=True, description="是否启用数字快捷选择(直接输入1-10选歌)"),
            "quick_choose_timeout": ConfigField(type=int, default=60, description="快捷选择有效期(秒)"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回音乐组件：点歌 Tool + /music、/choose、数字快捷选择命令"""
        try:
            from .modules.music_module import start_cache_cleanup
            start_cache_cleanup()
        except Exception as e:
            logger.warning(f"启动音乐缓存清理任务失败: {e}")

        return [
            (PlayMusicTool.get_tool_info(), PlayMusicTool),
            (MusicCommand.get_command_info(), MusicCommand),
            (ChooseCommand.get_command_info(), ChooseCommand),
            (QuickChooseCommand.get_command_info(), QuickChooseCommand),
        ]
