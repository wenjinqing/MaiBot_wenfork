"""
提醒任务管理器 - 定期检查提醒任务，时间到了发送提醒
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional
from src.common.logger import get_logger
from src.manager.async_task_manager import AsyncTask
from src.common.database.database_model import ReminderTasks
from src.plugin_system.apis import send_api
from src.config.config import global_config, model_config
from src.person_info.person_info import Person
from src.llm_models.utils_model import LLMRequest

logger = get_logger("提醒任务管理器")


class ReminderTaskManager(AsyncTask):
    """提醒任务管理器"""

    def __init__(self):
        # 从配置读取参数
        check_interval = getattr(global_config.reminder, 'check_interval_seconds', 60)
        super().__init__(
            task_name="ReminderTaskManager",
            wait_before_start=10,  # 启动后等待10秒
            run_interval=check_interval,  # 每N秒检查一次
        )

        # 初始化LLM请求器
        self.llm_request = LLMRequest(
            model_set=model_config.model_task_config.utils_small,
            request_type="reminder.message"
        )

    async def run(self):
        """定期检查提醒任务，执行到期的任务"""
        try:
            now = datetime.now().timestamp()

            # 查询所有未完成、未取消、且时间已到的任务
            due_tasks = (
                ReminderTasks.select()
                .where(
                    (ReminderTasks.remind_time <= now) &
                    (ReminderTasks.is_completed == False) &
                    (ReminderTasks.is_cancelled == False)
                )
                .order_by(ReminderTasks.remind_time)
            )

            if not due_tasks:
                return

            logger.info(f"发现 {len(list(due_tasks))} 个到期的提醒任务")

            for task in due_tasks:
                try:
                    await self._execute_reminder_task(task)
                except Exception as e:
                    logger.error(f"执行提醒任务 {task.task_id} 时出错: {e}")
                    continue

        except Exception as e:
            logger.error(f"检查提醒任务失败: {e}")
            import traceback
            traceback.print_exc()

    async def _execute_reminder_task(self, task: ReminderTasks):
        """执行提醒任务"""
        try:
            logger.info(f"执行提醒任务: {task.task_content} (任务ID: {task.task_id})")

            # 获取用户信息
            person = Person(person_id=task.person_id)
            person_name = person.person_name or "你"

            # 计算延迟时间
            now = datetime.now().timestamp()
            delay_seconds = now - task.remind_time

            # 构建提示词，让大模型生成拟人化的提醒
            if delay_seconds < 60:
                time_context = "现在正是时候"
            elif delay_seconds < 300:  # 5分钟内
                time_context = f"刚才（{int(delay_seconds / 60)}分钟前）"
            else:
                remind_time_str = datetime.fromtimestamp(task.remind_time).strftime("%H:%M")
                time_context = f"{remind_time_str}的时候"

            # 构建提示词
            reminder_prompt = f"""你需要提醒用户做一件事。

用户信息：
- 称呼：{person_name}
- 要做的事：{task.task_content}
- 提醒时间：{time_context}

请生成一条自然、友好的提醒消息。要求：
1. 语气要轻松自然，像朋友之间的提醒
2. 不要使用表情符号（如⏰、✅等）
3. 不要说"提醒你"、"提醒一下"这种生硬的词
4. 可以根据时间适当调整语气（准时/稍晚）
5. 保持简洁，1-2句话即可

