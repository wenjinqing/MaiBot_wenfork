"""
提醒任务Action - 解析用户的提醒请求并创建任务
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from src.common.logger import get_logger
from src.plugin_system.base.base_action import BaseAction, ActionActivationType
from src.plugin_system.base.component_types import ChatMode
from src.proactive_system.reminder_task_manager import create_reminder_task, cancel_reminder_task, get_user_reminder_tasks
from src.person_info.person_info import Person
from src.llm_models.utils_model import LLMRequest
from src.config.config import model_config

logger = get_logger("提醒任务Action")


class SetReminderAction(BaseAction):
    """设置提醒任务"""

    action_name = "设置提醒"
    action_description = "为用户设置提醒任务"
    activation_type = ActionActivationType.ALWAYS
    mode_enable = ChatMode.ALL

    action_require = """当用户要求你在特定时间提醒他做某事时，使用此动作。

示例：
- "12点提醒我出门"
- "明天早上8点提醒我开会"
- "下午3点提醒我喝水"
- "每天早上7点提醒我起床"
- "一小时后提醒我休息"

你需要：
1. 解析用户想要的提醒时间
2. 解析用户想要做的事情
3. 判断是否需要重复提醒

使用此动作时，在reasoning中说明：
- 提醒时间（如"今天12:00"）
- 提醒内容（如"出门"）
- 是否重复（如"每天重复"）"""

    action_parameters = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初始化LLM请求器
        self.llm_request = LLMRequest(
            model_set=model_config.model_task_config.utils_small,
            request_type="reminder.confirm"
        )

    async def execute(self) -> Tuple[bool, str]:
        """执行设置提醒任务"""
        try:
            # 获取消息内容
            if not self.action_message:
                return False, "❌ 缺少消息参数"

            user_text = self.action_message.processed_plain_text
            stream_id = self.chat_id
            platform = self.platform
            user_id = self.user_id

            # 获取person_id
            person = Person(platform=platform, user_id=user_id)
            person_id = person.person_id

            # 解析提醒请求
            remind_time, task_content, repeat_type = self._parse_reminder_request(user_text)

            if not remind_time or not task_content:
                return False, "❌ 无法解析提醒时间或内容，请重新描述"

            # 创建提醒任务
            task_id = await create_reminder_task(
                person_id=person_id,
                stream_id=stream_id,
                task_content=task_content,
                remind_time=remind_time,
                repeat_type=repeat_type,
            )

            # 构建提示词，让大模型生成拟人化的确认消息
            remind_time_obj = datetime.fromtimestamp(remind_time)
            time_str = remind_time_obj.strftime("%H:%M")
            today = datetime.now().date()
            remind_date = remind_time_obj.date()

            if remind_date == today:
                time_desc = f"今天{time_str}"
            elif remind_date == today + timedelta(days=1):
                time_desc = f"明天{time_str}"
            else:
                time_desc = remind_time_obj.strftime("%m月%d日 %H:%M")

            repeat_desc = ""
            if repeat_type == "daily":
                repeat_desc = "，每天重复"
            elif repeat_type == "weekly":
                repeat_desc = "，每周重复"
            elif repeat_type == "monthly":
                repeat_desc = "，每月重复"

            confirmation_prompt = f"""用户设置了一个提醒任务，你需要确认这个任务。

任务信息：
- 提醒时间：{time_desc}
- 任务内容：{task_content}
- 重复类型：{repeat_desc if repeat_desc else "一次性"}

请生成一条自然、友好的确认消息。要求：
1. 语气要轻松自然，像朋友之间的对话
2. 不要使用表情符号（如✅、⏰等）
3. 确认你会在指定时间提醒用户
4. 保持简洁，1句话即可
5. 可以稍微口语化一点

