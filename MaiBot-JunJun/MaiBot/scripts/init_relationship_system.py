"""
亲密度系统初始化脚本

功能：
1. 为现有用户初始化亲密度相关字段
2. 提供亲密度计算和更新工具
3. 根据历史消息数据计算初始亲密度
"""

import sys
import os
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.common.database.database_model import PersonInfo, Messages, db
from src.common.logger import get_logger

logger = get_logger("relationship_init")


def calculate_relationship_value(user_id: str, platform: str) -> dict:
    """
    根据历史消息计算用户的初始亲密度

    返回：
    {
        'relationship_value': int,  # 亲密度 (0-100)
        'total_messages': int,      # 总消息数
        'chat_frequency': float,    # 聊天频率
        'first_meet_time': float,   # 首次见面时间
        'last_chat_time': float,    # 最后聊天时间
        'interaction_score': float  # 互动评分
    }
    """
    try:
        # 查询该用户的所有消息
        messages = Messages.select().where(
            (Messages.user_id == user_id) &
            (Messages.user_platform == platform)
        ).order_by(Messages.time.asc())

        message_list = list(messages)
        total_messages = len(message_list)

        if total_messages == 0:
            return {
                'relationship_value': 0,
                'total_messages': 0,
                'chat_frequency': 0.0,
                'first_meet_time': None,
                'last_chat_time': None,
                'interaction_score': 0.0
            }

        # 首次和最后聊天时间
        first_meet_time = message_list[0].time
        last_chat_time = message_list[-1].time

        # 计算时间跨度（天数）
        time_span_days = (last_chat_time - first_meet_time) / 86400
        if time_span_days < 1:
            time_span_days = 1

        # 计算聊天频率（每天消息数）
        chat_frequency = total_messages / time_span_days

        # 计算亲密度（基于多个因素）
        # 1. 消息数量贡献 (0-40分)
        msg_score = min(40, total_messages / 10)

        # 2. 聊天频率贡献 (0-30分)
        freq_score = min(30, chat_frequency * 3)

        # 3. 时间跨度贡献 (0-20分) - 认识时间越长越高
        time_score = min(20, time_span_days / 30)

        # 4. 最近活跃度 (0-10分) - 最近7天有聊天加分
        days_since_last = (time.time() - last_chat_time) / 86400
        recent_score = max(0, 10 - days_since_last)

        relationship_value = int(msg_score + freq_score + time_score + recent_score)
        relationship_value = min(100, max(0, relationship_value))

        # 综合互动评分
        interaction_score = round(
            (msg_score / 40 * 0.4 +
             freq_score / 30 * 0.3 +
             time_score / 20 * 0.2 +
             recent_score / 10 * 0.1) * 10,
            2
        )

        return {
            'relationship_value': relationship_value,
            'total_messages': total_messages,
            'chat_frequency': round(chat_frequency, 2),
            'first_meet_time': first_meet_time,
            'last_chat_time': last_chat_time,
            'interaction_score': interaction_score
        }

    except Exception as e:
        logger.error(f"计算用户 {user_id} 亲密度失败: {e}")
        return {
            'relationship_value': 0,
            'total_messages': 0,
            'chat_frequency': 0.0,
            'first_meet_time': None,
            'last_chat_time': None,
            'interaction_score': 0.0
        }


def init_all_users():
    """为所有现有用户初始化亲密度数据"""
    logger.info("开始初始化用户亲密度系统...")

    try:
        with db:
            users = PersonInfo.select()
            total = users.count()
            logger.info(f"找到 {total} 个用户")

            updated_count = 0
            for i, user in enumerate(users, 1):
                logger.info(f"处理用户 {i}/{total}: {user.nickname or user.user_id}")

                # 计算亲密度数据
                data = calculate_relationship_value(user.user_id, user.platform)

                # 更新用户信息
                user.relationship_value = data['relationship_value']
                user.total_messages = data['total_messages']
                user.chat_frequency = data['chat_frequency']
                user.first_meet_time = data['first_meet_time']
                user.last_chat_time = data['last_chat_time']
                user.interaction_score = data['interaction_score']

                # 如果没有设置心情值，设为默认50
                if not hasattr(user, 'mood_value') or user.mood_value is None:
                    user.mood_value = 50

                user.save()
                updated_count += 1

                logger.info(
                    f"  亲密度: {data['relationship_value']}, "
                    f"消息数: {data['total_messages']}, "
                    f"频率: {data['chat_frequency']:.2f}/天"
                )

            logger.info(f"初始化完成！共更新 {updated_count} 个用户")

    except Exception as e:
        logger.error(f"初始化失败: {e}")
        raise


