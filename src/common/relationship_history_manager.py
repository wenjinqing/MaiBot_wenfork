"""
关系历史记录管理系统

记录所有重要的关系变化事件，方便调试和分析
"""

import time
import json
from typing import Optional, List, Dict
from src.common.database.database_model import RelationshipHistory, db
from src.common.logger import get_logger

logger = get_logger("relationship_history")


class RelationshipHistoryManager:
    """关系历史记录管理器"""

    @staticmethod
    def record_event(
        user_id: str,
        platform: str,
        event_type: str,
        old_value: Optional[float] = None,
        new_value: Optional[float] = None,
        reason: str = "",
        details: Optional[Dict] = None
    ) -> bool:
        """
        记录关系事件

        参数:
            user_id: 用户ID
            platform: 平台
            event_type: 事件类型
            old_value: 旧值
            new_value: 新值
            reason: 原因
            details: 详细信息（字典）

        返回:
            是否记录成功
        """
        try:
            with db:
                change_amount = None
                if old_value is not None and new_value is not None:
                    change_amount = new_value - old_value

                RelationshipHistory.create(
                    user_id=user_id,
                    platform=platform,
                    event_type=event_type,
                    old_value=old_value,
                    new_value=new_value,
                    change_amount=change_amount,
                    reason=reason,
                    details=json.dumps(details, ensure_ascii=False) if details else None,
                    timestamp=time.time()
                )

                logger.debug(
                    f"记录关系事件: {user_id}@{platform} - {event_type} "
                    f"({old_value} -> {new_value})"
                )
                return True

        except Exception as e:
            logger.error(f"记录关系事件失败: {e}", exc_info=True)
            return False

    @staticmethod
    def get_user_history(
        user_id: str,
        platform: str,
        event_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        获取用户的关系历史

        参数:
            user_id: 用户ID
            platform: 平台
            event_type: 事件类型（可选，不指定则返回所有类型）
            limit: 返回数量限制

        返回:
            历史记录列表
        """
        try:
            with db:
                query = RelationshipHistory.select().where(
                    (RelationshipHistory.user_id == user_id) &
                    (RelationshipHistory.platform == platform)
                )

                if event_type:
                    query = query.where(RelationshipHistory.event_type == event_type)

                query = query.order_by(RelationshipHistory.timestamp.desc()).limit(limit)

                history = []
                for record in query:
                    history.append({
                        'event_type': record.event_type,
                        'old_value': record.old_value,
                        'new_value': record.new_value,
                        'change_amount': record.change_amount,
                        'reason': record.reason,
                        'details': json.loads(record.details) if record.details else None,
                        'timestamp': record.timestamp
                    })

                return history

        except Exception as e:
            logger.error(f"获取用户历史失败: {e}", exc_info=True)
            return []

    @staticmethod
    def get_recent_events(
        event_type: Optional[str] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取最近的关系事件

        参数:
            event_type: 事件类型（可选）
            hours: 时间范围（小时）
            limit: 返回数量限制

        返回:
            事件列表
        """
        try:
            with db:
                cutoff_time = time.time() - (hours * 3600)

                query = RelationshipHistory.select().where(
                    RelationshipHistory.timestamp >= cutoff_time
                )

                if event_type:
                    query = query.where(RelationshipHistory.event_type == event_type)

                query = query.order_by(RelationshipHistory.timestamp.desc()).limit(limit)

                events = []
                for record in query:
                    events.append({
                        'user_id': record.user_id,
                        'platform': record.platform,
                        'event_type': record.event_type,
                        'old_value': record.old_value,
                        'new_value': record.new_value,
                        'change_amount': record.change_amount,
                        'reason': record.reason,
                        'timestamp': record.timestamp
                    })

                return events

        except Exception as e:
            logger.error(f"获取最近事件失败: {e}", exc_info=True)
            return []

    @staticmethod
    def get_statistics(user_id: str, platform: str) -> Dict:
        """
        获取用户的关系统计信息

        返回:
            统计信息字典
        """
        try:
            with db:
                history = RelationshipHistory.select().where(
                    (RelationshipHistory.user_id == user_id) &
                    (RelationshipHistory.platform == platform)
                )

                total_events = history.count()

                # 统计各类事件数量
                event_counts = {}
                for record in history:
                    event_type = record.event_type
                    event_counts[event_type] = event_counts.get(event_type, 0) + 1

                # 获取首次和最近事件
                first_event = history.order_by(RelationshipHistory.timestamp.asc()).first()
                last_event = history.order_by(RelationshipHistory.timestamp.desc()).first()

                return {
                    'total_events': total_events,
                    'event_counts': event_counts,
                    'first_event_time': first_event.timestamp if first_event else None,
                    'last_event_time': last_event.timestamp if last_event else None
                }

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}", exc_info=True)
            return {}

    @staticmethod
    def clean_old_records(days: int = 90) -> int:
        """
        清理旧的历史记录

        参数:
            days: 保留天数

        返回:
            删除的记录数
        """
        try:
            with db:
                cutoff_time = time.time() - (days * 86400)

                deleted = RelationshipHistory.delete().where(
                    RelationshipHistory.timestamp < cutoff_time
                ).execute()

                logger.info(f"清理了 {deleted} 条超过 {days} 天的历史记录")
                return deleted

        except Exception as e:
            logger.error(f"清理历史记录失败: {e}", exc_info=True)
            return 0


# 使用示例
if __name__ == "__main__":
    # 记录一个事件
    RelationshipHistoryManager.record_event(
        user_id="test_user",
        platform="qq",
        event_type="level_up",
        old_value=50.0,
        new_value=60.0,
        reason="关系等级提升：熟人 -> 朋友",
        details={'old_level': '熟人', 'new_level': '朋友'}
    )

    # 获取用户历史
    history = RelationshipHistoryManager.get_user_history(
        user_id="test_user",
        platform="qq",
        limit=10
    )

    print(f"找到 {len(history)} 条历史记录")
    for event in history:
        print(f"- {event['event_type']}: {event['reason']}")
