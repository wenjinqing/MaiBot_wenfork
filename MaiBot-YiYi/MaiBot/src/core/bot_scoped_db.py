"""
BotScopedDB - 提供带 bot_id 过滤的数据库访问层

此类封装了数据库查询，自动添加 bot_id 过滤，确保数据隔离。
"""

from typing import Optional, List
from src.common.database.database_model import (
    PersonInfo,
    ChatStreams,
    Messages,
    Expression,
    Jargon,
    RelationshipHistory,
    ReminderTasks,
    db
)
from src.common.logger import get_logger

logger = get_logger("BotScopedDB")


class BotScopedDB:
    """带 bot_id 作用域的数据库访问层"""

    def __init__(self, bot_id: str):
        """
        初始化数据库访问层

        Args:
            bot_id: 机器人唯一标识符
        """
        self.bot_id = bot_id
        logger.debug(f"初始化 BotScopedDB，bot_id: {bot_id}")

    # ==================== PersonInfo 相关方法 ====================

    def get_person_info(self, platform: str, user_id: str) -> Optional[PersonInfo]:
        """
        获取用户信息

        Args:
            platform: 平台（如 "qq"）
            user_id: 用户ID

        Returns:
            PersonInfo 对象，如果不存在则返回 None
        """
        return PersonInfo.get_or_none(
            PersonInfo.bot_id == self.bot_id,
            PersonInfo.platform == platform,
            PersonInfo.user_id == user_id
        )

    def create_person_info(self, platform: str, user_id: str, **kwargs) -> PersonInfo:
        """
        创建用户信息

        Args:
            platform: 平台
            user_id: 用户ID
            **kwargs: 其他字段

        Returns:
            创建的 PersonInfo 对象
        """
        # 生成 person_id
        person_id = f"{self.bot_id}_{platform}_{user_id}"

        with db:
            person = PersonInfo.create(
                bot_id=self.bot_id,
                platform=platform,
                user_id=user_id,
                person_id=person_id,
                **kwargs
            )
        logger.debug(f"创建用户信息: {person_id}")
        return person

    def get_or_create_person_info(self, platform: str, user_id: str, **kwargs) -> tuple[PersonInfo, bool]:
        """
        获取或创建用户信息

        Args:
            platform: 平台
            user_id: 用户ID
            **kwargs: 创建时的其他字段

        Returns:
            (PersonInfo 对象, 是否新创建)
        """
        person = self.get_person_info(platform, user_id)
        if person:
            return person, False

        person = self.create_person_info(platform, user_id, **kwargs)
        return person, True

    def get_all_persons(self, limit: Optional[int] = None) -> List[PersonInfo]:
        """
        获取所有用户信息

        Args:
            limit: 限制返回数量

        Returns:
            PersonInfo 列表
        """
        query = PersonInfo.select().where(PersonInfo.bot_id == self.bot_id)
        if limit:
            query = query.limit(limit)
        return list(query)

    def get_persons_by_relationship(self, min_value: float = 0.0, max_value: float = 100.0) -> List[PersonInfo]:
        """
        根据亲密度范围获取用户

        Args:
            min_value: 最小亲密度
            max_value: 最大亲密度

        Returns:
            PersonInfo 列表
        """
        return list(
            PersonInfo.select().where(
                PersonInfo.bot_id == self.bot_id,
                PersonInfo.relationship_value >= min_value,
                PersonInfo.relationship_value <= max_value
            )
        )

    # ==================== ChatStreams 相关方法 ====================

    def get_chat_stream(self, stream_id: str) -> Optional[ChatStreams]:
        """
        获取聊天流

        Args:
            stream_id: 聊天流ID

        Returns:
            ChatStreams 对象，如果不存在则返回 None
        """
        return ChatStreams.get_or_none(
            ChatStreams.bot_id == self.bot_id,
            ChatStreams.stream_id == stream_id
        )

    def create_chat_stream(self, stream_id: str, **kwargs) -> ChatStreams:
        """
        创建聊天流

        Args:
            stream_id: 聊天流ID
            **kwargs: 其他字段

        Returns:
            创建的 ChatStreams 对象
        """
        with db:
            stream = ChatStreams.create(
                bot_id=self.bot_id,
                stream_id=stream_id,
                **kwargs
            )
        logger.debug(f"创建聊天流: {stream_id}")
        return stream

    def get_or_create_chat_stream(self, stream_id: str, **kwargs) -> tuple[ChatStreams, bool]:
        """
        获取或创建聊天流

        Args:
            stream_id: 聊天流ID
            **kwargs: 创建时的其他字段

        Returns:
            (ChatStreams 对象, 是否新创建)
        """
        stream = self.get_chat_stream(stream_id)
        if stream:
            return stream, False

        stream = self.create_chat_stream(stream_id, **kwargs)
        return stream, True

    # ==================== Messages 相关方法 ====================

    def get_messages(self, chat_id: str, limit: Optional[int] = None) -> List[Messages]:
        """
        获取聊天消息

        Args:
            chat_id: 聊天ID
            limit: 限制返回数量

        Returns:
            Messages 列表
        """
        query = Messages.select().where(
            Messages.bot_id == self.bot_id,
            Messages.chat_id == chat_id
        ).order_by(Messages.time.desc())

        if limit:
            query = query.limit(limit)

        return list(query)

    def create_message(self, chat_id: str, message_id: str, **kwargs) -> Messages:
        """
        创建消息记录

        Args:
            chat_id: 聊天ID
            message_id: 消息ID
            **kwargs: 其他字段

        Returns:
            创建的 Messages 对象
        """
        with db:
            message = Messages.create(
                bot_id=self.bot_id,
                chat_id=chat_id,
                message_id=message_id,
                **kwargs
            )
        return message

    # ==================== Expression 相关方法 ====================

    def get_expressions(self, chat_id: str) -> List[Expression]:
        """
        获取表达学习记录

        Args:
            chat_id: 聊天ID

        Returns:
            Expression 列表
        """
        return list(
            Expression.select().where(
                Expression.bot_id == self.bot_id,
                Expression.chat_id == chat_id
            )
        )

    def create_expression(self, chat_id: str, **kwargs) -> Expression:
        """
        创建表达学习记录

        Args:
            chat_id: 聊天ID
            **kwargs: 其他字段

        Returns:
            创建的 Expression 对象
        """
        with db:
            expression = Expression.create(
                bot_id=self.bot_id,
                chat_id=chat_id,
                **kwargs
            )
        return expression

    # ==================== Jargon 相关方法 ====================

    def get_jargons(self, chat_id: str) -> List[Jargon]:
        """
        获取黑话记录

        Args:
            chat_id: 聊天ID

        Returns:
            Jargon 列表
        """
        return list(
            Jargon.select().where(
                Jargon.bot_id == self.bot_id,
                Jargon.chat_id == chat_id
            )
        )

    def create_jargon(self, chat_id: str, content: str, **kwargs) -> Jargon:
        """
        创建黑话记录

        Args:
            chat_id: 聊天ID
            content: 黑话内容
            **kwargs: 其他字段

        Returns:
            创建的 Jargon 对象
        """
        with db:
            jargon = Jargon.create(
                bot_id=self.bot_id,
                chat_id=chat_id,
                content=content,
                **kwargs
            )
        return jargon

    # ==================== RelationshipHistory 相关方法 ====================

    def get_relationship_history(
        self,
        user_id: str,
        platform: str,
        limit: Optional[int] = None
    ) -> List[RelationshipHistory]:
        """
        获取关系历史记录

        Args:
            user_id: 用户ID
            platform: 平台
            limit: 限制返回数量

        Returns:
            RelationshipHistory 列表
        """
        query = RelationshipHistory.select().where(
            RelationshipHistory.bot_id == self.bot_id,
            RelationshipHistory.user_id == user_id,
            RelationshipHistory.platform == platform
        ).order_by(RelationshipHistory.timestamp.desc())

        if limit:
            query = query.limit(limit)

        return list(query)

    def create_relationship_history(
        self,
        user_id: str,
        platform: str,
        event_type: str,
        **kwargs
    ) -> RelationshipHistory:
        """
        创建关系历史记录

        Args:
            user_id: 用户ID
            platform: 平台
            event_type: 事件类型
            **kwargs: 其他字段

        Returns:
            创建的 RelationshipHistory 对象
        """
        import time
        with db:
            history = RelationshipHistory.create(
                bot_id=self.bot_id,
                user_id=user_id,
                platform=platform,
                event_type=event_type,
                timestamp=time.time(),
                **kwargs
            )
        return history

    # ==================== ReminderTasks 相关方法 ====================

    def get_reminder_tasks(
        self,
        person_id: Optional[str] = None,
        is_completed: Optional[bool] = None
    ) -> List[ReminderTasks]:
        """
        获取提醒任务

        Args:
            person_id: 用户person_id（可选）
            is_completed: 是否已完成（可选）

        Returns:
            ReminderTasks 列表
        """
        query = ReminderTasks.select().where(ReminderTasks.bot_id == self.bot_id)

        if person_id is not None:
            query = query.where(ReminderTasks.person_id == person_id)

        if is_completed is not None:
            query = query.where(ReminderTasks.is_completed == is_completed)

        return list(query)

    def create_reminder_task(self, task_id: str, person_id: str, **kwargs) -> ReminderTasks:
        """
        创建提醒任务

        Args:
            task_id: 任务ID
            person_id: 用户person_id
            **kwargs: 其他字段

        Returns:
            创建的 ReminderTasks 对象
        """
        with db:
            task = ReminderTasks.create(
                bot_id=self.bot_id,
                task_id=task_id,
                person_id=person_id,
                **kwargs
            )
        return task

    # ==================== 统计方法 ====================

    def get_statistics(self) -> dict:
        """
        获取当前机器人的统计信息

        Returns:
            统计信息字典
        """
        with db:
            return {
                "bot_id": self.bot_id,
                "total_persons": PersonInfo.select().where(PersonInfo.bot_id == self.bot_id).count(),
                "total_chat_streams": ChatStreams.select().where(ChatStreams.bot_id == self.bot_id).count(),
                "total_messages": Messages.select().where(Messages.bot_id == self.bot_id).count(),
                "total_expressions": Expression.select().where(Expression.bot_id == self.bot_id).count(),
                "total_jargons": Jargon.select().where(Jargon.bot_id == self.bot_id).count(),
                "total_relationship_history": RelationshipHistory.select().where(RelationshipHistory.bot_id == self.bot_id).count(),
                "total_reminder_tasks": ReminderTasks.select().where(ReminderTasks.bot_id == self.bot_id).count(),
            }