直接输出提醒消息，不要有任何前缀或解释："""

            # 调用LLM生成提醒消息
            try:
                remind_message, (reasoning, model_name, _) = await self.llm_request.generate_response_async(
                    prompt=reminder_prompt,
                    temperature=0.8,
                    max_tokens=100,
                )

                if not remind_message or not remind_message.strip():
                    # 如果LLM生成失败，使用简单的备用消息
                    remind_message = f"{person_name}，该{task.task_content}啦～"
                else:
                    remind_message = remind_message.strip()

            except Exception as e:
                logger.error(f"LLM生成提醒消息失败: {e}")
                # 使用备用消息
                remind_message = f"{person_name}，该{task.task_content}啦～"

            # 发送提醒消息
            success = await send_api.text_to_stream(
                text=remind_message,
                stream_id=task.stream_id,
                typing=False,
                storage_message=True,
            )

            if success:
                # 检查是否需要重复
                if task.repeat_type:
                    await self._schedule_next_repeat(task)
                else:
                    # 标记为已完成
                    task.is_completed = True
                    task.save()

                logger.info(f"成功发送提醒: {task.task_content}")
            else:
                logger.error(f"发送提醒失败: {task.task_content}")

        except Exception as e:
            logger.error(f"执行提醒任务失败: {e}")
            import traceback
            traceback.print_exc()

    async def _schedule_next_repeat(self, task: ReminderTasks):
        """安排下一次重复提醒"""
        try:
            # 计算下一次提醒时间
            next_remind_time = None
            current_time = datetime.fromtimestamp(task.remind_time)

            if task.repeat_type == "daily":
                next_remind_time = current_time + timedelta(days=1)
            elif task.repeat_type == "weekly":
                next_remind_time = current_time + timedelta(weeks=1)
            elif task.repeat_type == "monthly":
                # 简单处理：加30天
                next_remind_time = current_time + timedelta(days=30)

            if next_remind_time:
                # 更新任务
                task.remind_time = next_remind_time.timestamp()
                task.repeat_count += 1
                task.save()

                logger.info(f"已安排下一次重复提醒: {next_remind_time.strftime('%Y-%m-%d %H:%M')}")
            else:
                # 标记为已完成
                task.is_completed = True
                task.save()

        except Exception as e:
            logger.error(f"安排下一次重复提醒失败: {e}")


# 提醒任务工具函数

async def create_reminder_task(
    person_id: str,
    stream_id: str,
    task_content: str,
    remind_time: float,
    repeat_type: Optional[str] = None,
) -> str:
    """
    创建提醒任务

    Args:
        person_id: 用户的person_id
        stream_id: 聊天流ID
        task_content: 任务内容（如"出门"）
        remind_time: 提醒时间戳
        repeat_type: 重复类型（daily/weekly/monthly/null）

    Returns:
        str: 任务ID
    """
    try:
        task_id = str(uuid.uuid4())
        now = datetime.now().timestamp()

        task = ReminderTasks.create(
            task_id=task_id,
            person_id=person_id,
            stream_id=stream_id,
            task_content=task_content,
            remind_time=remind_time,
            created_time=now,
            is_completed=False,
            is_cancelled=False,
            repeat_type=repeat_type,
            repeat_count=0,
        )

        logger.info(f"创建提醒任务: {task_content} (时间: {datetime.fromtimestamp(remind_time).strftime('%Y-%m-%d %H:%M')})")
        return task_id

    except Exception as e:
        logger.error(f"创建提醒任务失败: {e}")
        raise


async def cancel_reminder_task(task_id: str) -> bool:
    """
    取消提醒任务

    Args:
        task_id: 任务ID

    Returns:
        bool: 是否成功
    """
    try:
        task = ReminderTasks.get_or_none(ReminderTasks.task_id == task_id)
        if not task:
            logger.warning(f"未找到任务: {task_id}")
            return False

        task.is_cancelled = True
        task.save()

        logger.info(f"取消提醒任务: {task.task_content}")
        return True

    except Exception as e:
        logger.error(f"取消提醒任务失败: {e}")
        return False


async def get_user_reminder_tasks(person_id: str, include_completed: bool = False):
    """
    获取用户的提醒任务列表

    Args:
        person_id: 用户的person_id
        include_completed: 是否包含已完成的任务

    Returns:
        list: 任务列表
    """
    try:
        query = ReminderTasks.select().where(
            (ReminderTasks.person_id == person_id) &
            (ReminderTasks.is_cancelled == False)
        )

        if not include_completed:
            query = query.where(ReminderTasks.is_completed == False)

        tasks = list(query.order_by(ReminderTasks.remind_time))
        return tasks

    except Exception as e:
        logger.error(f"获取用户提醒任务失败: {e}")
        return []
