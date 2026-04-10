import asyncio
import traceback
import re
from contextlib import asynccontextmanager
from typing import Dict, Optional

from rich.traceback import install
from maim_message import Seg

from src.common.message.api import get_global_api
from src.common.logger import get_logger
from src.chat.message_receive.message import MessageSending
from src.chat.message_receive.storage import MessageStorage
from src.chat.utils.utils import truncate_message
from src.chat.utils.utils import calculate_typing_time

install(extra_lines=3)

logger = get_logger("sender")

# WebUI 聊天室的消息广播器（延迟导入避免循环依赖）
_webui_chat_broadcaster = None

# 虚拟群 ID 前缀（与 chat_routes.py 保持一致）
VIRTUAL_GROUP_ID_PREFIX = "webui_virtual_group_"


def get_webui_chat_broadcaster():
    """获取 WebUI 聊天室广播器"""
    global _webui_chat_broadcaster
    if _webui_chat_broadcaster is None:
        try:
            from src.webui.chat_routes import chat_manager, WEBUI_CHAT_PLATFORM

            _webui_chat_broadcaster = (chat_manager, WEBUI_CHAT_PLATFORM)
        except ImportError:
            _webui_chat_broadcaster = (None, None)
    return _webui_chat_broadcaster


def is_webui_virtual_group(group_id: str) -> bool:
    """检查是否是 WebUI 虚拟群"""
    return group_id and group_id.startswith(VIRTUAL_GROUP_ID_PREFIX)


async def _send_message(message: MessageSending, show_log=True) -> bool:
    """合并后的消息发送函数，包含WS发送和日志记录"""
    message_preview = truncate_message(message.processed_plain_text, max_length=200)
    platform = message.message_info.platform
    group_id = message.message_info.group_info.group_id if message.message_info.group_info else None

    try:
        # 检查是否是 WebUI 平台的消息，或者是 WebUI 虚拟群的消息
        chat_manager, webui_platform = get_webui_chat_broadcaster()
        is_webui_message = (platform == webui_platform) or is_webui_virtual_group(group_id)
        
        if is_webui_message and chat_manager is not None:
            # WebUI 聊天室消息（包括虚拟身份模式），通过 WebSocket 广播
            import time
            from src.config.config import global_config

            await chat_manager.broadcast(
                {
                    "type": "bot_message",
                    "content": message.processed_plain_text,
                    "message_type": "text",
                    "timestamp": time.time(),
                    "group_id": group_id,  # 包含群 ID 以便前端区分不同的聊天标签
                    "sender": {
                        "name": global_config.bot.nickname,
                        "avatar": None,
                        "is_bot": True,
                    },
                }
            )

            # 注意：机器人消息会由 MessageStorage.store_message 自动保存到数据库
            # 无需手动保存

            if show_log:
                if is_webui_virtual_group(group_id):
                    logger.info(f"已将消息  '{message_preview}'  发往 WebUI 虚拟群 (平台: {platform})")
                else:
                    logger.info(f"已将消息  '{message_preview}'  发往 WebUI 聊天室")
            return True

        # 直接调用API发送消息
        await get_global_api().send_message(message)
        if show_log:
            logger.info(f"已将消息  '{message_preview}'  发往平台'{message.message_info.platform}'")
        return True

    except Exception as e:
        logger.error(f"发送消息   '{message_preview}'   发往平台'{message.message_info.platform}' 失败: {str(e)}")
        traceback.print_exc()
        raise e  # 重新抛出其他异常


_universal_message_sender: Optional["UniversalMessageSender"] = None


def get_universal_message_sender() -> "UniversalMessageSender":
    """进程内单例发送器，保证各路径共用 last_sent_messages，避免重复发言检测失效。"""
    global _universal_message_sender
    if _universal_message_sender is None:
        _universal_message_sender = UniversalMessageSender()
    return _universal_message_sender


