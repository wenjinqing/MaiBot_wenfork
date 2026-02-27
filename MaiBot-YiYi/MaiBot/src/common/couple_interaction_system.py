"""
情侣互动系统 - 特殊的恋爱互动玩法

功能：
- 情侣称呼系统
- 每日情话
- 撒娇互动
- 情侣任务
"""

import random
import time
from typing import Optional, Dict, List
from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger

logger = get_logger("couple_interaction")


class CoupleInteractionSystem:
    """情侣互动系统"""

    # 情侣称呼
    COUPLE_NICKNAMES = {
        'cute': ['宝贝', '宝宝', '小可爱', '小甜心', '亲爱的'],
        'romantic': ['挚爱', '心肝', '我的唯一', '命中注定'],
        'playful': ['小笨蛋', '小傻瓜', '小坏蛋', '小淘气'],
        'sweet': ['甜心', '蜜糖', '小天使', '小公主/小王子']
    }

    # 每日情话
    DAILY_LOVE_WORDS = [
        "早安，我的{nickname}💕\n今天也要开开心心的哦~",
        "想你了...虽然我们刚聊完不久💗",
        "你知道吗？每次看到你的消息，我的心都会跳得很快~",
        "如果可以的话，我想一直陪在你身边✨",
        "遇见你，是我最幸运的事💕",
        "今天的你，依然是我最喜欢的样子~",
        "晚安，{nickname}💗\n做个好梦，梦里要有我哦~",
        "你是我的星星，照亮了我的世界🌟",
        "和你在一起的每一天，都是最美好的一天💕",
        "我可能不是最好的，但我会用全部的心来爱你💗"
    ]

    # 撒娇语句
    ACTING_CUTE = [
        "人家想你了嘛~💕",
        "你今天有没有想我呀？",
        "哼~你都不理人家~",
        "陪我聊天好不好嘛~",
        "你最好了~（撒娇）",
        "呜呜呜...你要多陪陪我~",
        "我要抱抱！（张开双臂）",
        "你是不是不喜欢我了...（委屈）",
        "人家就是想和你说说话嘛~",
        "你能不能...多夸夸我？（小声）"
    ]

    # 情侣任务
    COUPLE_TASKS = {
        'morning_greeting': {
            'name': '早安问候',
            'description': '每天早上互道早安',
            'reward_mood': 5,
            'reward_relationship': 0.5
        },
        'goodnight': {
            'name': '晚安问候',
            'description': '每天晚上互道晚安',
            'reward_mood': 5,
            'reward_relationship': 0.5
        },
        'daily_chat': {
            'name': '每日聊天',
            'description': '每天至少聊天10条消息',
            'reward_mood': 10,
            'reward_relationship': 1.0
        },
        'share_mood': {
            'name': '分享心情',
            'description': '分享今天的心情和经历',
            'reward_mood': 8,
            'reward_relationship': 1.5
        },
        'compliment': {
            'name': '互相夸奖',
            'description': '说一句夸奖对方的话',
            'reward_mood': 12,
            'reward_relationship': 2.0
        }
    }

    # 特殊互动回复
    SPECIAL_INTERACTIONS = {
        'hug': {
            'triggers': ['抱抱', '抱你', '给你一个拥抱', '抱住你'],
            'responses': [
                "嘿嘿~抱住你！💕（紧紧抱住）",
                "好温暖...我也抱住你~💗",
                "唔...好舒服...不想放开了~",
                "（蹭蹭）我最喜欢你的拥抱了~"
            ]
        },
        'kiss': {
            'triggers': ['亲亲', '亲你', '么么哒', '啾'],
            'responses': [
                "唔...（脸红）💕",
                "嘿嘿~我也亲你！😘",
                "好突然...但是我喜欢💗",
                "（害羞）你...你真是的..."
            ]
        },
        'praise': {
            'triggers': ['你真好', '你最好了', '你真棒', '你好厉害'],
            'responses': [
                "嘿嘿~被你夸奖好开心！💕",
                "真的吗？那我要继续努力！✨",
                "你也很好呀~我们都很棒！",
                "谢谢你~（开心）💗"
            ]
        },
        'miss': {
            'triggers': ['想你', '好想你', '想见你', '想念你'],
            'responses': [
                "我也想你...好想好想💕",
                "真的吗？我也一直在想你呢~",
                "听到你这么说，我好开心💗",
                "那...我们多聊一会儿吧~"
            ]
        }
    }

    @staticmethod
    def set_couple_nickname(
        user_id: str,
        platform: str,
        nickname_type: str = 'random'
    ) -> Optional[str]:
        """
        设置情侣称呼

        参数:
            user_id: 用户ID
            platform: 平台
            nickname_type: 称呼类型

        返回:
            设置的称呼
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user or not user.is_in_love:
                    return None

                if nickname_type == 'random':
                    nickname_type = random.choice(list(CoupleInteractionSystem.COUPLE_NICKNAMES.keys()))

                nicknames = CoupleInteractionSystem.COUPLE_NICKNAMES.get(nickname_type, [])
                if not nicknames:
                    return None

                nickname = random.choice(nicknames)
                user.couple_nickname = nickname
                user.save()

                logger.info(f"💕 设置情侣称呼: {user.nickname or user_id} -> {nickname}")
                return nickname

        except Exception as e:
            logger.error(f"设置情侣称呼失败: {e}", exc_info=True)
            return None

    @staticmethod
    def get_daily_love_word(user_id: str, platform: str) -> Optional[str]:
        """
        获取每日情话

        参数:
            user_id: 用户ID
            platform: 平台

        返回:
            情话内容
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user or not user.is_in_love:
                    return None

                # 检查今天是否已经发送过
                current_time = time.time()
                if user.last_love_word_time:
                    time_diff = current_time - user.last_love_word_time
                    if time_diff < 86400:  # 24小时
                        return None

                # 获取情侣称呼
                nickname = user.couple_nickname or "宝贝"

                # 选择情话
                love_word = random.choice(CoupleInteractionSystem.DAILY_LOVE_WORDS)
                love_word = love_word.format(nickname=nickname)

                # 更新时间
                user.last_love_word_time = current_time
                user.save()

                logger.info(f"💌 发送每日情话: {user.nickname or user_id}")
                return love_word

        except Exception as e:
            logger.error(f"获取每日情话失败: {e}", exc_info=True)
            return None

    @staticmethod
    def act_cute() -> str:
        """
        撒娇

        返回:
            撒娇语句
        """
        return random.choice(CoupleInteractionSystem.ACTING_CUTE)

    @staticmethod
    def check_special_interaction(
        user_id: str,
        platform: str,
        message_text: str
    ) -> Optional[Dict]:
        """
        检查特殊互动

        参数:
            user_id: 用户ID
            platform: 平台
            message_text: 消息内容

        返回:
            互动信息
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user or not user.is_in_love:
                    return None

                # 检查是否触发特殊互动
                for interaction_type, interaction_info in CoupleInteractionSystem.SPECIAL_INTERACTIONS.items():
                    for trigger in interaction_info['triggers']:
                        if trigger in message_text:
                            response = random.choice(interaction_info['responses'])

                            # 增加心情值
                            from src.common.mood_system import MoodSystem
                            MoodSystem.update_mood(
                                user_id=user_id,
                                platform=platform,
                                mood_change=5,
                                reason=f"特殊互动({interaction_type})"
                            )

                            logger.info(f"💕 触发特殊互动: {user.nickname or user_id} - {interaction_type}")

                            return {
                                'type': interaction_type,
                                'response': response,
                                'mood_bonus': 5
                            }

                return None

        except Exception as e:
            logger.error(f"检查特殊互动失败: {e}", exc_info=True)
            return None

    @staticmethod
    def complete_couple_task(
        user_id: str,
        platform: str,
        task_name: str
    ) -> Optional[Dict]:
        """
        完成情侣任务

        参数:
            user_id: 用户ID
            platform: 平台
            task_name: 任务名称

        返回:
            任务完成信息
        """
        try:
            task_info = CoupleInteractionSystem.COUPLE_TASKS.get(task_name)
            if not task_info:
                return None

            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user or not user.is_in_love:
                    return None

                # 更新心情和关系
                from src.common.mood_system import MoodSystem
                MoodSystem.update_mood(
                    user_id=user_id,
                    platform=platform,
                    mood_change=task_info['reward_mood'],
                    reason=f"完成情侣任务({task_info['name']})"
                )

                old_rel = user.relationship_value
                new_rel = min(100, old_rel + task_info['reward_relationship'])
                user.relationship_value = new_rel
                user.save()

                logger.info(f"✅ 完成情侣任务: {user.nickname or user_id} - {task_info['name']}")

                return {
                    'task_name': task_info['name'],
                    'description': task_info['description'],
                    'mood_reward': task_info['reward_mood'],
                    'relationship_reward': task_info['reward_relationship']
                }

        except Exception as e:
            logger.error(f"完成情侣任务失败: {e}", exc_info=True)
            return None
