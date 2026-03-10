"""
消息队列和并发控制
"""

import asyncio
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
from src.common.logger import get_logger

logger = get_logger("message_queue")


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 0  # 低优先级（普通消息）
    NORMAL = 1  # 正常优先级（@消息）
    HIGH = 2  # 高优先级（私聊消息）
    URGENT = 3  # 紧急优先级（管理员命令）


@dataclass
class QueuedMessage:
    """队列中的消息"""
    message: Any  # 消息对象
    priority: MessagePriority  # 优先级
    timestamp: float  # 入队时间
    retry_count: int = 0  # 重试次数


class MessageQueue:
    """消息队列（支持优先级）"""

    def __init__(self, maxsize: int = 100):
        """
        初始化消息队列

        Args:
            maxsize: 队列最大容量
        """
        self.maxsize = maxsize
        self._queues: Dict[MessagePriority, asyncio.Queue] = {
            priority: asyncio.Queue(maxsize=maxsize)
            for priority in MessagePriority
        }
        self._total_size = 0
        self._lock = asyncio.Lock()

    async def put(self, queued_message: QueuedMessage) -> bool:
        """
        将消息放入队列

        Args:
            queued_message: 队列消息

        Returns:
            bool: 是否成功放入
        """
        async with self._lock:
            if self._total_size >= self.maxsize:
                logger.warning(f"消息队列已满（{self._total_size}/{self.maxsize}），丢弃消息")
                return False

            queue = self._queues[queued_message.priority]
            try:
                await queue.put(queued_message)
                self._total_size += 1
                logger.debug(
                    f"消息入队: 优先级={queued_message.priority.name}, "
                    f"队列大小={self._total_size}/{self.maxsize}"
                )
                return True
            except asyncio.QueueFull:
                logger.warning(f"优先级 {queued_message.priority.name} 队列已满")
                return False

    async def get(self) -> Optional[QueuedMessage]:
        """
        从队列中获取消息（按优先级）

        Returns:
            Optional[QueuedMessage]: 队列消息，如果队列为空则返回 None
        """
        async with self._lock:
            # 按优先级从高到低获取
            for priority in sorted(MessagePriority, key=lambda p: p.value, reverse=True):
                queue = self._queues[priority]
                if not queue.empty():
                    queued_message = await queue.get()
                    self._total_size -= 1
                    logger.debug(
                        f"消息出队: 优先级={priority.name}, "
                        f"队列大小={self._total_size}/{self.maxsize}"
                    )
                    return queued_message

            return None

    def size(self) -> int:
        """获取队列总大小"""
        return self._total_size

    def is_empty(self) -> bool:
        """判断队列是否为空"""
        return self._total_size == 0

    def is_full(self) -> bool:
        """判断队列是否已满"""
        return self._total_size >= self.maxsize


class ConcurrencyController:
    """并发控制器"""

    def __init__(
        self,
        max_concurrent: int = 3,
        max_per_chat: int = 1,
        timeout: float = 60.0
    ):
        """
        初始化并发控制器

        Args:
            max_concurrent: 最大并发数（全局）
            max_per_chat: 每个聊天的最大并发数
            timeout: 任务超时时间（秒）
        """
        self.max_concurrent = max_concurrent
        self.max_per_chat = max_per_chat
        self.timeout = timeout

        # 全局信号量
        self._global_semaphore = asyncio.Semaphore(max_concurrent)

        # 每个聊天的信号量
        self._chat_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._chat_locks: Dict[str, asyncio.Lock] = {}

        # 正在处理的任务
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def _get_chat_semaphore(self, chat_id: str) -> asyncio.Semaphore:
        """获取聊天的信号量"""
        if chat_id not in self._chat_semaphores:
            self._chat_semaphores[chat_id] = asyncio.Semaphore(self.max_per_chat)
            self._chat_locks[chat_id] = asyncio.Lock()
        return self._chat_semaphores[chat_id]

    async def acquire(self, chat_id: str) -> bool:
        """
        获取执行权限

        Args:
            chat_id: 聊天 ID

        Returns:
            bool: 是否成功获取
        """
        try:
            # 先获取全局信号量
            await asyncio.wait_for(
                self._global_semaphore.acquire(),
                timeout=self.timeout
            )

            # 再获取聊天信号量
            chat_semaphore = self._get_chat_semaphore(chat_id)
            await asyncio.wait_for(
                chat_semaphore.acquire(),
                timeout=self.timeout
            )

            logger.debug(f"获取执行权限: chat_id={chat_id}")
            return True

        except asyncio.TimeoutError:
            logger.warning(f"获取执行权限超时: chat_id={chat_id}")
            return False

    def release(self, chat_id: str):
        """
        释放执行权限

        Args:
            chat_id: 聊天 ID
        """
        # 释放聊天信号量
        chat_semaphore = self._get_chat_semaphore(chat_id)
        chat_semaphore.release()

        # 释放全局信号量
        self._global_semaphore.release()

        logger.debug(f"释放执行权限: chat_id={chat_id}")

    async def execute_with_control(
        self,
        chat_id: str,
        task_id: str,
        coro: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        在并发控制下执行任务

        Args:
            chat_id: 聊天 ID
            task_id: 任务 ID
            coro: 协程函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            Any: 任务结果
        """
        # 获取执行权限
        if not await self.acquire(chat_id):
            raise Exception(f"无法获取执行权限: chat_id={chat_id}")

        try:
            # 创建任务
            task = asyncio.create_task(coro(*args, **kwargs))

            # 记录任务
            async with self._lock:
                self._active_tasks[task_id] = task

            # 等待任务完成（带超时）
            try:
                result = await asyncio.wait_for(task, timeout=self.timeout)
                return result
            except asyncio.TimeoutError:
                logger.error(f"任务超时: task_id={task_id}, chat_id={chat_id}")
                task.cancel()
                raise

        finally:
            # 清理任务
            async with self._lock:
                self._active_tasks.pop(task_id, None)

            # 释放执行权限
            self.release(chat_id)

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务 ID

        Returns:
            bool: 是否成功取消
        """
        async with self._lock:
            task = self._active_tasks.get(task_id)
            if task:
                task.cancel()
                logger.info(f"取消任务: task_id={task_id}")
                return True
            return False

    def get_active_count(self) -> int:
        """获取活跃任务数"""
        return len(self._active_tasks)

    def get_chat_active_count(self, chat_id: str) -> int:
        """获取指定聊天的活跃任务数"""
        count = 0
        for task_id in self._active_tasks:
            if chat_id in task_id:
                count += 1
        return count
