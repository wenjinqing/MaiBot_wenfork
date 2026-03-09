"""
消息处理器：新架构的消息处理入口
"""

from typing import Optional
from src.common.logger import get_logger
from src.chat_v2.agent import UnifiedChatAgent
from src.chat_v2.models import ExecutionResult


class MessageHandler:
    """消息处理器"""

    def __init__(self):
        self.agents = {}  # chat_id -> UnifiedChatAgent
        self.logger = get_logger("message_handler_v2")

    async def handle_message(
        self,
        message,
        chat_stream
    ) -> Optional[str]:
        """
        处理消息

        Args:
            message: 消息对象 (DatabaseMessages)
            chat_stream: 聊天流对象

        Returns:
            回复文本，如果不需要回复则返回 None
        """
        chat_id = chat_stream.stream_id

        try:
            # 获取或创建 Agent
            if chat_id not in self.agents:
                self.logger.info(f"为聊天 {chat_id} 创建新的 Agent")
                self.agents[chat_id] = UnifiedChatAgent(chat_stream)

            agent = self.agents[chat_id]

            # 处理消息
            result: ExecutionResult = await agent.process(message)

            # 记录统计信息
            if result.success:
                self.logger.info(
                    f"消息处理成功 [chat={chat_id}] "
                    f"LLM调用={result.llm_calls}次 "
                    f"工具调用={result.tool_calls}次 "
                    f"耗时={result.total_time:.2f}s"
                )
                return result.response
            else:
                self.logger.error(f"消息处理失败 [chat={chat_id}]: {result.error}")
                return None

        except Exception as e:
            self.logger.error(f"消息处理异常 [chat={chat_id}]: {e}", exc_info=True)
            return None

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
