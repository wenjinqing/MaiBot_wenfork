import asyncio
import traceback
from typing import Any, Optional, Dict

from src.chat.message_receive.chat_stream import get_chat_manager
from src.common.logger import get_logger
from src.chat.heart_flow.heartFC_chat import HeartFChatting
from src.chat.brain_chat.brain_chat import BrainChatting
from src.chat.message_receive.chat_stream import ChatStream

logger = get_logger("heartflow")


class Heartflow:
    """主心流协调器，负责初始化并协调聊天"""

    def __init__(self):
        self.heartflow_chat_list: Dict[Any, HeartFChatting | BrainChatting] = {}

    async def get_or_create_heartflow_chat(self, chat_id: Any) -> Optional[HeartFChatting | BrainChatting]:
        """获取或创建一个新的HeartFChatting实例"""
        try:
            if chat := self.heartflow_chat_list.get(chat_id):
                return chat
            chat_stream: ChatStream | None = get_chat_manager().get_stream(chat_id)
            if not chat_stream:
                raise ValueError(f"未找到 chat_id={chat_id} 的聊天流")
            if chat_stream.group_info:
                new_chat = HeartFChatting(chat_id=chat_id)
            else:
                new_chat = BrainChatting(chat_id=chat_id)
            await new_chat.start()
            self.heartflow_chat_list[chat_id] = new_chat
            return new_chat
        except Exception as e:
            logger.error(f"创建心流聊天 {chat_id} 失败: {e}", exc_info=True)
            traceback.print_exc()
            return None

    async def stop_chat(self, chat_id: Any) -> None:
        """停止并清理指定聊天流的后台循环（切换 v2 架构时使用）"""
        chat = self.heartflow_chat_list.pop(chat_id, None)  # type: ignore
        if chat is None:
            return
        chat.running = False
        if chat._loop_task and not chat._loop_task.done():
            chat._loop_task.cancel()
            try:
                await chat._loop_task
            except asyncio.CancelledError:
                pass
        logger.info(f"已停止旧架构后台循环: {chat_id}")

    async def stop_all(self) -> None:
        """停止所有后台循环"""
        for chat_id in list(self.heartflow_chat_list.keys()):
            await self.stop_chat(chat_id)


heartflow = Heartflow()
