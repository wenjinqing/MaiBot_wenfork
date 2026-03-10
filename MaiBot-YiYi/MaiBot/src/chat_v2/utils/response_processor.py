"""
消息后处理模块

负责处理 LLM 生成的原始回复，使用旧架构的 process_llm_response 逻辑
"""

from typing import List
from src.common.logger import get_logger
from src.chat.utils.utils import process_llm_response

logger = get_logger("response_processor")


class ResponseProcessor:
    """消息后处理器 - 直接使用旧架构的处理逻辑"""

    def __init__(self):
        pass

    async def process(
        self,
        raw_response: str,
        message: "MessageRecv",
        bot_config: dict,
    ) -> List[str]:
        """
        处理原始回复

        Args:
            raw_response: LLM 生成的原始回复
            message: 用户消息对象
            bot_config: 机器人配置

        Returns:
            List[str]: 处理后的回复列表
        """
        try:
            # 直接使用旧架构的 process_llm_response
            # 它会自动处理：
            # 1. 保护颜文字
            # 2. 去除括号内容（LLM 的旁白）
            # 3. 文字分割
            # 4. 错字生成（模拟人类打字）
            # 5. 恢复颜文字
            processed_responses = process_llm_response(
                text=raw_response,
                enable_splitter=True,
                enable_chinese_typo=True
            )

            logger.debug(f"消息后处理完成，原始: {raw_response[:50]}..., 处理后: {len(processed_responses)} 条")
            return processed_responses

        except Exception as e:
            logger.error(f"消息后处理失败: {e}")
            return [raw_response]  # 失败时返回���始回复
