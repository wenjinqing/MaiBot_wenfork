"""
消息处理器（集成队列和并发控制）
"""

import asyncio
import time
from typing import Optional, Callable, Any
from src.common.logger import get_logger
from src.chat_v2.utils.message_queue import (
    MessageQueue,
    QueuedMessage,
    MessagePriority,
    ConcurrencyController
)

logger = get_logger("message_processor")


class MessageProcessor:
    """消息处理器"""

    def __init__(
        self,
        handler: Callable,
        max_queue_size: int = 100,
        max_concurrent: int = 3,
        max_per_chat: int = 1,
        task_timeout: float = 60.0
    ):
        """
        初始化消息处理器

        Args:
            handler: 消息处理函数（async）
            max_queue_size: 队列最大容量
            max_concurrent: 最大并发数
            max_per_chat: 每个聊天的最大并发数
            task_timeout: 任务超时时间
        """
        self.handler = handler
        self.queue = MessageQueue(maxsize=max_queue_size)
        self.concurrency = ConcurrencyController(
            max_concurrent=max_concurrent,
            max_per_chat=max_per_chat,
            timeout=task_timeout
        )

        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

        # 统计信息
        self.stats = {
            "total_received": 0,
            "total_processed": 0,
            "total_failed": 0,
            "total_dropped": 0,
        }

    async def start(self):
        """启动消息处理器"""
        if self._running:
            logger.warning("消息处理器已经在运行")
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("消息处理器已启动")

    async def stop(self):
        """停止消息处理器"""
        if not self._running:
            return

        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        logger.info("消息处理器已停止")

    async def submit(
        self,
        message: Any,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> bool:
        """
        提交消息到队列

        Args:
            message: 消息对象
            priority: 优先级

        Returns:
            bool: 是否成功提交
        """
        self.stats["total_received"] += 1

        queued_message = QueuedMessage(
            message=message,
            priority=priority,
            timestamp=time.time()
        )

        success = await self.queue.put(queued_message)

        if not success:
            self.stats["total_dropped"] += 1
            logger.warning(f"消息被丢弃: message_id={getattr(message, 'message_id', 'unknown')}")

        return success

    async def _worker(self):
        """工作线程：从队列中取消息并处理"""
        logger.info("消息处理工作线程已启动")

        while self._running:
            try:
                # 从队列获取消息
                queued_message = await self.queue.get()

                if queued_message is None:
                    # 队列为空，等待一下
                    await asyncio.sleep(0.1)
                    continue

                # 处理消息
                await self._process_message(queued_message)

            except asyncio.CancelledError:
                logger.info("消���处理工作线程被取消")
                break
            except Exception as e:
                logger.error(f"消息处理工作线程异常: {e}", exc_info=True)
                await asyncio.sleep(1)  # 出错后等待一下

        logger.info("消息处理工作线程已停止")

    async def _process_message(self, queued_message: QueuedMessage):
        """
        处理单个消息

        Args:
            queued_message: 队列消息
        """
        message = queued_message.message
        message_id = getattr(message, 'message_id', 'unknown')
        chat_id = getattr(message, 'chat_id', 'unknown')

        try:
            # 计算等待时间
            wait_time = time.time() - queued_message.timestamp

            logger.info(
                f"开始处理消息: message_id={message_id}, "
                f"priority={queued_message.priority.name}, "
                f"wait_time={wait_time:.2f}s, "
                f"retry_count={queued_message.retry_count}"
            )

            # 在并发控制下执行处理
            task_id = f"{chat_id}_{message_id}"
            result = await self.concurrency.execute_with_control(
                chat_id=chat_id,
                task_id=task_id,
                coro=self.handler,
                message
            )

            # 检查处理结果
            if result and getattr(result, 'success', False):
                self.stats["total_processed"] += 1
                logger.info(f"消息处理成功: message_id={message_id}")
            else:
                # 处理失败，考虑重试
                await self._handle_failure(queued_message)

        except asyncio.TimeoutError:
            logger.error(f"消息处理超时: message_id={message_id}")
            await self._handle_failure(queued_message)

        except Exception as e:
            logger.error(f"消息处理异常: message_id={message_id}, error={e}", exc_info=True)
            await self._handle_failure(queued_message)

    async def _handle_failure(self, queued_message: QueuedMessage, max_retries: int = 2):
        """
        处理失败的消息

        Args:
            queued_message: 队列消息
            max_retries: 最大重试次数
        """
        message_id = getattr(queued_message.message, 'message_id', 'unknown')

        if queued_message.retry_count < max_retries:
            # 重试
            queued_message.retry_count += 1
            queued_message.timestamp = time.time()

            logger.info(
                f"消息将重试: message_id={message_id}, "
                f"retry_count={queued_message.retry_count}/{max_retries}"
            )

            # 重新放入队列（降低优先级）
            if queued_message.priority.value > MessagePriority.LOW.value:
                queued_message.priority = MessagePriority(queued_message.priority.value - 1)

            await self.queue.put(queued_message)
        else:
            # 超过最大重试次数，放弃
            self.stats["total_failed"] += 1
            logger.error(
                f"消息处理失败，已放弃: message_id={message_id}, "
                f"retry_count={queued_message.retry_count}"
            )

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self.stats,
            "queue_size": self.queue.size(),
            "active_tasks": self.concurrency.get_active_count(),
        }

    def get_status(self) -> str:
        """获取状态字符串"""
        stats = self.get_stats()
        return (
            f"消息处理器状态: "
            f"运行={self._running}, "
            f"队列={stats['queue_size']}, "
            f"活跃任务={stats['active_tasks']}, "
            f"已接收={stats['total_received']}, "
            f"已处理={stats['total_processed']}, "
            f"失败={stats['total_failed']}, "
            f"丢弃={stats['total_dropped']}"
        )
