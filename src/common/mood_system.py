"""
心情值管理系统

心情值影响：
- 回复风格（心情好时更活泼）
- 亲密度提升速度（心情好时提升快20%）
- 表白触发条件（心情值 >= 70）
"""

import time
from typing import Optional, Dict
from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger

logger = get_logger("mood_system")


class MoodSystem:
    """心情值管理系统"""

    # 心情值变化规则
    MOOD_RULES = {
        'praised': 10,           # 被赞美/夸奖
        'cared': 8,              # 被关心
        'gift': 15,              # 收到礼物/红包
        'long_chat': 5,          # 长时间聊天（>30分钟）
        'deep_talk': 8,          # 深度对话
        'funny': 5,              # 有趣的对话

        'ignored': -5,           # 被无视
        'cold': -3,              # 冷淡回复
        'penalty_minor': -5,     # 轻微惩罚
        'penalty_moderate': -10, # 中度惩罚
        'penalty_severe': -20,   # 严重惩罚
        'long_absence': -15,     # 长时间未联系
    }

    @staticmethod
    def update_mood(
        user_id: str,
        platform: str,
        mood_change: float,
        reason: str = ""
    ) -> Optional[Dict]:
        """
        更新用户心情值

        参数:
            user_id: 用户ID
            platform: 平台
            mood_change: 心情变化值（正数提升，负数降低）
            reason: 变化原因

        返回:
            更新后的用户信息
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    logger.warning(f"用户不存在: {user_id}@{platform}")
                    return None

                old_mood = user.mood_value
                new_mood = max(0, min(100, old_mood + mood_change))
                user.mood_value = new_mood
                user.save()

                # 记录显著的心情变化
                if abs(mood_change) >= 10:
                    direction = "提升" if mood_change > 0 else "下降"
                    logger.info(
                        f"😊 心情{direction}: {user.nickname or user_id} "
                        f"({old_mood} -> {new_mood}, {mood_change:+.0f}) - {reason}"
                    )

                return {
                    'user_id': user_id,
                    'nickname': user.nickname,
                    'old_mood': old_mood,
                    'new_mood': new_mood,
                    'mood_change': mood_change
                }

        except Exception as e:
            logger.error(f"更新心情值失败: {e}", exc_info=True)
            return None

    @staticmethod
    def get_mood_multiplier(mood_value: float) -> float:
        """
        根据心情值返回亲密度提升倍率

        心情值 >= 80: 1.2x（心情很好）
        心情值 60-80: 1.1x（心情不错）
        心情值 40-60: 1.0x（心情一般）
        心情值 20-40: 0.9x（心情不好）
        心情值 < 20: 0.8x（心情很差）
        """
        if mood_value >= 80:
            return 1.2
        elif mood_value >= 60:
            return 1.1
        elif mood_value >= 40:
            return 1.0
        elif mood_value >= 20:
            return 0.9
        else:
            return 0.8

    @staticmethod
    def get_mood_description(mood_value: float) -> str:
        """获取心情描述"""
        if mood_value >= 80:
            return "心情很好 😊"
        elif mood_value >= 60:
            return "心情不错 🙂"
        elif mood_value >= 40:
            return "心情一般 😐"
        elif mood_value >= 20:
            return "心情不好 😔"
        else:
            return "心情很差 😢"

    @staticmethod
    def daily_mood_recovery(user_id: str, platform: str) -> bool:
        """
        每日心情值自然恢复到50（中性）

        返回: 是否进行了恢复
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return False

                old_mood = user.mood_value

                # 向50靠拢（每天恢复10%的差距）
                if old_mood != 50:
                    recovery = (50 - old_mood) * 0.1
                    new_mood = old_mood + recovery
                    user.mood_value = round(new_mood)
                    user.save()

                    logger.debug(
                        f"心情自然恢复: {user.nickname or user_id} "
                        f"({old_mood} -> {user.mood_value})"
                    )
                    return True

                return False

        except Exception as e:
            logger.error(f"心情恢复失败: {e}")
            return False

    @staticmethod
    def detect_mood_keywords(message_text: str) -> Optional[str]:
        """
        检测消息中的心情关键词

        返回: 心情事件类型（praised/cared/funny等）
        """
        if not message_text:
            return None

        message_lower = message_text.lower()

        # 赞美关键词
        praise_keywords = [
            '好棒', '厉害', '优秀', '聪明', '可爱', '漂亮', '帅',
            '温柔', '贴心', '善良', '有趣', '幽默', '好看'
        ]
        if any(kw in message_lower for kw in praise_keywords):
            return 'praised'

        # 关心关键词
        care_keywords = [
            '还好吗', '怎么样', '累不累', '休息', '注意身体',
            '别太累', '照顾好自己', '多喝水', '早点睡'
        ]
        if any(kw in message_lower for kw in care_keywords):
            return 'cared'

        # 有趣的对话（包含笑声）
        funny_keywords = ['哈哈', '哈哈哈', '笑死', '好笑', '有意思', 'www', '2333']
        if any(kw in message_lower for kw in funny_keywords):
            return 'funny'

        return None


# 使用示例
if __name__ == "__main__":
    # 测试心情值更新
    result = MoodSystem.update_mood(
        user_id="test_user",
        platform="qq",
        mood_change=10,
        reason="被夸奖"
    )

    if result:
        print(f"用户: {result['nickname']}")
        print(f"心情变化: {result['old_mood']} -> {result['new_mood']}")
        print(f"心情描述: {MoodSystem.get_mood_description(result['new_mood'])}")
        print(f"亲密度倍率: {MoodSystem.get_mood_multiplier(result['new_mood'])}x")
