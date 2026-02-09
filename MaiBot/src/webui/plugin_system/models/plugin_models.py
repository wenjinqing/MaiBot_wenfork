"""插件系统 Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class FetchRawFileRequest(BaseModel):
    """获取 Raw 文件请求"""

    owner: str = Field(..., description="仓库所有者", example="MaiM-with-u")
    repo: str = Field(..., description="仓库名称", example="plugin-repo")
    branch: str = Field(..., description="分支名称", example="main")
    file_path: str = Field(..., description="文件路径", example="plugin_details.json")
    mirror_id: Optional[str] = Field(None, description="指定镜像源 ID")
    custom_url: Optional[str] = Field(None, description="自定义完整 URL")


class FetchRawFileResponse(BaseModel):
    """获取 Raw 文件响应"""

    success: bool = Field(..., description="是否成功")
    data: Optional[str] = Field(None, description="文件内容")
    error: Optional[str] = Field(None, description="错误信息")
    mirror_used: Optional[str] = Field(None, description="使用的镜像源")
    attempts: int = Field(..., description="尝试次数")
    url: Optional[str] = Field(None, description="实际请求的 URL")


class CloneRepositoryRequest(BaseModel):
    """克隆仓库请求"""

    owner: str = Field(..., description="仓库所有者", example="MaiM-with-u")
    repo: str = Field(..., description="仓库名称", example="plugin-repo")
    target_path: str = Field(..., description="目标路径（相对于插件目录）")
    branch: Optional[str] = Field(None, description="分支名称", example="main")
    mirror_id: Optional[str] = Field(None, description="指定镜像源 ID")
    custom_url: Optional[str] = Field(None, description="自定义完整 URL")


class CloneRepositoryResponse(BaseModel):
    """克隆仓库响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    path: Optional[str] = Field(None, description="克隆路径")
    error: Optional[str] = Field(None, description="错误信息")
    mirror_used: Optional[str] = Field(None, description="使用的镜像源")


class MirrorConfigResponse(BaseModel):
    """镜像源配置响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    mirrors: Optional[List[Dict[str, Any]]] = Field(None, description="镜像源列表")


class AvailableMirrorsResponse(BaseModel):
    """可用镜像源响应"""

    mirrors: List[Dict[str, Any]] = Field(..., description="镜像源列表")


class AddMirrorRequest(BaseModel):
    """添加镜像源请求"""

    id: str = Field(..., description="镜像源 ID")
    name: str = Field(..., description="镜像源名称")
    base_url: str = Field(..., description="基础 URL")
    priority: int = Field(default=0, description="优先级")
    enabled: bool = Field(default=True, description="是否启用")


class UpdateMirrorRequest(BaseModel):
    """更新镜像源请求"""

    name: Optional[str] = Field(None, description="镜像源名称")
    base_url: Optional[str] = Field(None, description="基础 URL")
    priority: Optional[int] = Field(None, description="优先级")
    enabled: Optional[bool] = Field(None, description="是否启用")


class GitStatusResponse(BaseModel):
    """Git 状态响应"""

    git_available: bool = Field(..., description="Git 是否可用")
    git_version: Optional[str] = Field(None, description="Git 版本")


class InstallPluginRequest(BaseModel):
    """安装插件请求"""

    plugin_id: str = Field(..., description="插件 ID")
    version: Optional[str] = Field(None, description="版本")


class VersionResponse(BaseModel):
    """版本响应"""

    version: str = Field(..., description="版本号")


class UninstallPluginRequest(BaseModel):
    """卸载插件请求"""

    plugin_id: str = Field(..., description="插件 ID")


class UpdatePluginRequest(BaseModel):
    """更新插件请求"""

    plugin_id: str = Field(..., description="插件 ID")
    target_version: Optional[str] = Field(None, description="目标版本")
    force: bool = Field(default=False, description="是否强制更新")


class UpdatePluginConfigRequest(BaseModel):
    """更新插件配置请求"""

    config: Dict[str, Any] = Field(..., description="配置数据")
