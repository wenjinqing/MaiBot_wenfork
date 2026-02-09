"""插件系统模块 - 向后兼容的导入接口"""

# 导入模型
from .models.plugin_models import (
    FetchRawFileRequest,
    FetchRawFileResponse,
    CloneRepositoryRequest,
    CloneRepositoryResponse,
    MirrorConfigResponse,
    AvailableMirrorsResponse,
    AddMirrorRequest,
    UpdateMirrorRequest,
    GitStatusResponse,
    InstallPluginRequest,
    VersionResponse,
    UninstallPluginRequest,
    UpdatePluginRequest,
    UpdatePluginConfigRequest,
)

# 导入工具函数
from .utils.helpers import (
    get_token_from_cookie_or_header,
    parse_version,
)

__all__ = [
    # 模型
    "FetchRawFileRequest",
    "FetchRawFileResponse",
    "CloneRepositoryRequest",
    "CloneRepositoryResponse",
    "MirrorConfigResponse",
    "AvailableMirrorsResponse",
    "AddMirrorRequest",
    "UpdateMirrorRequest",
    "GitStatusResponse",
    "InstallPluginRequest",
    "VersionResponse",
    "UninstallPluginRequest",
    "UpdatePluginRequest",
    "UpdatePluginConfigRequest",
    # 工具函数
    "get_token_from_cookie_or_header",
    "parse_version",
]