def show_top_users(limit=10):
    """显示亲密度最高的用户"""
    logger.info(f"\n亲密度排行榜 (Top {limit}):")
    logger.info("=" * 80)

    try:
        with db:
            users = (PersonInfo
                    .select()
                    .where(PersonInfo.relationship_value > 0)
                    .order_by(PersonInfo.relationship_value.desc())
                    .limit(limit))

            for i, user in enumerate(users, 1):
                logger.info(
                    f"{i:2d}. {user.nickname or user.user_id:20} | "
                    f"亲密度: {user.relationship_value:3d} | "
                    f"消息: {user.total_messages:5d} | "
                    f"频率: {user.chat_frequency:6.2f}/天"
                )
    except Exception as e:
        logger.error(f"查询失败: {e}")


def get_relationship_level(value: int) -> str:
    """根据亲密度值返回关系等级"""
    if value >= 80:
        return "挚友"
    elif value >= 60:
        return "好友"
    elif value >= 40:
        return "熟人"
    elif value >= 20:
        return "认识"
    else:
        return "陌生人"


def show_statistics():
    """显示亲密度统计信息"""
    logger.info("\n亲密度系统统计:")
    logger.info("=" * 80)

    try:
        with db:
            total_users = PersonInfo.select().count()

            # 按等级统计
            levels = {
                "挚友 (80-100)": PersonInfo.select().where(PersonInfo.relationship_value >= 80).count(),
                "好友 (60-79)": PersonInfo.select().where(
                    (PersonInfo.relationship_value >= 60) &
                    (PersonInfo.relationship_value < 80)
                ).count(),
                "熟人 (40-59)": PersonInfo.select().where(
                    (PersonInfo.relationship_value >= 40) &
                    (PersonInfo.relationship_value < 60)
                ).count(),
                "认识 (20-39)": PersonInfo.select().where(
                    (PersonInfo.relationship_value >= 20) &
                    (PersonInfo.relationship_value < 40)
                ).count(),
                "陌生人 (0-19)": PersonInfo.select().where(PersonInfo.relationship_value < 20).count(),
            }

            logger.info(f"总用户数: {total_users}")
            logger.info("\n关系等级分布:")
            for level, count in levels.items():
                percentage = (count / total_users * 100) if total_users > 0 else 0
                logger.info(f"  {level:20} {count:4d} 人 ({percentage:5.1f}%)")

            # 平均亲密度
            avg_relationship = PersonInfo.select(
                PersonInfo.relationship_value
            ).where(PersonInfo.relationship_value > 0).scalar(as_tuple=True)

            if avg_relationship:
                avg = sum(avg_relationship) / len(avg_relationship)
                logger.info(f"\n平均亲密度: {avg:.2f}")

    except Exception as e:
        logger.error(f"统计失败: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="亲密度系统管理工具")
    parser.add_argument('--init', action='store_true', help='初始化所有用户的亲密度')
    parser.add_argument('--top', type=int, default=10, help='显示亲密度排行榜')
    parser.add_argument('--stats', action='store_true', help='显示统计信息')

    args = parser.parse_args()

    if args.init:
        init_all_users()

    if args.stats:
        show_statistics()

    if args.top:
        show_top_users(args.top)

    if not any([args.init, args.stats, args.top]):
        # 默认行为：初始化并显示统计
        init_all_users()
        show_statistics()
        show_top_users(10)
