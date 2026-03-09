"""
LRU 缓存工具
"""

import time
from typing import Any, Optional, Dict
from collections import OrderedDict
from src.common.logger import get_logger

logger = get_logger("cache")


class LRUCache:
    """LRU 缓存实现"""

    def __init__(self, max_size: int = 100, ttl: float = 300.0):
        """
        初始化 LRU 缓存

        Args:
            max_size: 最大缓存条目数
            ttl: 缓存过期时间（秒），默认 5 分钟
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期则返回 None
        """
        if key not in self.cache:
            self.misses += 1
            return None

        value, timestamp = self.cache[key]

        # 检查是否过期
        if time.time() - timestamp > self.ttl:
            del self.cache[key]
            self.misses += 1
            return None

        # 移动到末尾（最近使用）
        self.cache.move_to_end(key)
        self.hits += 1
        return value

    def set(self, key: str, value: Any) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
        """
        # 如果已存在，先删除
        if key in self.cache:
            del self.cache[key]

        # 添加新值
        self.cache[key] = (value, time.time())

        # 如果超过最大大小，删除最旧的
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def delete(self, key: str) -> bool:
        """
        删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "ttl": self.ttl,
        }

    def cleanup_expired(self) -> int:
        """
        清理过期的缓存条目

        Returns:
            清理的条目数
        """
        current_time = time.time()
        expired_keys = []

        for key, (value, timestamp) in self.cache.items():
            if current_time - timestamp > self.ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.debug(f"清理了 {len(expired_keys)} 个过期缓存条目")

        return len(expired_keys)


class CacheManager:
    """缓存管理器，管理多个缓存实例"""

    def __init__(self):
        self.caches: Dict[str, LRUCache] = {}

    def get_cache(self, name: str, max_size: int = 100, ttl: float = 300.0) -> LRUCache:
        """
        获取或创建缓存实例

        Args:
            name: 缓存名称
            max_size: 最大缓存条目数
            ttl: 缓存过期时间（秒）

        Returns:
            LRU 缓存实例
        """
        if name not in self.caches:
            self.caches[name] = LRUCache(max_size=max_size, ttl=ttl)
            logger.info(f"创建缓存: {name} (max_size={max_size}, ttl={ttl}s)")

        return self.caches[name]

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有缓存的统计信息

        Returns:
            所有缓存的统计信息
        """
        return {name: cache.get_stats() for name, cache in self.caches.items()}

    def cleanup_all_expired(self) -> int:
        """
        清理所有缓存的过期条目

        Returns:
            总共清理的条目数
        """
        total_cleaned = 0
        for cache in self.caches.values():
            total_cleaned += cache.cleanup_expired()
        return total_cleaned

    def clear_all(self) -> None:
        """清空所有缓存"""
        for cache in self.caches.values():
            cache.clear()
        logger.info("已清空所有缓存")


# 全局缓存管理器
cache_manager = CacheManager()
