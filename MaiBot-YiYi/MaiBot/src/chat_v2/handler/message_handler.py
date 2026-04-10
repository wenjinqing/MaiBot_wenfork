"""
消息处理器：新架构的消息处理入口
"""

import asyncio
import time
from typing import Dict, Optional

from src.common.logger import get_logger
from src.config.config import global_config
from src.chat_v2.agent import UnifiedChatAgent
from src.chat_v2.models import ExecutionResult


class MessageHandler:
    """消息处理器"""

    def __init__(self):
        self.agents = {}  # chat_id -> UnifiedChatAgent
        self.logger = get_logger("message_handler_v2")
        self._v2_seen_message_at: Dict[str, float] = {}
        self._v2_message_id_locks: Dict[str, asyncio.Lock] = {}
        self._v2_chat_process_locks: Dict[str, asyncio.Lock] = {}

    def _dedup_key_for_inbound(self, message, chat_id: str) -> Optional[str]:
        try:
            mi = getattr(message, "message_info", None)
            if mi is None:
                return None
            mid = getattr(mi, "message_id", None)
            plat = getattr(mi, "platform", None) or ""
            if not mid or str(mid) == "notice":
                return None
            return f"{plat}:{chat_id}:{mid}"
        except Exception:
            return None

    def _lock_for_dedup_key(self, key: str) -> asyncio.Lock:
        if key not in self._v2_message_id_locks:
            self._v2_message_id_locks[key] = asyncio.Lock()
        return self._v2_message_id_locks[key]

    def _lock_for_chat(self, chat_id: str) -> asyncio.Lock:
        if chat_id not in self._v2_chat_process_locks:
            self._v2_chat_process_locks[chat_id] = asyncio.Lock()
        return self._v2_chat_process_locks[chat_id]

    def _prune_dedup_maps(self, now: float, ttl_sec: float) -> None:
        if len(self._v2_seen_message_at) < 1500:
            return
        cutoff = now - max(ttl_sec, 1.0) * 3
        old = [k for k, t in self._v2_seen_message_at.items() if t < cutoff]
        for k in old[:400]:
            self._v2_seen_message_at.pop(k, None)
            self._v2_message_id_locks.pop(k, None)

    async def handle_message(
        self,
        message,
        chat_stream
    ) -> Optional[str]:
        """
        处理消息

        Args:
            message: 消息对象 (MessageRecv / 带 message_info)
            chat_stream: 聊天流对象

        Returns:
            回复文本，如果不需要回复则返回 None
        """
        chat_id = chat_stream.stream_id
        serial = getattr(global_config.inner, "v2_serial_process_per_stream", True)

        async def _run() -> Optional[str]:
            dedup_key = self._dedup_key_for_inbound(message, chat_id)
            ttl_sec = float(
                getattr(global_config.inner, "v2_inbound_message_dedup_ttl_seconds", 180.0) or 0.0
            )

            if dedup_key is None or ttl_sec <= 0:
                result = await self._handle_message_once(message, chat_stream)
                return result.response if result.success else None

            lock = self._lock_for_dedup_key(dedup_key)
            async with lock:
                now = time.time()
                self._prune_dedup_maps(now, ttl_sec)
                last_ok = self._v2_seen_message_at.get(dedup_key)
                if last_ok is not None and (now - last_ok) < ttl_sec:
                    self.logger.warning(
                        f"跳过 chat_v2 重复入站: message_id 已在 {now - last_ok:.1f}s 内成功处理过 "
                        f"(dedup_key={dedup_key})，避免同一条消息触发两轮回复"
                    )
                    return None

                # 与同 dedup_key 并发时串行；在锁内跑完整 process，避免双通路的第二遍抢在「已处理」写入之前开始
                result = await self._handle_message_once(message, chat_stream)
                if result.success:
                    self._v2_seen_message_at[dedup_key] = time.time()
                return result.response if result.success else None

        if serial:
            async with self._lock_for_chat(chat_id):
                return await _run()
        return await _run()

    async def _handle_message_once(
        self,
        message,
        chat_stream,
    ) -> ExecutionResult:
        chat_id = chat_stream.stream_id

        try:
            if chat_id not in self.agents:
                self.logger.info(f"为聊天 {chat_id} 创建新的 Agent")
                self.agents[chat_id] = UnifiedChatAgent(chat_stream)

            agent = self.agents[chat_id]

            result: ExecutionResult = await agent.process(message)

            if result.success:
                self.logger.info(
                    f"消息处理成功 [chat={chat_id}] "
                    f"LLM调用={result.llm_calls}次 "
                    f"工具调用={result.tool_calls}次 "
                    f"耗时={result.total_time:.2f}s"
                )
            else:
                self.logger.error(f"消息处理失败 [chat={chat_id}]: {result.error}")
            return result

        except Exception as e:
            self.logger.error(f"消息处理异常 [chat={chat_id}]: {e}", exc_info=True)
            return ExecutionResult(success=False, error=str(e))

    def clear_agent(self, chat_id: str):
        """清除指定聊天的 Agent"""
        if chat_id in self.agents:
            del self.agents[chat_id]
            self.logger.info(f"已清除聊天 {chat_id} 的 Agent")

    def clear_all_agents(self):
        """清除所有 Agent"""
        count = len(self.agents)
        self.agents.clear()
        self.logger.info(f"已清除所有 Agent，共 {count} 个")


# 全局单例
_message_handler = None


def get_message_handler() -> MessageHandler:
    """获取全局消息处理器"""
    global _message_handler
    if _message_handler is None:
        _message_handler = MessageHandler()
    return _message_handler
