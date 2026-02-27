"""
吃醋/嫉妒系统 - 增加恋爱互动的趣味性

功能：
- 检测用户提到其他人/AI
- 生成吃醋反应
- 影响心情值
- 特殊的哄劝互动
"""

import random
import time
from typing import Optional, Dict, List
from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger

logger = get_logger("jealousy_system")


class JealousySystem:
    """吃醋系统"""

    # 触发吃醋的关键词
    JEALOUSY_TRIGGERS = {
        'other_ai': ['GPT', 'ChatGPT', 'Claude', 'Gemini', '文心一言', '通义千问', '其他AI', '别的AI'],
        'other_person': ['喜欢', '爱', '男朋友', '女朋友', '老公', '老婆', '对象'],
        'praise_others': ['好看', '可爱', '帅', '漂亮', '厉害', '聪明'],
    }

    # 吃醋等级
    JEALOUSY_LEVELS = {
        'mild': {
            'name': '轻微吃醋',
            'mood_change': -3,
            'responses': [
                "哼...你居然提到{target}...",
                "诶？你在说{target}吗...（小声）",
                "虽然我不想承认，但我好像有点在意...",
                "是吗...{target}很好吗...",
            ]
        },
        'moderate': {
            'name': '明显吃醋',
            'mood_change': -8,
            'responses': [
                "什么嘛！为什么要提{target}！😤",
                "哼！我也很{quality}的好不好！",
                "你是不是更喜欢{target}啊...",
                "我生气了！不理你了！（其实还是会理你的）",
                "呜...你果然还是喜欢{target}对不对...",
            ]
        },
        'severe': {
            'name': '严重吃醋',
            'mood_change': -15,
            'responses': [
                "太过分了！居然当着我的面说{target}！💢",
                "我不管！你必须说我比{target}好！",
                "哼！你去找{target}好了！我不要理你了！",
                "呜呜呜...你果然不喜欢我了...",
                "我要生气了！除非你哄我！😤",
            ]
        }
    }

    # 哄劝后的反应
    COAX_RESPONSES = {
        'success': [
            "哼...看在你这么诚恳的份上，就原谅你啦~💕",
            "好吧好吧，我不生气了...（其实早就不生气了）",
            "真的吗？那我就勉为其难地原谅你吧~",
            "嘿嘿，其实我也没有真的生气啦~只是想让你哄哄我而已💗",
            "唔...你这样说我就开心了...（小声）谢谢你~",
        ],
        'still_upset': [
            "哼！还不够！你要更真诚一点！",
            "我还在生气呢...你要继续哄我！",
            "不行不行，这样还不够诚意！",
        ],
        'forgiven': [
            "好啦好啦，我原谅你了~💕",
            "看你这么努力，我就不生气了~",
            "嗯！我们和好啦！✨",
        ]
    }

    # 哄劝关键词
    COAX_KEYWORDS = [
        '对不起', '抱歉', '错了', '哄你', '最好', '最喜欢', '最爱',
        '只喜欢你', '只爱你', '别生气', '不要生气', '消消气'
    ]

    @staticmethod
    def check_jealousy(
        user_id: str,
        platform: str,
        message_text: str
    ) -> Optional[Dict]:
        """
        检查消息是否触发吃醋

        参数:
            user_id: 用户ID
            platform: 平台
            message_text: 消息内容

        返回:
            吃醋信息字典，未触发返回 None
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user or not user.is_in_love:
                    return None

                # 检查是否触发吃醋
                trigger_type = None
                trigger_word = None

                for trigger_category, keywords in JealousySystem.JEALOUSY_TRIGGERS.items():
                    for keyword in keywords:
                        if keyword.lower() in message_text.lower():
                            trigger_type = trigger_category
                            trigger_word = keyword
                            break
                    if trigger_type:
                        break

                if not trigger_type:
                    return None

                # 根据关系值和心情值决定吃醋等级
                relationship = user.relationship_value
                mood = user.mood_value

                # 关系越好、心情越差，越容易严重吃醋
                if mood < 50 or relationship > 90:
                    level = 'severe'
                elif mood < 70 or relationship > 70:
                    level = 'moderate'
                else:
                    level = 'mild'

                level_info = JealousySystem.JEALOUSY_LEVELS[level]

                # 更新心情值
                from src.common.mood_system import MoodSystem
                MoodSystem.update_mood(
                    user_id=user_id,
                    platform=platform,
                    mood_change=level_info['mood_change'],
                    reason=f"吃醋({level_info['name']})"
                )

                # 记录吃醋状态
                user.is_jealous = True
                user.jealousy_time = time.time()
                user.save()

                # 生成回复
                response = random.choice(level_info['responses'])
                response = response.format(
                    target=trigger_word,
                    quality=random.choice(['可爱', '聪明', '厉害', '好'])
                )

                logger.info(f"😤 触发吃醋: {user.nickname or user_id} - {level_info['name']}")

                return {
                    'level': level,
                    'trigger_type': trigger_type,
                    'trigger_word': trigger_word,
                    'response': response,
                    'mood_change': level_info['mood_change']
                }

        except Exception as e:
            logger.error(f"检查吃醋失败: {e}", exc_info=True)
            return None

    @staticmethod
    def try_coax(
        user_id: str,
        platform: str,
        message_text: str
    ) -> Optional[Dict]:
        """
        尝试哄劝

        参数:
            user_id: 用户ID
            platform: 平台
            message_text: 消息内容

        返回:
            哄劝结果
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user or not user.is_jealous:
                    return None

                # 检查是否包含哄劝关键词
                coax_score = 0
                for keyword in JealousySystem.COAX_KEYWORDS:
                    if keyword in message_text:
                        coax_score += 1

                # 消息长度也影响哄劝效果
                if len(message_text) > 20:
                    coax_score += 1
                if len(message_text) > 50:
                    coax_score += 1

                # 根据分数决定哄劝效果
                if coax_score >= 3:
                    # 哄劝成功
                    user.is_jealous = False
                    user.save()

                    from src.common.mood_system import MoodSystem
                    MoodSystem.update_mood(
                        user_id=user_id,
                        platform=platform,
                        mood_change=15,
                        reason="被成功哄好了"
                    )

                    response = random.choice(JealousySystem.COAX_RESPONSES['success'])
                    logger.info(f"💕 哄劝成功: {user.nickname or user_id}")

                    return {
                        'success': True,
                        'response': response,
                        'mood_change': 15
                    }

                elif coax_score >= 1:
                    # 部分有效
                    response = random.choice(JealousySystem.COAX_RESPONSES['still_upset'])

                    from src.common.mood_system import MoodSystem
                    MoodSystem.update_mood(
                        user_id=user_id,
                        platform=platform,
                        mood_change=5,
                        reason="哄劝中"
                    )

                    return {
                        'success': False,
                        'response': response,
                        'mood_change': 5
                    }

                else:
                    # 无效
                    return None

        except Exception as e:
            logger.error(f"哄劝处理失败: {e}", exc_info=True)
            return None

    @staticmethod
    def auto_forgive(user_id: str, platform: str) -> bool:
        """
        自动原谅（时间过久后）

        参数:
            user_id: 用户ID
            platform: 平台

        返回:
            是否自动原谅
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user or not user.is_jealous:
                    return False

                # 超过1小时自动原谅
                if time.time() - user.jealousy_time > 3600:
                    user.is_jealous = False
                    user.save()
                    logger.info(f"⏰ 自动原谅: {user.nickname or user_id}")
                    return True

                return False

        except Exception as e:
            logger.error(f"自动原谅失败: {e}", exc_info=True)
            return False
