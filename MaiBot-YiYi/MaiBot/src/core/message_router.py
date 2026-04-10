"""
MessageRouter - 消息路由器

负责将消息路由到对应的机器人实例。
"""

from typing import Dict, Optional
from src.core.bot_instance import BotInstance, BotStatus
from src.common.logger import get_logger

logger = get_logger("MessageRouter")


class MessageRouter:
    """消息路由器"""

    def __init__(self):
        """初始化消息路由器"""
        self.bot_instances: Dict[str, BotInstance] = {}
        self.qq_to_bot_map: Dict[str, str] = {}  # QQ账号 -> bot_id 映射
        self.failed_route_count: int = 0
        logger.info("消息路由器已初始化")

    def register_bot(self, bot_instance: BotInstance):
        """
        注册机器人实例

        Args:
            bot_instance: 机器人实例
        """
        bot_id = bot_instance.bot_id
        qq_account = bot_instance.config.bot.qq_account

        if bot_id in self.bot_instances:
            logger.warning(f"机器人 {bot_id} 已注册，将被覆盖")

        self.bot_instances[bot_id] = bot_instance
        self.qq_to_bot_map[qq_account] = bot_id

        logger.info(f"注册机器人: {bot_id} (QQ: {qq_account}, 昵称: {bot_instance.config.bot.nickname})")

    def unregister_bot(self, bot_id: str):
        """
        注销机器人实例

        Args:
            bot_id: 机器人ID
        """
        if bot_id not in self.bot_instances:
            logger.warning(f"机器人 {bot_id} 未注册")
            return

        bot_instance = self.bot_instances[bot_id]
        qq_account = bot_instance.config.bot.qq_account

        del self.bot_instances[bot_id]
        if qq_account in self.qq_to_bot_map:
            del self.qq_to_bot_map[qq_account]

        logger.info(f"注销机器人: {bot_id}")

    def get_bot_by_id(self, bot_id: str) -> Optional[BotInstance]:
        """
        根据 bot_id 获取机器人实例

        Args:
            bot_id: 机器人ID

        Returns:
            机器人实例，如果不存在则返回 None
        """
        return self.bot_instances.get(bot_id)

    def get_bot_by_qq(self, qq_account: str) -> Optional[BotInstance]:
        """
        根据 QQ 账号获取机器人实例

        Args:
            qq_account: QQ账号

        Returns:
            机器人实例，如果不存在则返回 None
        """
        bot_id = self.qq_to_bot_map.get(qq_account)
        if bot_id:
            return self.bot_instances.get(bot_id)
        return None

    def get_all_bots(self) -> Dict[str, BotInstance]:
        """
        获取所有机器人实例

        Returns:
            机器人实例字典 {bot_id: BotInstance}
        """
        return self.bot_instances.copy()

    def get_running_bots(self) -> Dict[str, BotInstance]:
        """
        获取所有运行中的机器人实例

        Returns:
            运行中的机器人实例字典
        """
        return {
            bot_id: bot
            for bot_id, bot in self.bot_instances.items()
            if bot.status == BotStatus.RUNNING
        }

    async def route_message(self, message_data: dict) -> bool:
        """
        路由消息到对应的机器人实例

        Args:
            message_data: 消息数据，应包含目标信息

        Returns:
            是否成功路由
        """
        try:
            # 提取目标 QQ 账号
            target_qq = self._extract_target_qq(message_data)

            if not target_qq:
                logger.warning("无法从消息中提取目标 QQ 账号")
                self.failed_route_count += 1
                return False

            # 查找对应的机器人实例
            bot_instance = self.get_bot_by_qq(target_qq)

            if not bot_instance:
                logger.warning(f"未找到 QQ 账号 {target_qq} 对应的机器人实例")
                self.failed_route_count += 1
                return False

            if bot_instance.status != BotStatus.RUNNING:
                logger.warning(f"机器人 {bot_instance.bot_id} 未运行，状态: {bot_instance.status.value}")
                self.failed_route_count += 1
                return False

            # 路由消息到机器人实例
            logger.debug(f"路由消息到机器人: {bot_instance.bot_id} (QQ: {target_qq})")
            await bot_instance.process_message(message_data)

            return True

        except Exception as e:
            logger.error(f"路由消息失败: {e}")
            self.failed_route_count += 1
            return False

    def _extract_target_qq(self, message_data: dict) -> Optional[str]:
        """
        从消息数据中提取目标 QQ 账号

        Args:
            message_data: 消息数据

        Returns:
            目标 QQ 账号，如果无法提取则返回 None
        """
        # 尝试多种方式提取目标 QQ
        # 1. 直接从 target_qq 字段获取
        if "target_qq" in message_data:
            return message_data["target_qq"]

        # 2. 从 bot_info 获取
        if "bot_info" in message_data and "qq_account" in message_data["bot_info"]:
            return message_data["bot_info"]["qq_account"]

        # 3. 从 message_info 获取（如果是私聊）
        if "message_info" in message_data:
            msg_info = message_data["message_info"]
            if "platform" in msg_info and msg_info["platform"] == "qq":
                # 对于私聊消息，接收者就是机器人
                if "receiver_id" in msg_info:
                    return msg_info["receiver_id"]

        # 4. 从 chat_stream 获取
        if "chat_stream" in message_data:
            stream = message_data["chat_stream"]
            if "bot_qq" in stream:
                return stream["bot_qq"]

        # 5. 默认返回第一个运行中的机器人（兼容模式）
        running_bots = self.get_running_bots()
        if running_bots:
            first_bot = next(iter(running_bots.values()))
            logger.debug(f"无法提取目标 QQ，使用默认机器人: {first_bot.bot_id}")
            return first_bot.config.bot.qq_account

        return None

    async def broadcast_message(self, message_data: dict):
        """
        广播消息到所有运行中的机器人

        Args:
            message_data: 消息数据
        """
        running_bots = self.get_running_bots()

        if not running_bots:
            logger.warning("没有运行中的机器人，无法广播消息")
            return

        logger.info(f"广播消息到 {len(running_bots)} 个机器人")

        # 并发处理
        tasks = [
            bot.process_message(message_data)
            for bot in running_bots.values()
        ]

        import asyncio
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        fail_n = sum(1 for r in results if isinstance(r, Exception))
        if fail_n:
            self.failed_route_count += fail_n
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"广播完成: {success_count}/{len(running_bots)} 成功")

    def get_router_statistics(self) -> dict:
        """
        获取路由器统计信息

        Returns:
            统计信息字典
        """
        total_bots = len(self.bot_instances)
        running_bots = len(self.get_running_bots())
        stopped_bots = sum(1 for bot in self.bot_instances.values() if bot.status == BotStatus.STOPPED)
        error_bots = sum(1 for bot in self.bot_instances.values() if bot.status == BotStatus.ERROR)

        total_messages = sum(bot.message_count for bot in self.bot_instances.values())

        # 构建机器人列表
        bots = []
        for bot_id, bot in self.bot_instances.items():
            bots.append({
                "bot_id": bot_id,
                "nickname": bot.config.bot.nickname,
                "qq_account": bot.config.bot.qq_account,
                "status": bot.status.value,
                "message_count": bot.message_count,
            })

        return {
            "total_bots": total_bots,
            "running_bots": running_bots,
            "stopped_bots": stopped_bots,
            "error_bots": error_bots,
            "total_messages": total_messages,
            "failed_routes": self.failed_route_count,
            "bots": bots,
        }

    def __repr__(self) -> str:
        return f"MessageRouter(bots={len(self.bot_instances)}, running={len(self.get_running_bots())})"


# 全局消息路由器实例
_message_router: Optional[MessageRouter] = None


def get_message_router() -> MessageRouter:
    """获取全局消息路由器实例"""
    global _message_router
    if _message_router is None:
        _message_router = MessageRouter()
    return _message_router
