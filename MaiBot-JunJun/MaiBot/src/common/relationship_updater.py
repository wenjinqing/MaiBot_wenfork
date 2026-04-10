"""
亲密度动态更新工具

在聊天过程中实时更新用户的亲密度值
可以集成到消息处理流程中
"""

import time
from typing import Optional
from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger
from src.common.person_info_resolve import get_person_by_user_platform

logger = get_logger("relationship_updater")


class RelationshipUpdater:
    """亲密度更新器"""

    # 亲密度变化规则（大幅降低提升速度）
    RULES = {
        'normal_message': 0.02,     # 普通消息 +0.02 (大幅降低)
        'long_message': 0.08,       # 长消息(>50字) +0.08 (大幅降低)
        'emoji_message': 0.05,      # 表情包消息 +0.05 (大幅降低)
        'image_message': 0.05,      # 图片消息 +0.05 (大幅降低)
        'at_bot': 0.15,             # @机器人 +0.15 (大幅降低)
        'reply_bot': 0.1,           # 回复机器人 +0.1 (大幅降低)
        'active_chat': 0.25,        # 主动聊天(间隔>1小时) +0.25 (大幅降低)
        'continuous_chat': 0.15,    # 连续聊天(5分钟内) +0.15 (大幅降低)
        'daily_first': 0.5,         # 每日首次聊天 +0.5 (大幅降低)
        'long_absence': -5.0,       # 长时间未聊(>30天) -5.0
        'deep_conversation': 1.0,   # 深度对话(>200字) +1.0 (降低)
        'night_chat': 0.3,          # 深夜聊天(23:00-6:00) +0.3 (降低)
        'special_keyword': 0.5,     # 特殊关键词(喜欢/爱/想你等) +0.5 (降低)
    }

    @staticmethod
    def update_on_message(
        user_id: str,
        platform: str,
        message_length: int = 0,
        message_text: str = "",
        has_emoji: bool = False,
        has_image: bool = False,
        is_at_bot: bool = False,
        is_reply_bot: bool = False
    ) -> Optional[dict]:
        """
        收到消息时更新亲密度

        参数:
            user_id: 用户ID
            platform: 平台
            message_length: 消息长度
            message_text: 消息文本内容
            has_emoji: 是否包含表情包
            has_image: 是否包含图片
            is_at_bot: 是否@机器人
            is_reply_bot: 是否回复机器人

        返回:
            更新后的用户信息字典，失败返回 None
        """
        try:
            with db:
                user = get_person_by_user_platform(user_id, platform)

                if not user:
                    logger.warning(f"用户不存在: {user_id}@{platform}")
                    return None

                current_time = time.time()
                last_chat = user.last_chat_time or 0
                old_relationship = user.relationship_value

                # 计算亲密度变化
                delta = 0.0

                # 基础消息分数
                delta += RelationshipUpdater.RULES['normal_message']

                # 长消息加分
                if message_length > 50:
                    delta += RelationshipUpdater.RULES['long_message']

                # 深度对话加分（超长消息）
                if message_length > 200:
                    delta += RelationshipUpdater.RULES['deep_conversation']

                # 表情包加分
                if has_emoji:
                    delta += RelationshipUpdater.RULES['emoji_message']

                # 图片加分
                if has_image:
                    delta += RelationshipUpdater.RULES['image_message']

                # @机器人加分
                if is_at_bot:
                    delta += RelationshipUpdater.RULES['at_bot']

                # 回复机器人加分
                if is_reply_bot:
                    delta += RelationshipUpdater.RULES['reply_bot']

                # 主动聊天加分（间隔>1小时）
                if current_time - last_chat > 3600:
                    delta += RelationshipUpdater.RULES['active_chat']

                # 连续聊天加分（5分钟内）
                if 0 < current_time - last_chat < 300:
                    delta += RelationshipUpdater.RULES['continuous_chat']

                # 每日首次聊天加分
                if RelationshipUpdater._is_new_day(last_chat, current_time):
                    delta += RelationshipUpdater.RULES['daily_first']

                # 深夜聊天加分（23:00-6:00）
                if RelationshipUpdater._is_night_time(current_time):
                    delta += RelationshipUpdater.RULES['night_chat']

                # 特殊关键词加分
                if RelationshipUpdater._has_special_keywords(message_text):
                    delta += RelationshipUpdater.RULES['special_keyword']

                # 亲密度越高，提升越困难（递减系数）
                difficulty_factor = RelationshipUpdater._get_difficulty_factor(user.relationship_value)
                delta *= difficulty_factor

                # 应用心情倍率
                from src.common.mood_system import MoodSystem
                mood_multiplier = MoodSystem.get_mood_multiplier(user.mood_value)
                delta *= mood_multiplier

                # 更新用户数据
                new_relationship = min(100, max(0, user.relationship_value + delta))
                user.relationship_value = new_relationship
                user.total_messages += 1
                user.last_chat_time = current_time

                # 更新首次见面时间
                if not user.first_meet_time:
                    user.first_meet_time = current_time

                # 重新计算聊天频率
                if user.first_meet_time:
                    time_span_days = (current_time - user.first_meet_time) / 86400
                    if time_span_days < 1:
                        time_span_days = 1
                    user.chat_frequency = user.total_messages / time_span_days

                # 更新互动评分
                user.interaction_score = RelationshipUpdater._calculate_interaction_score(user)

                user.save()

                # 获取旧的和新的关系等级
                old_level = RelationshipUpdater.get_relationship_level(old_relationship)
                new_level = RelationshipUpdater.get_relationship_level(new_relationship)

                # 检查是否触发表白（亲密度达到100）
                confession_triggered = False
                if new_relationship >= 100 and old_relationship < 100:
                    confession_triggered = True
                    logger.info(f"💕 [重大变故] 触发表白！用户: {user.nickname or user_id} (亲密度: {old_relationship:.1f} -> {new_relationship:.1f})")

                # 记录重大变故
                # 1. 关系等级变化
                if old_level != new_level:
                    logger.info(f"🔄 [重大变故] 关系等级变化: {user.nickname or user_id} ({old_level} -> {new_level}, 亲密度: {old_relationship:.1f} -> {new_relationship:.1f})")

                # 2. 亲密度大幅变化（一次变化超过5分）
                elif abs(delta) >= 5.0:
                    direction = "上升" if delta > 0 else "下降"
                    logger.info(f"📊 [重大变故] 亲密度大幅{direction}: {user.nickname or user_id} ({old_relationship:.1f} -> {new_relationship:.1f}, Δ{delta:+.2f})")

                # 3. 关系破裂（亲密度降到0或负数）
                elif new_relationship <= 0 and old_relationship > 0:
                    logger.warning(f"💔 [重大变故] 关系破裂！用户: {user.nickname or user_id} (亲密度: {old_relationship:.1f} -> {new_relationship:.1f})")

                # 普通日志（调试级别）
                else:
                    logger.debug(
                        f"更新亲密度: {user.nickname or user_id} "
                        f"({old_relationship:.1f} -> {new_relationship:.1f}, Δ{delta:+.2f})"
                    )

                return {
                    'user_id': user.user_id,
                    'nickname': user.nickname,
                    'relationship_value': new_relationship,
                    'old_relationship_value': old_relationship,
                    'delta': delta,
                    'total_messages': user.total_messages,
                    'chat_frequency': user.chat_frequency,
                    'interaction_score': user.interaction_score,
                    'level': RelationshipUpdater.get_relationship_level(new_relationship),
                    'confession_triggered': confession_triggered  # 是否触发表白
                }

        except Exception as e:
            logger.error(f"更新亲密度失败: {e}")
            return None

    @staticmethod
    def check_and_decay(user_id: str, platform: str) -> bool:
        """
        检查并衰减长时间未聊天用户的亲密度

        衰减规则：
        - 7-14天：-0.5/天（轻微衰减）
        - 14-30天：-1.0/天（中度衰减）
        - 30天以上：-2.0/天（重度衰减）
        - 高亲密度（80+）衰减速度 x1.5

        返回: 是否进行了衰减
        """
        try:
            with db:
                user = get_person_by_user_platform(user_id, platform)

                if not user or not user.last_chat_time:
                    return False

                current_time = time.time()
                days_since_last = (current_time - user.last_chat_time) / 86400

                # 少于7天不衰减
                if days_since_last < 7:
                    return False

                old_value = user.relationship_value

                # 计算衰减值
                decay_per_day = 0.0
                if days_since_last < 14:
                    decay_per_day = -0.5  # 轻微衰减
                elif days_since_last < 30:
                    decay_per_day = -1.0  # 中度衰减
                else:
                    decay_per_day = -2.0  # 重度衰减

                # 高亲密度衰减更快
                if old_value >= 80:
                    decay_per_day *= 1.5

                # 计算总衰减（从上次聊天到现在）
                total_decay = decay_per_day * days_since_last

                # 应用衰减
                new_value = max(0, old_value + total_decay)
                user.relationship_value = new_value

                # 衰减也会影响心情
                if total_decay < -5:
                    user.mood_value = max(0, user.mood_value - 10)

                user.save()

                # 记录衰减
                decay_level = "轻微" if days_since_last < 14 else "中度" if days_since_last < 30 else "重度"
                logger.warning(
                    f"⏰ [重大变故] 亲密度衰减({decay_level}): {user.nickname or user_id} "
                    f"({old_value:.1f} -> {new_value:.1f}, {total_decay:.1f}) "
                    f"已{days_since_last:.0f}天未聊天"
                )
                return True

        except Exception as e:
            logger.error(f"检查亲密度衰减失败: {e}")
            return False

    @staticmethod
    def get_relationship_level(value: float) -> str:
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

    @staticmethod
    def get_reply_style(relationship_value: float) -> dict:
        """
        根据亲密度返回回复风格建议

        返回:
        {
            'tone': str,           # 语气 (formal/friendly/intimate)
            'emoji_rate': float,   # 表情使用率 (0-1)
            'length': str,         # 回复长度 (short/medium/long)
            'formality': float     # 正式程度 (0-1)
        }
        """
        if relationship_value >= 80:
            return {
                'tone': 'intimate',
                'emoji_rate': 0.8,
                'length': 'long',
                'formality': 0.2,
                'description': '亲密朋友，可以开玩笑、使用昵称、多用表情'
            }
        elif relationship_value >= 60:
            return {
                'tone': 'friendly',
                'emoji_rate': 0.6,
                'length': 'medium',
                'formality': 0.4,
                'description': '好友，友好热情、适当使用表情'
            }
        elif relationship_value >= 40:
            return {
                'tone': 'friendly',
                'emoji_rate': 0.4,
                'length': 'medium',
                'formality': 0.6,
                'description': '熟人，礼貌友好、少量表情'
            }
        elif relationship_value >= 20:
            return {
                'tone': 'formal',
                'emoji_rate': 0.2,
                'length': 'short',
                'formality': 0.8,
                'description': '初识，保持礼貌、较为正式'
            }
        else:
            return {
                'tone': 'formal',
                'emoji_rate': 0.1,
                'length': 'short',
                'formality': 0.9,
                'description': '陌生人，正式礼貌、简洁回复'
            }

    @staticmethod
    def _is_new_day(last_time: float, current_time: float) -> bool:
        """判断是否是新的一天"""
        from datetime import datetime
        last_date = datetime.fromtimestamp(last_time).date()
        current_date = datetime.fromtimestamp(current_time).date()
        return last_date != current_date

    @staticmethod
    def _is_night_time(timestamp: float) -> bool:
        """判断是否是深夜时间（23:00-6:00）"""
        from datetime import datetime
        hour = datetime.fromtimestamp(timestamp).hour
        return hour >= 23 or hour < 6

    @staticmethod
    def _has_special_keywords(text: str) -> bool:
        """检测消息中是否包含特殊关键词"""
        if not text:
            return False

        special_keywords = [
            '喜欢', '爱', '想你', '想念', '思念', '在乎',
            '陪伴', '陪你', '永远', '一直', '一生',
            '心动', '心跳', '温柔', '可爱', '最好',
            '宝贝', '亲爱的', '小可爱', '小宝贝'
        ]

        text_lower = text.lower()
        return any(keyword in text_lower for keyword in special_keywords)

    @staticmethod
    def _get_difficulty_factor(current_relationship: float) -> float:
        """
        根据当前亲密度返回难度系数（越高越难提升，后期普通消息几乎无效）

        0-20: 1.0 (正常速度)
        20-40: 0.8
        40-60: 0.5
        60-80: 0.25 (普通消息效果减半)
        80-90: 0.1 (普通消息几乎无效)
        90-95: 0.05 (需要深度互动)
        95-100: 0.01 (极难提升，只有特殊事件有效)
        """
        if current_relationship < 20:
            return 1.0
        elif current_relationship < 40:
            return 0.8
        elif current_relationship < 60:
            return 0.5
        elif current_relationship < 80:
            return 0.25  # 普通消息效果大幅降低
        elif current_relationship < 90:
            return 0.1   # 普通消息几乎无效
        elif current_relationship < 95:
            return 0.05  # 需要深度互动
        else:
            return 0.01  # 极难提升

    @staticmethod
    def _calculate_interaction_score(user: PersonInfo) -> float:
        """计算综合互动评分"""
        # 消息数量分 (0-4分)
        msg_score = min(4, user.total_messages / 100)

        # 聊天频率分 (0-3分)
        freq_score = min(3, user.chat_frequency / 2)

        # 亲密度分 (0-3分)
        rel_score = user.relationship_value / 100 * 3

        return round(msg_score + freq_score + rel_score, 2)


# 使用示例
if __name__ == "__main__":
    # 模拟收到消息时更新亲密度
    result = RelationshipUpdater.update_on_message(
        user_id="123456",
        platform="qq",
        message_length=60,
        has_emoji=True,
        is_at_bot=True
    )

    if result:
        print(f"用户: {result['nickname']}")
        print(f"亲密度: {result['relationship_value']} ({result['level']})")
        print(f"总消息: {result['total_messages']}")

        # 获取回复风格建议
        style = RelationshipUpdater.get_reply_style(result['relationship_value'])
        print(f"\n回复风格: {style['description']}")
        print(f"语气: {style['tone']}")
        print(f"表情使用率: {style['emoji_rate']*100}%")
