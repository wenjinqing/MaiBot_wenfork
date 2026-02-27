"""
表白触发条件检查器

检查用户是否满足表白条件
"""

import time
from typing import Optional, Dict
from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger

logger = get_logger("confession_checker")


class ConfessionChecker:
    """表白条件检查器"""

    # 表白触发条件
    CONFESSION_CONDITIONS = {
        'active': {
            'min_relationship': 99.0,      # 主动表白：最低亲密度
            'min_messages': 500,           # 主动表白：最低消息数
            'min_frequency': 4.0,          # 主动表白：最低聊天频率
            'max_days_inactive': 7,        # 最近活跃天数
            'min_mood': 70,                # 主动表白：最低心情值
        },
        'passive': {
            'min_relationship': 90.0,      # 接受表白：最低亲密度（降低到90）
            'min_messages': 200,           # 接受表白：最低消息数
            'min_frequency': 2.0,          # 接受表白：最低聊天频率
            'max_days_inactive': 7,        # 最近活跃天数
            'min_mood': 60,                # 接受表白：最低心情值
        }
    }

    @staticmethod
    def check_confession_conditions(
        user_id: str,
        platform: str,
        check_type: str = 'active'  # 'active' 主动表白, 'passive' 接受表白
    ) -> Dict:
        """
        检查用户是否满足表白条件

        参数:
            user_id: 用户ID
            platform: 平台
            check_type: 检查类型
                - 'active': 主动表白（亲密度>=99）
                - 'passive': 接受表白（亲密度>=95）

        返回:
            {
                'can_confess': bool,  # 是否可以表白
                'conditions_met': dict,  # 各项条件是否满足
                'missing_conditions': list,  # 未满足的条件
                'user_stats': dict  # 用户统计信息
            }
        """
        try:
            with db:
                # 首先检查是否已经有恋人
                existing_lover = PersonInfo.select().where(
                    PersonInfo.is_in_love == True
                ).first()

                if existing_lover:
                    # 如果已经有恋人，不能再表白
                    return {
                        'can_confess': False,
                        'conditions_met': {},
                        'missing_conditions': [f'已经有恋人了（{existing_lover.nickname}），不能同时和多个人恋爱'],
                        'user_stats': {}
                    }

                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return {
                        'can_confess': False,
                        'conditions_met': {},
                        'missing_conditions': ['用户不存在'],
                        'user_stats': {}
                    }

                # 计算距离上次聊天的天数
                current_time = time.time()
                days_since_last = 999
                if user.last_chat_time:
                    days_since_last = (current_time - user.last_chat_time) / 86400

                # 根据检查类型获取条件
                conditions = ConfessionChecker.CONFESSION_CONDITIONS[check_type]

                # 检查各项条件
                conditions_met = {
                    'relationship': user.relationship_value >= conditions['min_relationship'],
                    'messages': user.total_messages >= conditions['min_messages'],
                    'frequency': user.chat_frequency >= conditions['min_frequency'],
                    'recent_active': days_since_last <= conditions['max_days_inactive'],
                    'mood': user.mood_value >= conditions['min_mood'],
                }

                # 找出未满足的条件
                missing_conditions = []
                if not conditions_met['relationship']:
                    missing_conditions.append(
                        f"亲密度不足 ({user.relationship_value:.1f}/{conditions['min_relationship']})"
                    )
                if not conditions_met['messages']:
                    missing_conditions.append(
                        f"消息数不足 ({user.total_messages}/{conditions['min_messages']})"
                    )
                if not conditions_met['frequency']:
                    missing_conditions.append(
                        f"聊天频率不足 ({user.chat_frequency:.1f}/{conditions['min_frequency']})"
                    )
                if not conditions_met['recent_active']:
                    missing_conditions.append(
                        f"最近未活跃 (已{days_since_last:.0f}天未聊天)"
                    )
                if not conditions_met['mood']:
                    missing_conditions.append(
                        f"心情值不足 ({user.mood_value}/{conditions['min_mood']})"
                    )

                # 判断是否可以表白
                can_confess = all(conditions_met.values())

                # 用户统计信息
                user_stats = {
                    'nickname': user.nickname,
                    'relationship_value': user.relationship_value,
                    'total_messages': user.total_messages,
                    'chat_frequency': user.chat_frequency,
                    'days_since_last': days_since_last,
                    'mood_value': user.mood_value,
                    'is_in_love': user.is_in_love,
                }

                return {
                    'can_confess': can_confess,
                    'conditions_met': conditions_met,
                    'missing_conditions': missing_conditions,
                    'user_stats': user_stats
                }

        except Exception as e:
            logger.error(f"检查表白条件失败: {e}", exc_info=True)
            return {
                'can_confess': False,
                'conditions_met': {},
                'missing_conditions': ['检查失败'],
                'user_stats': {}
            }

    @staticmethod
    def get_confession_progress(user_id: str, platform: str) -> Dict:
        """
        获取表白进度

        返回:
            各项条件的完成百分比
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return {}

                current_time = time.time()
                days_since_last = 0
                if user.last_chat_time:
                    days_since_last = (current_time - user.last_chat_time) / 86400

                # 使用主动表白的条件计算进度
                conditions = ConfessionChecker.CONFESSION_CONDITIONS['active']

                progress = {
                    'relationship': min(100, (user.relationship_value / conditions['min_relationship']) * 100),
                    'messages': min(100, (user.total_messages / conditions['min_messages']) * 100),
                    'frequency': min(100, (user.chat_frequency / conditions['min_frequency']) * 100),
                    'recent_active': 100 if days_since_last <= conditions['max_days_inactive'] else 0,
                    'mood': min(100, (user.mood_value / conditions['min_mood']) * 100),
                }

                # 总体进度
                overall_progress = sum(progress.values()) / len(progress)

                return {
                    'progress': progress,
                    'overall': overall_progress
                }

        except Exception as e:
            logger.error(f"获取表白进度失败: {e}", exc_info=True)
            return {}


# 使用示例
if __name__ == "__main__":
    # 检查表白条件
    result = ConfessionChecker.check_confession_conditions(
        user_id="test_user",
        platform="qq",
        check_type="active"
    )

    print(f"可以表白: {result['can_confess']}")
    print(f"\n条件满足情况:")
    for condition, met in result['conditions_met'].items():
        status = "✓" if met else "✗"
        print(f"  {status} {condition}")

    if result['missing_conditions']:
        print(f"\n未满足的条件:")
        for condition in result['missing_conditions']:
            print(f"  - {condition}")

    print(f"\n用户统计:")
    for key, value in result['user_stats'].items():
        print(f"  {key}: {value}")
