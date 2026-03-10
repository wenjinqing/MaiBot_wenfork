"""
持续运行的聊天循环系统

支持主动发言、定时任务、持续观察等功能
"""

import asyncio
import time
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime, timedelta
from src.common.logger import get_logger
from src.chat_v2.adapters.planner_adapter import planner_adapter_manager

logger = get_logger("chat_loop")


class ScheduledTask:
    """定时任务"""

    def __init__(
        self,
        name: str,
        callback: Callable,
        interval: Optional[int] = None,
        cron_hour: Optional[int] = None,
        cron_minute: Optional[int] = None,
        enabled: bool = True
    ):
        """
        初始化定时任务

        Args:
            name: 任务名称
            callback: 回调函数
            interval: 间隔时间（秒），如果设置则按间隔执行
            cron_hour: 定时小时（0-23），如果设置则按时间执行
            cron_minute: 定时分钟（0-59）
            enabled: 是否启用
        """
        self.name = name
        self.callback = callback
        self.interval = interval
        self.cron_hour = cron_hour
        self.cron_minute = cron_minute
        self.enabled = enabled
        self.last_run_time = 0.0
        self.last_run_date: Optional[str] = None

    async def should_run(self) -> bool:
        """判断是否应该运行"""
        if not self.enabled:
            return False

        now = time.time()

        # 间隔执行
        if self.interval:
            if now - self.last_run_time >= self.interval:
                return True

        # 定时执行
        if self.cron_hour is not None:
            current_time = datetime.now()
            current_date = current_time.strftime("%Y-%m-%d")

            # 检查是否已经在今天执行过
            if self.last_run_date == current_date:
                return False

            # 检查是否到了执行时间
            target_hour = self.cron_hour
            target_minute = self.cron_minute or 0

            if current_time.hour == target_hour and current_time.minute == target_minute:
                return True

        return False

    async def run(self):
        """执行任务"""
        try:
            logger.info(f"执行定时任务: {self.name}")
            await self.callback()
            self.last_run_time = time.time()

            # 如果是定时任���，记录执行日期
            if self.cron_hour is not None:
                self.last_run_date = datetime.now().strftime("%Y-%m-%d")

            logger.info(f"定时任务执行成功: {self.name}")

        except Exception as e:
            logger.error(f"定时任务执行失败 {self.name}: {e}", exc_info=True)


