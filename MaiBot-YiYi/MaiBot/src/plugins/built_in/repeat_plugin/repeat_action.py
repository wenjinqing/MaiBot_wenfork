"""
复读 Action - 基于 Action 系统的可靠复读实现
"""
from typing import Tuple
from src.plugin_system.base.base_action import BaseAction, ActionActivationType
from src.plugin_system.base.component_types import ChatMode
from src.common.logger import get_logger
from src.common.message_repository import find_messages
from src.config.config import global_config
from datetime import datetime

logger = get_logger("repeat_action")


class RepeatAction(BaseAction):
    """复读 Action"""

    action_name = "复读"
    action_description = "检测群聊复读并加入复读"
    activation_type = ActionActivationType.ALWAYS  # 总是检查
    mode_enable = ChatMode.GROUP  # 仅在群聊中启用
    action_parameters = {}

    # 类级别的状态记录（跨实例共享）
    _last_repeat_time = {}  # 记录每个群最后一次复读的时间
    _last_repeat_content = {}  # 记录每个群最后一次复读的内容

    async def execute(self) -> Tuple[bool, str]:
        """执行复读检测"""
        try:
            if self.__class__.mode_enable == ChatMode.GROUP and not self.is_group:
                return False, ""

            # 检查是否启用复读功能
            repeat_config = getattr(global_config, 'repeat', None)
            if not repeat_config or not getattr(repeat_config, 'enable', False):
                return False, ""

            # 获取配置
            threshold = getattr(repeat_config, 'threshold', 4)
            min_interval = getattr(repeat_config, 'min_interval_seconds', 60)
            min_length = getattr(repeat_config, 'min_message_length', 1)
            max_length = getattr(repeat_config, 'max_message_length', 50)

            # 获取当前消息文本
            current_text = self.action_message.processed_plain_text or ""
            current_text = current_text.strip()

            # 检查消息长度
            if len(current_text) < min_length or len(current_text) > max_length:
                return False, ""

            # 检查复读间隔
            chat_id = self.chat_id
            now = datetime.now().timestamp()
            last_time = RepeatAction._last_repeat_time.get(chat_id, 0)
            if now - last_time < min_interval:
                return False, ""

            # 检查是否刚刚复读过相同内容
            last_content = RepeatAction._last_repeat_content.get(chat_id, "")
            if last_content == current_text:
                return False, ""

            # 获取最近的消息历史
            recent_messages = find_messages(
                message_filter={'chat_id': chat_id},
                limit=threshold + 5,
                limit_mode='latest',
                filter_bot=False,
                filter_command=True,
            )

            if len(recent_messages) < threshold:
                return False, ""

            # 检查最近的N条消息是否都相同
            bot_user_id = str(global_config.bot.qq_account)
            repeat_count = 0
            is_bot_message = False

            # 从最新的消息开始检查
            for msg in list(recent_messages)[:threshold]:
                msg_text = (msg.processed_plain_text or "").strip()
                if msg_text == current_text:
                    repeat_count += 1
                    # 检查是否是机器人发送的
                    if msg.user_id == bot_user_id:
                        is_bot_message = True
                else:
                    break

            # 如果达到阈值且不是复读机器人自己的话
            if repeat_count >= threshold and not is_bot_message:
                # 记录复读时间和内容
                RepeatAction._last_repeat_time[chat_id] = now
                RepeatAction._last_repeat_content[chat_id] = current_text

                logger.info(f"检测到复读（{repeat_count}条相同消息）: {current_text[:20]}...")
                return True, current_text

            return False, ""

        except Exception as e:
            logger.error(f"复读检测失败: {e}", exc_info=True)
            return False, ""
