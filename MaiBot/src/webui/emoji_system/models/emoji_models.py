"""表情包系统 Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import Optional, List


class EmojiResponse(BaseModel):
    """表情包响应模型"""

    id: int = Field(..., description="表情包 ID")
    full_path: str = Field(..., description="完整路径")
    format: str = Field(..., description="图片格式")
    emoji_hash: str = Field(..., description="哈希值")
    description: str = Field(..., description="描述")
    query_count: int = Field(..., description="查询次数")
    is_registered: bool = Field(..., description="是否已注册")
    is_banned: bool = Field(..., description="是否被禁止")
    emotion: Optional[str] = Field(None, description="情感标签")
    record_time: float = Field(..., description="记录时间")
    register_time: Optional[float] = Field(None, description="注册时间")
    usage_count: int = Field(..., description="使用次数")
    last_used_time: Optional[float] = Field(None, description="最后使用时间")


class EmojiListResponse(BaseModel):
    """表情包列表响应"""

    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    emojis: List[EmojiResponse] = Field(..., description="表情包列表")


class EmojiDetailResponse(BaseModel):
    """表情包详情响应"""

    emoji: EmojiResponse = Field(..., description="表情包信息")


class EmojiUpdateRequest(BaseModel):
    """表情包更新请求"""

    description: Optional[str] = Field(None, description="描述")
    emotion: Optional[str] = Field(None, description="情感标签")
    is_registered: Optional[bool] = Field(None, description="是否注册")
    is_banned: Optional[bool] = Field(None, description="是否禁止")


class EmojiUpdateResponse(BaseModel):
    """表情包更新响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    emoji: Optional[EmojiResponse] = Field(None, description="更新后的表情包")


class EmojiDeleteResponse(BaseModel):
    """表情包删除响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""

    emoji_ids: List[int] = Field(..., description="表情包 ID 列表")


class BatchDeleteResponse(BaseModel):
    """批量删除响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    deleted_count: int = Field(..., description="删除数量")
    failed_count: int = Field(..., description="失败数量")


class EmojiUploadResponse(BaseModel):
    """表情包上传响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    emoji: Optional[EmojiResponse] = Field(None, description="上传的表情包")


class ThumbnailCacheStatsResponse(BaseModel):
    """缩略图缓存统计响应"""

    total_cached: int = Field(..., description="缓存总数")
    total_size_mb: float = Field(..., description="总大小(MB)")
    cache_dir: str = Field(..., description="缓存目录")
    orphaned_count: int = Field(..., description="孤立文件数")


class ThumbnailCleanupResponse(BaseModel):
    """缩略图清理响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    deleted_count: int = Field(..., description="删除数量")
    freed_size_mb: float = Field(..., description="释放空间(MB)")


class ThumbnailPreheatResponse(BaseModel):
    """缩略图预热响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    total_count: int = Field(..., description="总数")
    generated_count: int = Field(..., description="生成数量")
    skipped_count: int = Field(..., description="跳过数量")
