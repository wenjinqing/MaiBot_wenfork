"""
Action Planner 系统集成适配器

将旧架构的 Action Planner 系统集成到新架构中
注意：新架构已有 Function Calling 工具系统，Action Planner 作为可选增强功能
"""

from typing import Optional, List, Dict, Any
from src.common.logger import get_logger
from src.chat.planner_actions.planner import ActionPlanner
from src.chat.planner_actions.action_manager import ActionManager
from src.common.data_models.info_data_model import ActionPlannerInfo

logger = get_logger("planner_adapter")


class PlannerAdapter:
    """Action Planner 适配器"""

    def __init__(self, chat_id: str):
        """
        初始化 Planner 适配器

        Args:
            chat_id: 聊天流 ID
        """
        self.chat_id = chat_id

        # 创建 ActionManager
        self.action_manager = ActionManager()

        # 创建 ActionPlanner
        self.planner = ActionPlanner(chat_id=chat_id, action_manager=self.action_manager)

    async def plan_actions(
        self,
        is_mentioned: bool = False,
        loop_start_time: float = 0.0
    ) -> List[ActionPlannerInfo]:
        """
        规划动作

        Args:
            is_mentioned: 是否被提及
            loop_start_time: 循环开始时间

        Returns:
            List[ActionPlannerInfo]: 规划的动作列表
        """
        try:
            # 获取可用动作
            available_actions = self.action_manager.get_using_actions()

            # 调用 planner 进行规划
            actions = await self.planner.plan(
                available_actions=available_actions,
                loop_start_time=loop_start_time,
                is_mentioned=is_mentioned
            )

            if actions:
                logger.debug(
                    f"Planner 规划了 {len(actions)} 个动作: "
                    f"{[action.action_type for action in actions]}"
                )

            return actions

        except Exception as e:
            logger.error(f"规划动作失败: {e}", exc_info=True)
            return []

    def should_reply(self, actions: List[ActionPlannerInfo]) -> bool:
        """
        根据规划的动作判断是否应该回复

        Args:
            actions: 规划的动作列表

        Returns:
            bool: 是否应该回复
        """
        if not actions:
            return False

        # 检查是否有 reply 动作
        for action in actions:
            if action.action_type == "reply":
                return True

        return False

    def should_no_reply_until_call(self, actions: List[ActionPlannerInfo]) -> bool:
        """
        根据规划的动作判断是否应该进入沉默模式

        Args:
            actions: 规划的动作列表

        Returns:
            bool: 是否应该进入沉默模式
        """
        if not actions:
            return False

        # 检查是否有 no_reply_until_call 动作
        for action in actions:
            if action.action_type == "no_reply_until_call":
                return True

        return False

    def get_reply_reason(self, actions: List[ActionPlannerInfo]) -> Optional[str]:
        """
        获取回复理由

        Args:
            actions: 规划的动作列表

        Returns:
            Optional[str]: 回复理由
        """
        for action in actions:
            if action.action_type == "reply":
                return action.reasoning

        return None

    def get_target_message(self, actions: List[ActionPlannerInfo]) -> Optional[Any]:
        """
        获取目标消息

        Args:
            actions: 规划的动作列表

        Returns:
            Optional[Any]: 目标消息
        """
        for action in actions:
            if action.action_type == "reply" and action.action_message:
                return action.action_message

        return None

    def get_custom_actions(self, actions: List[ActionPlannerInfo]) -> List[ActionPlannerInfo]:
        """
        获取自定义动作（非 reply、no_reply、no_reply_until_call）

        Args:
            actions: 规划的动作列表

        Returns:
            List[ActionPlannerInfo]: 自定义动作列表
        """
        internal_actions = {"reply", "no_reply", "no_reply_until_call", "wait_time"}

        custom_actions = []
        for action in actions:
            if action.action_type not in internal_actions:
                custom_actions.append(action)

        return custom_actions

    async def execute_custom_actions(
        self,
        actions: List[ActionPlannerInfo],
        chat_stream: Any,
        thinking_id: str = "",
        cycle_timers: Optional[Dict] = None
    ) -> List[str]:
        """
        执行自定义动作

        Args:
            actions: 动作列表
            chat_stream: 聊天流
            thinking_id: 思考 ID
            cycle_timers: 计时器

        Returns:
            List[str]: 执行结果列表
        """
        results = []

        if cycle_timers is None:
            cycle_timers = {}

        for action in actions:
            try:
                # 创建动作实例
                action_instance = self.action_manager.create_action(
                    action_name=action.action_type,
                    action_data=action.action_data or {},
                    action_reasoning=action.reasoning,
                    cycle_timers=cycle_timers,
                    thinking_id=thinking_id,
                    chat_stream=chat_stream,
                    log_prefix=f"[{self.chat_id}]",
                    action_message=action.action_message
                )

                if action_instance:
                    # 执行动作
                    result = await action_instance.execute()
                    results.append(f"{action.action_type}: {result}")
                    logger.info(f"执行动作 {action.action_type} 成功: {result}")
                else:
                    logger.warning(f"无法创建动作实例: {action.action_type}")
                    results.append(f"{action.action_type}: 创建失败")

            except Exception as e:
                logger.error(f"执行动作 {action.action_type} 失败: {e}", exc_info=True)
                results.append(f"{action.action_type}: 执行失败 - {e}")

        return results

    def get_plan_log(self) -> str:
        """
        获取规划日志

        Returns:
            str: 规划日志
        """
        return self.planner.get_plan_log_str()

    def add_execution_log(self, result: str):
        """
        添加执行日志

        Args:
            result: 执行结果
        """
        self.planner.add_plan_excute_log(result)


class PlannerAdapterManager:
    """Planner 适配器管理器"""

    def __init__(self):
        self.adapters: Dict[str, PlannerAdapter] = {}

    def get_or_create_adapter(self, chat_id: str) -> PlannerAdapter:
        """
        获取或创建 Planner 适配器

        Args:
            chat_id: 聊天流 ID

        Returns:
            PlannerAdapter: Planner 适配器
        """
        if chat_id not in self.adapters:
            self.adapters[chat_id] = PlannerAdapter(chat_id)
        return self.adapters[chat_id]


# 全局实例
planner_adapter_manager = PlannerAdapterManager()
