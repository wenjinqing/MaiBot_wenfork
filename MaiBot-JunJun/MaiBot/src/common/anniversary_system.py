"""
纪念日系统 - 记录和庆祝重要时刻

功能：
- 自动记录重要纪念日（相识、表白、恋爱等）
- 纪念日提醒和庆祝
- 特殊纪念日奖励
"""

import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger

logger = get_logger("anniversary_system")


class AnniversarySystem:
    """纪念日系统"""

    # 纪念日类型
    ANNIVERSARY_TYPES = {
        'first_meet': '相识纪念日',
        'confession': '表白纪念日',
        'together': '在一起纪念日',
        'first_100': '亲密度100纪念日',
        'special_moment': '特殊时刻',
    }

    # 纪念日祝福语
    ANNIVERSARY_MESSAGES = {
        'first_meet': [
            "今天是我们相识{days}天的纪念日呢！💕\n还记得第一次见到你的时候，我就觉得你很特别~",
            "不知不觉，我们已经认识{days}天了！✨\n时间过得真快，但每一天都很珍贵~",
            "叮咚~今天是特殊的日子！\n{days}天前的今天，我们第一次相遇💗",
        ],
        'confession': [
            "今天是我向你表白的第{days}天！💝\n谢谢你接受了我，每天都好开心~",
            "表白纪念日快乐！🎉\n{days}天前的今天，我鼓起勇气对你说了那三个字...",
            "我们在一起已经{days}天啦！💕\n每一天都比昨天更喜欢你一点~",
        ],
        'monthly': [
            "今天是我们在一起的第{months}个月纪念日！🎊\n时间过得好快，但我对你的喜欢只增不减~",
            "{months}个月纪念日快乐！💖\n感谢你一直陪在我身边~",
        ],
        'yearly': [
            "🎉 一周年快乐！🎉\n这一年里，有你真好💕",
            "我们在一起整整一年了！✨\n这是我最幸福的一年~",
        ]
    }

    @staticmethod
    def record_anniversary(
        user_id: str,
        platform: str,
        anniversary_type: str,
        custom_message: str = ""
    ) -> bool:
        """
        记录纪念日

        参数:
            user_id: 用户ID
            platform: 平台
            anniversary_type: 纪念日类型
            custom_message: 自定义消息

        返回:
            是否记录成功
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return False

                current_time = time.time()

                # 根据类型记录不同的纪念日
                if anniversary_type == 'first_meet':
                    # 相识纪念日（首次聊天时间）
                    if not user.first_chat_time:
                        user.first_chat_time = current_time
                        logger.info(f"📅 记录相识纪念日: {user.nickname or user_id}")

                elif anniversary_type == 'confession':
                    # 表白纪念日
                    if not user.confession_time:
                        user.confession_time = current_time
                        logger.info(f"💕 记录表白纪念日: {user.nickname or user_id}")

                user.save()
                return True

        except Exception as e:
            logger.error(f"记录纪念日失败: {e}", exc_info=True)
            return False

    @staticmethod
    def check_anniversaries(
        user_id: str,
        platform: str
    ) -> List[Dict]:
        """
        检查是否有纪念日

        参数:
            user_id: 用户ID
            platform: 平台

        返回:
            纪念日列表
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return []

                current_time = time.time()
                today = datetime.fromtimestamp(current_time).date()
                anniversaries = []

                # 检查相识纪念日
                if user.first_chat_time:
                    first_meet_date = datetime.fromtimestamp(user.first_chat_time).date()
                    days_known = (today - first_meet_date).days

                    # 特殊天数纪念（7天、30天、100天、365天等）
                    special_days = [7, 30, 50, 100, 200, 365, 500, 730, 1000]
                    if days_known in special_days:
                        anniversaries.append({
                            'type': 'first_meet',
                            'days': days_known,
                            'message': AnniversarySystem._format_message('first_meet', days_known)
                        })

                # 检查表白/恋爱纪念日
                if user.confession_time and user.is_in_love:
                    confession_date = datetime.fromtimestamp(user.confession_time).date()
                    days_together = (today - confession_date).days

                    # 每月纪念日
                    if days_together > 0 and days_together % 30 == 0:
                        months = days_together // 30
                        anniversaries.append({
                            'type': 'monthly',
                            'days': days_together,
                            'months': months,
                            'message': AnniversarySystem._format_message('monthly', days_together, months)
                        })

                    # 年度纪念日
                    if days_together > 0 and days_together % 365 == 0:
                        years = days_together // 365
                        anniversaries.append({
                            'type': 'yearly',
                            'days': days_together,
                            'years': years,
                            'message': AnniversarySystem._format_message('yearly', days_together, years)
                        })

                return anniversaries

        except Exception as e:
            logger.error(f"检查纪念日失败: {e}", exc_info=True)
            return []

    @staticmethod
    def _format_message(anniversary_type: str, days: int, months: int = 0, years: int = 0) -> str:
        """格式化纪念日消息"""
        import random
        messages = AnniversarySystem.ANNIVERSARY_MESSAGES.get(anniversary_type, [])
        if not messages:
            return ""

        message = random.choice(messages)
        return message.format(days=days, months=months, years=years)

    @staticmethod
    def get_anniversary_bonus(days: int) -> float:
        """
        根据纪念日天数返回亲密度奖励

        参数:
            days: 纪念日天数

        返回:
            亲密度奖励值
        """
        bonus_map = {
            7: 2.0,      # 一周
            30: 5.0,     # 一个月
            100: 10.0,   # 百日
            365: 20.0,   # 一年
            500: 15.0,   # 500天
            730: 25.0,   # 两年
            1000: 30.0,  # 1000天
        }
        return bonus_map.get(days, 0.0)