直接输出确认消息，不要有任何前缀或解释："""

            # 调用LLM生成确认消息
            try:
                reply_message, (reasoning, model_name, _) = await self.llm_request.generate_response_async(
                    prompt=confirmation_prompt,
                    temperature=0.8,
                    max_tokens=100,
                )

                if not reply_message or not reply_message.strip():
                    # 如果LLM生成失败，使用简单的备用消息
                    reply_message = f"好的，{time_desc}我会提醒你{task_content}的～"
                else:
                    reply_message = reply_message.strip()

            except Exception as e:
                logger.error(f"LLM生成确认消息失败: {e}")
                # 使用备用消息
                reply_message = f"好的，{time_desc}我会提醒你{task_content}的～"

            return True, reply_message

        except Exception as e:
            logger.error(f"设置提醒任务失败: {e}")
            import traceback
            traceback.print_exc()
            return False, f"❌ 设置提醒失败: {str(e)}"

    def _parse_reminder_request(self, text: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
        """
        解析提醒请求

        Returns:
            (remind_time, task_content, repeat_type)
        """
        try:
            # 提取时间和内容
            remind_time = None
            task_content = None
            repeat_type = None

            # 检查是否是重复提醒
            if "每天" in text or "每日" in text:
                repeat_type = "daily"
            elif "每周" in text:
                repeat_type = "weekly"
            elif "每月" in text:
                repeat_type = "monthly"

            # 解析时间
            now = datetime.now()

            # 模式1: "X点" 或 "X点Y分"
            time_pattern1 = r'(\d{1,2})点(?:(\d{1,2})分)?'
            match = re.search(time_pattern1, text)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if match.group(2) else 0

                # 构建提醒时间
                remind_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # 如果时间已过，设置为明天
                if remind_datetime <= now:
                    remind_datetime += timedelta(days=1)

                remind_time = remind_datetime.timestamp()

            # 模式2: "X小时后" 或 "X分钟后"
            if not remind_time:
                time_pattern2 = r'(\d+)(小时|分钟)后'
                match = re.search(time_pattern2, text)
                if match:
                    amount = int(match.group(1))
                    unit = match.group(2)

                    if unit == "小时":
                        remind_datetime = now + timedelta(hours=amount)
                    else:  # 分钟
                        remind_datetime = now + timedelta(minutes=amount)

                    remind_time = remind_datetime.timestamp()

            # 模式3: "明天X点"
            if not remind_time:
                time_pattern3 = r'明天(\d{1,2})点(?:(\d{1,2})分)?'
                match = re.search(time_pattern3, text)
                if match:
                    hour = int(match.group(1))
                    minute = int(match.group(2)) if match.group(2) else 0

                    remind_datetime = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                    remind_time = remind_datetime.timestamp()

            # 模式4: "早上/中午/下午/晚上X点"
            if not remind_time:
                time_pattern4 = r'(早上|中午|下午|晚上)(\d{1,2})点(?:(\d{1,2})分)?'
                match = re.search(time_pattern4, text)
                if match:
                    period = match.group(1)
                    hour = int(match.group(2))
                    minute = int(match.group(3)) if match.group(3) else 0

                    # 调整小时（如果需要）
                    if period == "早上" and hour < 12:
                        pass  # 保持原样
                    elif period == "中午" and hour < 12:
                        hour = 12
                    elif period == "下午" and hour < 12:
                        hour += 12
                    elif period == "晚上" and hour < 12:
                        hour += 12

                    remind_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    # 如果时间已过，设置为明天
                    if remind_datetime <= now:
                        remind_datetime += timedelta(days=1)

                    remind_time = remind_datetime.timestamp()

            # 提取任务内容
            # 查找"提醒我"后面的内容
            content_pattern = r'提醒(?:我|他|她)?(.+?)(?:$|[，。！？])'
            match = re.search(content_pattern, text)
            if match:
                task_content = match.group(1).strip()
                # 移除时间相关的词
                task_content = re.sub(r'(早上|中午|下午|晚上|\d+点|\d+分钟?|小时|明天|每天|每周|每月)', '', task_content).strip()

            return remind_time, task_content, repeat_type

        except Exception as e:
            logger.error(f"解析提醒请求失败: {e}")
            return None, None, None


class ListRemindersAction(BaseAction):
    """查看提醒任务列表"""

    action_name = "查看提醒"
    action_description = "查看用户的提醒任务列表"
    activation_type = ActionActivationType.KEYWORD
    mode_enable = ChatMode.ALL

    action_require = """当用户想要查看他的提醒任务列表时，使用此动作。

