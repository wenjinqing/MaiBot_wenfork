"""
图片查看插件（从 music_plugin 拆分独立，故障隔离）

整合「看看腿」(image_module) 和 「JK / 白丝 / 黑丝」(body_part_module) 两类随机图片功能。
关键词 + 命令触发，走第三方图片 API。
"""

from typing import List, Tuple, Type
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
    ConfigField,
)
from src.common.logger import get_logger

from .modules.image_module import RandomImageAction, RandomImageCommand
from .modules.body_part_module import (
    JKImageAction,
    JKImageCommand,
    BaisiImageAction,
    HeisiImageAction,
)

logger = get_logger("image_viewer_plugin")


@register_plugin
class ImageViewerPlugin(BasePlugin):
    """图片查看插件（看看腿 + JK/白丝/黑丝）"""

    plugin_name = "image_viewer_plugin"
    plugin_description = "随机图片：看看腿、JK、白丝、黑丝（关键词+命令触发）"
    plugin_version = "1.0.0"
    plugin_author = "JunJun"
    enable_plugin = True
    config_file_name = "config.toml"
    dependencies = []
    python_dependencies = ["aiohttp"]

    config_section_descriptions = {
        "plugin": "插件基本配置",
        "image": "看看腿功能配置",
        "body_part": "JK/白丝/黑丝功能配置",
    }

    config_schema = {
        "plugin": {
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
            "name": ConfigField(type=str, default="image_viewer_plugin", description="插件名称"),
            "version": ConfigField(type=str, default="1.0.0", description="插件版本"),
        },
        "image": {
            "api_url": ConfigField(type=str, default="https://www.onexiaolaji.cn/RandomPicture/api/", description="图片API地址"),
            "api_key": ConfigField(type=str, default="qq249663924", description="API密钥"),
            "available_classes": ConfigField(type=list, default=[101, 102, 103, 104], description="可用的图片类型列表"),
        },
        "body_part": {
            "api_url": ConfigField(type=str, default="https://www.onexiaolaji.cn/RandomPicture/api/", description="美女图片API地址"),
            "api_key": ConfigField(type=str, default="qq249663924", description="API密钥"),
            "available_classes": ConfigField(type=list, default=[101, 102, 103, 104, 105, 106, 107, 108, 109, 111, 112, 11001, 11002, 11003], description="可用的图片类型列表"),
            "jk_classes": ConfigField(type=list, default=[101, 11001], description="已弃用：JK 现走 jk_api_url"),
            "jk_api_url": ConfigField(type=str, default="https://v2.xxapi.cn/api/jk?return=json", description="JK：xxapi return=json"),
            "baisi_api_url": ConfigField(type=str, default="https://v2.xxapi.cn/api/baisi?return=json", description="白丝：xxapi baisi"),
            "heisi_api_url": ConfigField(type=str, default="https://v2.xxapi.cn/api/heisi?return=json", description="黑丝：xxapi heisi"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回图片组件：看看腿 + JK/白丝/黑丝"""
        return [
            (RandomImageAction.get_action_info(), RandomImageAction),
            (RandomImageCommand.get_command_info(), RandomImageCommand),
            (JKImageAction.get_action_info(), JKImageAction),
            (JKImageCommand.get_command_info(), JKImageCommand),
            (BaisiImageAction.get_action_info(), BaisiImageAction),
            (HeisiImageAction.get_action_info(), HeisiImageAction),
        ]