class ChatLoop:
    """聊天循环"""

    def __init__(
        self,
        chat_id: str,
        agent: Any,
        chat_stream: Any,
        loop_interval: float = 5.0,
        enable_proactive_speak: bool = True,
        enable_scheduled_tasks: bool = True,
        enable_observation: bool = True
    ):
        """
        初始化聊天循环

        Args:
            chat_id: 聊天 ID
            agent: UnifiedAgent 实例
            chat_stream: ChatStream 实例
            loop_interval: 循环间隔（秒）
            enable_proactive_speak: 是否启用主动发言
            enable_scheduled_tasks: 是否启用定时任务
            enable_observation: 是否启用持续观察
        """
        self.chat_id = chat_id
        self.agent = agent
        self.chat_stream = chat_stream
        self.loop_interval = loop_interval
        self.enable_proactive_speak = enable_proactive_speak
        self.enable_scheduled_tasks = enable_scheduled_tasks
        self.enable_observation = enable_observation

        self.running = False
        self.loop_task: Optional[asyncio.Task] = None

        # 定时任务列表
        self.scheduled_tasks: List[ScheduledTask] = []

        # Planner 适配器
        self.planner_adapter = planner_adapter_manager.get_or_create_adapter(chat_id)

        # 状态追踪
        self.last_message_time = time.time()
        self.last_proactive_speak_time = 0.0
        self.observation_data: Dict[str, Any] = {}

        logger.info(f"[{chat_id}] 聊天循环已初始化")

    def add_scheduled_task(self, task: ScheduledTask):
        """
        添加定时任务

        Args:
            task: 定时任务
        """
        self.scheduled_tasks.append(task)
        logger.info(f"[{self.chat_id}] 添加定时任务: {task.name}")

    def remove_scheduled_task(self, task_name: str):
        """
        移除定时任务

        Args:
            task_name: 任务名称
        """
        self.scheduled_tasks = [t for t in self.scheduled_tasks if t.name != task_name]
        logger.info(f"[{self.chat_id}] 移除定时任务: {task_name}")

    async def start(self):
        """启动聊天循环"""
        if self.running:
            logger.warning(f"[{self.chat_id}] 聊天循环已经在运行")
            return

        self.running = True
        self.loop_task = asyncio.create_task(self._loop())
        logger.info(f"[{self.chat_id}] 聊天循环已启动")

    async def stop(self):
        """停止聊天循环"""
        if not self.running:
            return

        self.running = False

        if self.loop_task:
            self.loop_task.cancel()
            try:
                await self.loop_task
            except asyncio.CancelledError:
                pass

        logger.info(f"[{self.chat_id}] 聊天循环已停止")

    async def _loop(self):
        """主循环"""
        logger.info(f"[{self.chat_id}] 进入聊天循环")

        while self.running:
            try:
                loop_start_time = time.time()

                # 1. 执行定时任务
                if self.enable_scheduled_tasks:
                    await self._check_scheduled_tasks()

                # 2. 持续观察
                if self.enable_observation:
                    await self._observe()

                # 3. 检查是否需要主动发言
                if self.enable_proactive_speak:
                    await self._check_proactive_speak()

                # 4. 等待
                elapsed = time.time() - loop_start_time
                sleep_time = max(0, self.loop_interval - elapsed)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                logger.info(f"[{self.chat_id}] 聊天循环被取消")
                break
            except Exception as e:
                logger.error(f"[{self.chat_id}] 聊天循环出错: {e}", exc_info=True)
                await asyncio.sleep(self.loop_interval)

    async def _check_scheduled_tasks(self):
        """检查并执行定时任务"""
        for task in self.scheduled_tasks:
            try:
                if await task.should_run():
                    await task.run()
            except Exception as e:
                logger.error(f"[{self.chat_id}] 检查定时任务失败 {task.name}: {e}", exc_info=True)

    async def _observe(self):
        """持续观察聊天状态"""
        try:
            # 更新最后消息时间
            # 这里可以从数据库获取最新消息时间
            # self.last_message_time = get_last_message_time()

            # 收集观察数据
            self.observation_data["last_check_time"] = time.time()
            self.observation_data["idle_time"] = time.time() - self.last_message_time

        except Exception as e:
            logger.error(f"[{self.chat_id}] 观察失败: {e}", exc_info=True)

    async def _check_proactive_speak(self):
        """检查是否需要主动发言"""
        try:
            # 使用 Planner 判断是否需要主动发言
            actions = await self.planner_adapter.plan_actions(
                is_mentioned=False,
                loop_start_time=time.time()
            )

            # 检查是否有主动发言的动作
            for action in actions:
                if action.action_type == "proactive_speak":
                    await self._proactive_speak(action.reasoning)
                    break

        except Exception as e:
            logger.error(f"[{self.chat_id}] 检查主动发言失败: {e}", exc_info=True)

    async def _proactive_speak(self, reason: str):
        """
        主动发言

        Args:
            reason: 发言理由
        """
        try:
            # 检查冷却时间（避免频繁主动发言）
            min_interval = 3600  # 1小时
            if time.time() - self.last_proactive_speak_time < min_interval:
                logger.debug(f"[{self.chat_id}] 主动发言冷却中")
                return

            logger.info(f"[{self.chat_id}] 主动发言: {reason}")

            # 这里可以调用 agent 生成主动发言内容
            # content = await self.agent.generate_proactive_content(reason)
            # await self.chat_stream.send_message(content)

            self.last_proactive_speak_time = time.time()

        except Exception as e:
            logger.error(f"[{self.chat_id}] 主动发言失败: {e}", exc_info=True)

    def update_last_message_time(self):
        """更新最后消息时间（在收到新消息时调用）"""
        self.last_message_time = time.time()


class ChatLoopManager:
    """聊天循环管理器"""

    def __init__(self):
        self.loops: Dict[str, ChatLoop] = {}

    def create_loop(
        self,
        chat_id: str,
        agent: Any,
        chat_stream: Any,
        **kwargs
    ) -> ChatLoop:
        """
        创建聊天循环

        Args:
            chat_id: 聊天 ID
            agent: UnifiedAgent 实例
            chat_stream: ChatStream 实例
            **kwargs: 其他参数

        Returns:
            ChatLoop: 聊天循环实例
        """
        if chat_id in self.loops:
            logger.warning(f"聊天循环已存在: {chat_id}")
            return self.loops[chat_id]

        loop = ChatLoop(chat_id, agent, chat_stream, **kwargs)
        self.loops[chat_id] = loop
        return loop

    def get_loop(self, chat_id: str) -> Optional[ChatLoop]:
        """
        获取聊天循环

        Args:
            chat_id: 聊天 ID

        Returns:
            Optional[ChatLoop]: 聊天循环实例
        """
        return self.loops.get(chat_id)

    async def start_loop(self, chat_id: str):
        """
        启动聊天循环

        Args:
            chat_id: 聊天 ID
        """
        loop = self.loops.get(chat_id)
        if loop:
            await loop.start()
        else:
            logger.warning(f"聊天循环不存在: {chat_id}")

    async def stop_loop(self, chat_id: str):
        """
        停止聊天循环

        Args:
            chat_id: 聊天 ID
        """
        loop = self.loops.get(chat_id)
        if loop:
            await loop.stop()

    async def stop_all(self):
        """停止所有聊天循环"""
        for chat_id, loop in self.loops.items():
            await loop.stop()
        logger.info("所有聊天循环已停止")


# 全局实例
chat_loop_manager = ChatLoopManager()