示例：
- "我有哪些提醒"
- "查看我的提醒"
- "提醒列表"
- "我设置了什么提醒"

使用此动作时，在reasoning中说明用户想要查看提醒列表。"""

    action_parameters = {}

    async def execute(self) -> Tuple[bool, str]:
        """执行查看提醒任务列表"""
        try:
            # 获取参数
            if not self.action_message:
                return False, "❌ 缺少消息参数"

            platform = self.platform
            user_id = self.user_id

            # 获取person_id
            person = Person(platform=platform, user_id=user_id)
            person_id = person.person_id

            # 获取提醒任务列表
            tasks = await get_user_reminder_tasks(person_id, include_completed=False)

            if not tasks:
                return True, "你目前没有待执行的提醒任务"

            # 构建回复
            if len(tasks) == 1:
                task = tasks[0]
                remind_time_str = datetime.fromtimestamp(task.remind_time).strftime("%m-%d %H:%M")
                repeat_info = ""
                if task.repeat_type == "daily":
                    repeat_info = "（每天）"
                elif task.repeat_type == "weekly":
                    repeat_info = "（每周）"
                elif task.repeat_type == "monthly":
                    repeat_info = "（每月）"

                return True, f"你有一个提醒：{remind_time_str} {task.task_content}{repeat_info}"
            else:
                reply = f"你有 {len(tasks)} 个提醒任务：\n\n"
                for i, task in enumerate(tasks, 1):
                    remind_time_str = datetime.fromtimestamp(task.remind_time).strftime("%m-%d %H:%M")
                    repeat_info = ""
                    if task.repeat_type == "daily":
                        repeat_info = " 🔁"
                    elif task.repeat_type == "weekly":
                        repeat_info = " 🔁"
                    elif task.repeat_type == "monthly":
                        repeat_info = " 🔁"

                    reply += f"{i}. {remind_time_str} {task.task_content}{repeat_info}\n"

                return True, reply

        except Exception as e:
            logger.error(f"查看提醒任务列表失败: {e}")
            import traceback
            traceback.print_exc()
            return False, f"❌ 查看提醒失败: {str(e)}"


class CancelReminderAction(BaseAction):
    """取消提醒任务"""

    action_name = "取消提醒"
    action_description = "取消用户的提醒任务"
    activation_type = ActionActivationType.KEYWORD
    mode_enable = ChatMode.ALL

    action_require = """当用户想要取消某个提醒任务时，使用此动作。

示例：
- "取消提醒"
- "删除提醒"
- "不用提醒我了"

注意：由于需要知道具体取消哪个任务，建议先让用户查看提醒列表，然后再取消。
目前的实现会取消用户最近的一个提醒任务。"""

    action_parameters = {}

    async def execute(self) -> Tuple[bool, str]:
        """执行取消提醒任务"""
        try:
            # 获取参数
            if not self.action_message:
                return False, "❌ 缺少消息参数"

            platform = self.platform
            user_id = self.user_id

            # 获取person_id
            person = Person(platform=platform, user_id=user_id)
            person_id = person.person_id

            # 获取提醒任务列表
            tasks = await get_user_reminder_tasks(person_id, include_completed=False)

            if not tasks:
                return True, "你目前没有待执行的提醒任务"

            # 取消最近的一个任务（简化实现）
            task = tasks[0]
            success = await cancel_reminder_task(task.task_id)

            if success:
                return True, f"好的，已经取消了「{task.task_content}」的提醒"
            else:
                return False, "取消提醒失败了，要不要再试一次？"

        except Exception as e:
            logger.error(f"取消提醒任务失败: {e}")
            import traceback
            traceback.print_exc()
            return False, f"❌ 取消提醒失败: {str(e)}"
