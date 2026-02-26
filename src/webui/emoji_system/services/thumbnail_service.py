"""缩略图生成和管理服务"""
from pathlib import Path
from PIL import Image
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple
from src.common.logger import get_logger

logger = get_logger("webui.emoji.thumbnail")

# ==================== 缩略图缓存配置 ====================
# 缩略图缓存目录
THUMBNAIL_CACHE_DIR = Path("data/emoji_thumbnails")
# 缩略图尺寸 (宽, 高)
THUMBNAIL_SIZE = (200, 200)
# 缩略图质量 (WebP 格式, 1-100)
THUMBNAIL_QUALITY = 80


class ThumbnailService:
    """缩略图服务 - 线程安全的缩略图生成和管理"""

    def __init__(self):
        # 缓存锁，防止并发生成同一缩略图
        self._thumbnail_locks: dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()

        # 缩略图生成专用线程池（避免阻塞事件循环）
        self._thumbnail_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="thumbnail")

        # 正在生成中的缩略图哈希集合（防止重复提交任务）
        self._generating_thumbnails: set[str] = set()
        self._generating_lock = threading.Lock()

    def _get_thumbnail_lock(self, file_hash: str) -> threading.Lock:
        """获取指定文件哈希的锁，用于防止并发生成同一缩略图"""
        with self._locks_lock:
            if file_hash not in self._thumbnail_locks:
                self._thumbnail_locks[file_hash] = threading.Lock()
            return self._thumbnail_locks[file_hash]

    def _ensure_thumbnail_cache_dir(self) -> Path:
        """确保缩略图缓存目录存在"""
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return THUMBNAIL_CACHE_DIR

    def get_thumbnail_cache_path(self, file_hash: str) -> Path:
        """获取缩略图缓存路径"""
        return THUMBNAIL_CACHE_DIR / f"{file_hash}.webp"

    def generate_thumbnail(self, source_path: str, file_hash: str) -> Path:
        """
        生成缩略图并保存到缓存目录

        Args:
            source_path: 原图路径
            file_hash: 文件哈希值，用作缓存文件名

        Returns:
            缩略图路径

        Features:
            - GIF: 提取第一帧作为缩略图
            - 所有格式统一转为 WebP
            - 保持宽高比缩放
        """
        self._ensure_thumbnail_cache_dir()
        cache_path = self.get_thumbnail_cache_path(file_hash)

        # 使用锁防止并发生成同一缩略图
        lock = self._get_thumbnail_lock(file_hash)
        with lock:
            # 双重检查，可能在等待锁时已被其他线程生成
            if cache_path.exists():
                return cache_path

            try:
                with Image.open(source_path) as img:
                    # GIF 特殊处理：提取第一帧
                    if img.format == "GIF":
                        img.seek(0)
                        img = img.convert("RGBA")

                    # 转换为 RGB（WebP 不支持 RGBA 的某些模式）
                    if img.mode in ("RGBA", "LA", "P"):
                        # 创建白色背景
                        background = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode == "P":
                            img = img.convert("RGBA")
                        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                        img = background
                    elif img.mode != "RGB":
                        img = img.convert("RGB")

                    # 保持宽高比缩放
                    img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

                    # 保存为 WebP
                    img.save(cache_path, "WEBP", quality=THUMBNAIL_QUALITY, method=6)

                logger.debug(f"生成缩略图成功: {file_hash}")
                return cache_path

            except Exception as e:
                logger.error(f"生成缩略图失败 {file_hash}: {e}")
                raise

    def background_generate_thumbnail(self, source_path: str, file_hash: str) -> None:
        """
        后台生成缩略图（在线程池中执行）

        生成完成后自动从 generating 集合中移除
        """
        try:
            self.generate_thumbnail(source_path, file_hash)
        except Exception as e:
            logger.warning(f"后台生成缩略图失败 {file_hash}: {e}")
        finally:
            with self._generating_lock:
                self._generating_thumbnails.discard(file_hash)

    def submit_background_generation(self, source_path: str, file_hash: str) -> bool:
        """
        提交后台缩略图生成任务

        Returns:
            是否成功提交（False 表示已在生成中）
        """
        with self._generating_lock:
            if file_hash in self._generating_thumbnails:
                return False
            self._generating_thumbnails.add(file_hash)

        self._thumbnail_executor.submit(self.background_generate_thumbnail, source_path, file_hash)
        return True

    def is_generating(self, file_hash: str) -> bool:
        """检查是否正在生成缩略图"""
        with self._generating_lock:
            return file_hash in self._generating_thumbnails

    def cleanup_orphaned_thumbnails(self, valid_hashes: set[str]) -> Tuple[int, int]:
        """
        清理孤立的缩略图文件

        Args:
            valid_hashes: 有效的文件哈希集合

        Returns:
            (删除数量, 释放空间字节数)
        """
        if not THUMBNAIL_CACHE_DIR.exists():
            return 0, 0

        deleted_count = 0
        freed_bytes = 0

        for cache_file in THUMBNAIL_CACHE_DIR.glob("*.webp"):
            file_hash = cache_file.stem
            if file_hash not in valid_hashes:
                try:
                    file_size = cache_file.stat().st_size
                    cache_file.unlink()
                    deleted_count += 1
                    freed_bytes += file_size
                    logger.debug(f"删除孤立缩略图: {file_hash}")
                except Exception as e:
                    logger.warning(f"删除缩略图失败 {file_hash}: {e}")

        return deleted_count, freed_bytes

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        if not THUMBNAIL_CACHE_DIR.exists():
            return {
                "total_cached": 0,
                "total_size_mb": 0.0,
                "cache_dir": str(THUMBNAIL_CACHE_DIR),
            }

        total_cached = 0
        total_size = 0

        for cache_file in THUMBNAIL_CACHE_DIR.glob("*.webp"):
            total_cached += 1
            total_size += cache_file.stat().st_size

        return {
            "total_cached": total_cached,
            "total_size_mb": total_size / (1024 * 1024),
            "cache_dir": str(THUMBNAIL_CACHE_DIR),
        }

    def clear_all_cache(self) -> Tuple[int, int]:
        """
        清空所有缓存

        Returns:
            (删除数量, 释放空间字节数)
        """
        if not THUMBNAIL_CACHE_DIR.exists():
            return 0, 0

        deleted_count = 0
        freed_bytes = 0

        for cache_file in THUMBNAIL_CACHE_DIR.glob("*.webp"):
            try:
                file_size = cache_file.stat().st_size
                cache_file.unlink()
                deleted_count += 1
                freed_bytes += file_size
            except Exception as e:
                logger.warning(f"删除缓存文件失败 {cache_file}: {e}")

        return deleted_count, freed_bytes


# 全局单例
_thumbnail_service = ThumbnailService()


def get_thumbnail_service() -> ThumbnailService:
    """获取缩略图服务单例"""
    return _thumbnail_service
