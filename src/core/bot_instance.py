"""
BotInstance - 单个机器人实例

封装了单个机器人的所有组件和状态。
"""

import asyncio
import time
from typing import Optional
from enum import Enum

from src.config.official_configs import BotInstanceConfig
from src.core.bot_scoped_db import BotScopedDB
from src.core.bot_context import set_current_bot_id, BotContextManager
from src.common.logger import get_logger

logger = get_logger("BotInstance")


class BotStatus(Enum):
    """机器人状态枚举"""
    STOPPED = "stopped"      # 已停止
    STARTING = "starting"    # 启动中
    RUNNING = "running"      # 运行中
    STOPPING = "stopping"    # 停止中
    ERROR = "error"          # 错误状态


class BotInstance:
    """单个机器人实例"""

    def __init__(self, bot_id: str, config: BotInstanceConfig):
        """
        初始化机器人实例

        Args:
            bot_id: 机器人唯一标识符
            config: 机器人配置
        """
        self.bot_id = bot_id
        self.config = config
        self.status = BotStatus.STOPPED
        self.error_message: Optional[str] = None

        # 数据库访问层
        self.db = BotScopedDB(bot_id)

        # 统计信息
        self.message_count = 0
        self.start_time: Optional[float] = None
        self.last_message_time: Optional[float] = None

        # 组件（延迟初始化）
        self.chat_bot = None
        self.heartflow_processor = None
        self.mood_manager = None
        self.plugin_manager = None

        logger.info(f"创建机器人实例: {bot_id} ({config.bot.nickname})")

    async def initialize(self):
        """初始化机器人组件"""
        try:
            self.status = BotStatus.STARTING
            logger.info(f"[{self.bot_id}] 正在初始化机器人组件...")

            # 设置机器人上下文
            set_current_bot_id(self.bot_id)

            # TODO: 初始化各个组件
            # self.chat_bot = ChatBot(self.bot_id, self.config)
            # self.heartflow_processor = HeartFCMessageReceiver(self.bot_id, self.config)
            # self.mood_manager = MoodManager(self.bot_id, self.config)
            # self.plugin_manager = PluginManager(self.bot_id, self.config)

            # 等待组件初始化完成
            await asyncio.sleep(0.1)

            self.status = BotStatus.RUNNING
            self.start_time = time.time()
            logger.info(f"[{self.bot_id}] 机器人初始化完成")

        except Exception as e:
            self.status = BotStatus.ERROR
            self.error_message = str(e)
            logger.error(f"[{self.bot_id}] 机器人初始化失败: {e}")
            raise

    async def start(self):
        """启动机器人"""
        if self.status == BotStatus.RUNNING:
            logger.warning(f"[{self.bot_id}] 机器人已在运行中")
            return

        logger.info(f"[{self.bot_id}] 启动机器人...")
        await self.initialize()

    async def stop(self):
        """停止机器人"""
        if self.status == BotStatus.STOPPED:
            logger.warning(f"[{self.bot_id}] 机器人已停止")
            return

        try:
            self.status = BotStatus.STOPPING
            logger.info(f"[{self.bot_id}] 正在停止机器人...")

            # TODO: 停止各个组件
            # if self.chat_bot:
            #     await self.chat_bot.stop()
            # if self.heartflow_processor:
            #     await self.heartflow_processor.stop()

            self.status = BotStatus.STOPPED
            logger.info(f"[{self.bot_id}] 机器人已停止")

        except Exception as e:
            self.status = BotStatus.ERROR
            self.error_message = str(e)
            logger.error(f"[{self.bot_id}] 停止机器人失败: {e}")
            raise

    async def restart(self):
        """重启机器人"""
        logger.info(f"[{self.bot_id}] 重启机器人...")
        await self.stop()
        await asyncio.sleep(1)
        await self.start()

    async def reload_config(self, new_config: BotInstanceConfig):
        """
        重载配置

        Args:
            new_config: 新的配置
        """
        logger.info(f"[{self.bot_id}] 重载配置...")
        self.config = new_config

        # 如果机器人正在运行，需要重启以应用新配置
        if self.status == BotStatus.RUNNING:
            await self.restart()

    async def process_message(self, message_data: dict):
        """
        处理消息

        Args:
            message_data: 消息数据
        """
        if self.status != BotStatus.RUNNING:
            logger.warning(f"[{self.bot_id}] 机器人未运行，无法处理消息")
            return

        try:
            # 设置机器人上下文（确保所有数据库查询都使用正确的 bot_id）
            with BotContextManager(self.bot_id):
                self.message_count += 1
                self.last_message_time = time.time()

                # TODO: 调用消息处理器
                # await self.heartflow_processor.process_message(message_data)

                logger.debug(f"[{self.bot_id}] 处理消息: {message_data.get('message_id', 'unknown')}")

        except Exception as e:
            logger.error(f"[{self.bot_id}] 处理消息失败: {e}")
            raise

    def get_status_info(self) -> dict:
        """
        获取机器人状态信息

        Returns:
            状态信息字典
        """
        uptime = None
        if self.start_time:
            uptime = time.time() - self.start_time

        return {
            "bot_id": self.bot_id,
            "nickname": self.config.bot.nickname,
            "qq_account": self.config.bot.qq_account,
            "status": self.status.value,
            "enabled": self.config.enabled,
            "error_message": self.error_message,
            "message_count": self.message_count,
            "start_time": self.start_time,
            "uptime": uptime,
            "last_message_time": self.last_message_time,
        }

    def get_statistics(self) -> dict:
        """
        获取机器人统计信息

        Returns:
            统计信息字典
        """
        # 获取数据库统计
        db_stats = self.db.get_statistics()

        # 合并状态信息
        status_info = self.get_status_info()

        return {
            **status_info,
            **db_stats,
        }

    def __repr__(self) -> str:
        return f"BotInstance(bot_id={self.bot_id}, nickname={self.config.bot.nickname}, status={self.status.value})"