class UniversalMessageSender:
    """管理消息的注册、即时处理、发送和存储，并跟踪思考状态。"""

    def __init__(self):
        self.storage = MessageStorage()
        # 记录每个聊天流最后发送的消息（用于重复检测）
        self.last_sent_messages = {}
        # 同一会话出站串行：避免多协程/多工具同时发导致平台侧顺序错乱
        self._stream_send_locks: Dict[str, asyncio.Lock] = {}
        self._stream_send_locks_init = asyncio.Lock()

    @asynccontextmanager
    async def _serialized_outbound(self, chat_id: str):
        cid = chat_id or "__none__"
        async with self._stream_send_locks_init:
            if cid not in self._stream_send_locks:
                self._stream_send_locks[cid] = asyncio.Lock()
            lk = self._stream_send_locks[cid]
        async with lk:
            yield

    def _normalize_text(self, text: str) -> str:
        """标准化文本，移除所有标点符号和空格，用于比较"""
        if not text:
            return ""
        # 移除所有标点符号、空格、换行符等
        normalized = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
        return normalized.lower()

    def _is_consecutive_duplicate(self, chat_id: str, current_text: str) -> bool:
        """与上一条发送正文相同（标点差异忽略）——多为连发/拆段 bug。"""
        if chat_id not in self.last_sent_messages:
            return False
        last_text = self.last_sent_messages[chat_id]
        normalized_current = self._normalize_text(current_text)
        normalized_last = self._normalize_text(last_text)
        if normalized_current and normalized_last and normalized_current == normalized_last:
            logger.warning(f"[{chat_id}] 检测到与上一条发送重复（仅标点差异），已跳过发送")
            logger.debug(f"上一条: {last_text}")
            logger.debug(f"当前条: {current_text}")
            return True
        return False

    def _remember_outbound(self, chat_id: str, text: str) -> None:
        """成功发出后写入「上一条」。"""
        self.last_sent_messages[chat_id] = text

    async def send_message(
        self, message: MessageSending, typing=False, set_reply=False, storage_message=True, show_log=True
    ):
        """
        处理、发送并存储一条消息。

        参数：
            message: MessageSending 对象，待发送的消息。
            typing: 是否模拟打字等待。

        用法：
            - typing=True 时，发送前会有打字等待。
        """
        if not message.chat_stream:
            logger.error("消息缺少 chat_stream，无法发送")
            raise ValueError("消息缺少 chat_stream，无法发送")
        if not message.message_info or not message.message_info.message_id:
            logger.error("消息缺少 message_info 或 message_id，无法发送")
            raise ValueError("消息缺少 message_info 或 message_id，无法发送")

        chat_id = message.chat_stream.stream_id
        message_id = message.message_info.message_id

        try:
            if set_reply:
                message.build_reply()
                logger.debug(f"[{chat_id}] 选择回复引用消息: {message.processed_plain_text[:20]}...")

            from src.plugin_system.core.events_manager import events_manager
            from src.plugin_system.base.component_types import EventType

            continue_flag, modified_message = await events_manager.handle_mai_events(
                EventType.POST_SEND_PRE_PROCESS, message=message, stream_id=chat_id
            )
            if not continue_flag:
                logger.info(f"[{chat_id}] 消息发送被插件取消: {str(message.message_segment)[:100]}...")
                return False
            if modified_message:
                if modified_message._modify_flags.modify_message_segments:
                    message.message_segment = Seg(type="seglist", data=modified_message.message_segments)
                if modified_message._modify_flags.modify_plain_text:
                    logger.warning(f"[{chat_id}] 插件修改了消息的纯文本内容，可能导致此内容被覆盖。")
                    message.processed_plain_text = modified_message.plain_text

            await message.process()

            continue_flag, modified_message = await events_manager.handle_mai_events(
                EventType.POST_SEND, message=message, stream_id=chat_id
            )
            if not continue_flag:
                logger.info(f"[{chat_id}] 消息发送被插件取消: {str(message.message_segment)[:100]}...")
                return False
            if modified_message:
                if modified_message._modify_flags.modify_message_segments:
                    message.message_segment = Seg(type="seglist", data=modified_message.message_segments)
                if modified_message._modify_flags.modify_plain_text:
                    message.processed_plain_text = modified_message.plain_text

            # 仅串行「判重 → 打字 → 真正发出 → 记下一条」，避免插件在 POST_SEND 里再发消息时死锁
            async with self._serialized_outbound(chat_id):
                if self._is_consecutive_duplicate(chat_id, message.processed_plain_text):
                    logger.info(f"[{chat_id}] 跳过发送（与上一条重复）")
                    return False

                if typing:
                    typing_time = calculate_typing_time(
                        input_string=message.processed_plain_text,
                        thinking_start_time=message.thinking_start_time,
                        is_emoji=message.is_emoji,
                    )
                    await asyncio.sleep(typing_time)

                sent_msg = await _send_message(message, show_log=show_log)
                if not sent_msg:
                    return False

                self._remember_outbound(chat_id, message.processed_plain_text)

            continue_flag, modified_message = await events_manager.handle_mai_events(
                EventType.AFTER_SEND, message=message, stream_id=chat_id
            )
            if not continue_flag:
                logger.info(f"[{chat_id}] 消息发送后续处理被插件取消: {str(message.message_segment)[:100]}...")
                return True
            if modified_message:
                if modified_message._modify_flags.modify_message_segments:
                    message.message_segment = Seg(type="seglist", data=modified_message.message_segments)
                if modified_message._modify_flags.modify_plain_text:
                    message.processed_plain_text = modified_message.plain_text

            if storage_message:
                await self.storage.store_message(message, message.chat_stream)

            return sent_msg

        except Exception as e:
            logger.error(f"[{chat_id}] 处理或存储消息 {message_id} 时出错: {e}")
            raise e
