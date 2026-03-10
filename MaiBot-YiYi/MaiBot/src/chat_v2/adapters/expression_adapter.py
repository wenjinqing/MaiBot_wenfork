"""
表达学习和反思系统集成适配器

将旧架构的表达学习和反思系统集成到新架构的 UnifiedAgent 中
"""

from typing import Optional, List, Dict, Any
from src.common.logger import get_logger
from src.express.expression_learner import expression_learner_manager
from src.express.expression_selector import expression_selector
from src.express.expression_reflector import expression_reflector_manager

logger = get_logger("expression_adapter")


class ExpressionAdapter:
    """表达系统适配器"""

    def __init__(self, chat_id: str):
        """
        初始化表达适配器

        Args:
            chat_id: 聊天流 ID
        """
        self.chat_id = chat_id

        # 获取表达学习器
        self.learner = expression_learner_manager.get_expression_learner(chat_id)

        # 获取表达反思器
        self.reflector = expression_reflector_manager.get_or_create_reflector(chat_id)

    async def check_and_trigger_learning(self) -> bool:
        """
        检查并触发表达学习

        Returns:
            bool: 是否触发了学习
        """
        try:
            # 检查是否应该触发学习
            if not self.learner.should_trigger_learning():
                return False

            # 触发学习（异步）
            await self.learner.trigger_learning_for_chat()
            logger.info(f"表达学习已触发: chat_id={self.chat_id}")
            return True

        except Exception as e:
            logger.error(f"触发表达学习失败: {e}", exc_info=True)
            return False

    async def check_and_trigger_reflection(self) -> bool:
        """
        检查并触发表达反思

        Returns:
            bool: 是否触发���反思
        """
        try:
            # 检查并提问表达反思
            asked = await self.reflector.check_and_ask()

            if asked:
                logger.info(f"表达反思已触发: chat_id={self.chat_id}")

            return asked

        except Exception as e:
            logger.error(f"触发表达反思失败: {e}", exc_info=True)
            return False

    async def select_expressions(
        self,
        chat_info: str,
        max_num: int = 10,
        target_message: Optional[str] = None,
        reply_reason: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        选择适合的表达方式

        Args:
            chat_info: 聊天内容信息
            max_num: 最大��择数量
            target_message: 目标消息内容
            reply_reason: 回复理由

        Returns:
            List[Dict[str, Any]]: 选中的表达方式列表
        """
        try:
            # 调用表达选择器
            expressions, selected_ids = await expression_selector.select_suitable_expressions(
                chat_id=self.chat_id,
                chat_info=chat_info,
                max_num=max_num,
                target_message=target_message,
                reply_reason=reply_reason,
            )

            if expressions:
                logger.debug(
                    f"选择了 {len(expressions)} 个表达方式: "
                    f"chat_id={self.chat_id}, "
                    f"ids={selected_ids}"
                )

            return expressions

        except Exception as e:
            logger.error(f"选择表达方式失败: {e}", exc_info=True)
            return []

    def can_use_expression(self) -> bool:
        """
        检查是否可以使用表达

        Returns:
            bool: 是否可��使用表达
        """
        return expression_selector.can_use_expression_for_chat(self.chat_id)

    def format_expressions_for_prompt(self, expressions: List[Dict[str, Any]]) -> str:
        """
        将表达方式格式化为 prompt 文本

        Args:
            expressions: 表达方式列表

        Returns:
            str: 格式化后的文本
        """
        if not expressions:
            return ""

        lines = ["**可用的表达方式：**"]
        for i, expr in enumerate(expressions, 1):
            situation = expr.get("situation", "")
            style = expr.get("style", "")
            lines.append(f"{i}. 当「{situation}」时，使用「{style}」")

        lines.append("")
        lines.append("**使用建议：**")
        lines.append("- 根据当前聊天情境，选择最合适的表达方式")
        lines.append("- 可以灵活运用，不必完全照搬")
        lines.append("- 如果没有合适的，可以不使用")

        return "\n".join(lines)


class ExpressionAdapterManager:
    """表达适配器管理器"""

    def __init__(self):
        self.adapters: Dict[str, ExpressionAdapter] = {}

    def get_or_create_adapter(self, chat_id: str) -> ExpressionAdapter:
        """
        获取或创建表达适配器

        Args:
            chat_id: 聊天流 ID

        Returns:
            ExpressionAdapter: 表达适配器
        """
        if chat_id not in self.adapters:
            self.adapters[chat_id] = ExpressionAdapter(chat_id)
        return self.adapters[chat_id]


# 全局实例
expression_adapter_manager = ExpressionAdapterManager()
