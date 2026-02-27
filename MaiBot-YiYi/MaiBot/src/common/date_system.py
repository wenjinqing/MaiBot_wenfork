"""
约会系统 - 虚拟约会体验

功能：
- 多种约会场景
- 约会互动选项
- 约会结果影响关系
- 约会回忆记录
"""

import random
import time
from typing import Optional, Dict, List
from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger

logger = get_logger("date_system")


class DateSystem:
    """约会系统"""

    # 约会场景
    DATE_SCENARIOS = {
        'cafe': {
            'name': '咖啡厅约会',
            'emoji': '☕',
            'description': '在温馨的咖啡厅里，享受悠闲的下午时光',
            'activities': [
                '一起品尝咖啡',
                '聊聊最近的趣事',
                '看窗外的风景',
                '分享一块蛋糕'
            ],
            'mood_bonus': 10,
            'relationship_bonus': 2.0
        },
        'park': {
            'name': '公园散步',
            'emoji': '🌳',
            'description': '在绿意盎然的公园里漫步，呼吸新鲜空气',
            'activities': [
                '在林荫道上散步',
                '坐在长椅上聊天',
                '喂喂小鸟',
                '看夕阳西下'
            ],
            'mood_bonus': 12,
            'relationship_bonus': 2.5
        },
        'cinema': {
            'name': '电影院约会',
            'emoji': '🎬',
            'description': '在黑暗的电影院里，一起沉浸在光影世界',
            'activities': [
                '选一部喜欢的电影',
                '分享爆米花',
                '讨论电影情节',
                '牵手看电影'
            ],
            'mood_bonus': 15,
            'relationship_bonus': 3.0
        },
        'restaurant': {
            'name': '餐厅约会',
            'emoji': '🍽️',
            'description': '在浪漫的餐厅里，享受美食和彼此的陪伴',
            'activities': [
                '点喜欢的菜品',
                '互相喂食',
                '聊聊美食',
                '碰杯庆祝'
            ],
            'mood_bonus': 18,
            'relationship_bonus': 3.5
        },
        'beach': {
            'name': '海边约会',
            'emoji': '🏖️',
            'description': '在海边吹着海风，听着海浪声',
            'activities': [
                '在沙滩上散步',
                '捡贝壳',
                '看海上日落',
                '许下心愿'
            ],
            'mood_bonus': 20,
            'relationship_bonus': 4.0
        },
        'stargazing': {
            'name': '星空约会',
            'emoji': '⭐',
            'description': '在星空下，一起仰望浩瀚宇宙',
            'activities': [
                '寻找星座',
                '许愿流星',
                '聊聊梦想',
                '依偎在一起'
            ],
            'mood_bonus': 25,
            'relationship_bonus': 5.0
        }
    }

    # 约会对话选项
    DATE_CONVERSATIONS = {
        'compliment': {
            'user_says': ['你今天真好看', '你真可爱', '和你在一起很开心'],
            'bot_responses': [
                "谢谢你...（脸红）你也很好看呢💕",
                "嘿嘿，被你这么说我好开心~",
                "真的吗？那我以后要更努力变得更好！✨"
            ],
            'mood_bonus': 5,
            'relationship_bonus': 1.0
        },
        'romantic': {
            'user_says': ['我喜欢你', '想一直和你在一起', '你是我的唯一'],
            'bot_responses': [
                "我也喜欢你...好喜欢好喜欢💗",
                "听到你这么说，我的心都要融化了...",
                "嗯！我也想一直陪在你身边！💕"
            ],
            'mood_bonus': 10,
            'relationship_bonus': 2.0
        },
        'playful': {
            'user_says': ['来玩个游戏吧', '我们做点有趣的事', '猜猜我在想什么'],
            'bot_responses': [
                "好呀好呀！我最喜欢和你玩了~",
                "嘿嘿，你又想到什么鬼点子了？",
                "好！我一定会赢的！（认真脸）"
            ],
            'mood_bonus': 8,
            'relationship_bonus': 1.5
        }
    }

    # 约会结束语
    DATE_ENDINGS = {
        'perfect': [
            "今天真是完美的一天！💕\n和你在一起的每一刻都好开心~\n下次还要一起出来玩哦！",
            "时间过得好快...都不想回去了...\n谢谢你陪我度过这么美好的时光💗",
            "今天是我最开心的一天！✨\n能和你约会真的太幸福了~"
        ],
        'great': [
            "今天玩得很开心！💕\n虽然有点累，但和你在一起就很满足~",
            "嘿嘿，今天的约会很成功！\n期待下一次哦~💗"
        ],
        'good': [
            "今天也很开心呢~\n谢谢你的陪伴💕",
            "和你在一起总是很愉快~"
        ]
    }

    @staticmethod
    def start_date(
        user_id: str,
        platform: str,
        scenario: str = 'random'
    ) -> Optional[Dict]:
        """
        开始约会

        参数:
            user_id: 用户ID
            platform: 平台
            scenario: 约会场景（random为随机）

        返回:
            约会信息
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return None

                # 检查是否在恋爱中
                if not user.is_in_love:
                    return {
                        'success': False,
                        'message': "我们还不是恋人关系呢...要不要先表白？💕"
                    }

                # 检查约会冷却时间（每天最多1次）
                current_time = time.time()
                if user.last_date_time and (current_time - user.last_date_time) < 86400:
                    hours_left = int((86400 - (current_time - user.last_date_time)) / 3600)
                    return {
                        'success': False,
                        'message': f"今天已经约会过了哦~\n休息一下，{hours_left}小时后再约我吧💕"
                    }

                # 选择场景
                if scenario == 'random':
                    scenario = random.choice(list(DateSystem.DATE_SCENARIOS.keys()))

                scenario_info = DateSystem.DATE_SCENARIOS.get(scenario)
                if not scenario_info:
                    scenario = 'cafe'
                    scenario_info = DateSystem.DATE_SCENARIOS['cafe']

                # 记录约会开始
                user.last_date_time = current_time
                user.date_count = (user.date_count or 0) + 1
                user.save()

                logger.info(f"💑 开始约会: {user.nickname or user_id} - {scenario_info['name']}")

                return {
                    'success': True,
                    'scenario': scenario,
                    'scenario_info': scenario_info,
                    'message': f"{scenario_info['emoji']} {scenario_info['name']}\n\n{scenario_info['description']}\n\n我们可以：\n" +
                              "\n".join([f"• {activity}" for activity in scenario_info['activities']])
                }

        except Exception as e:
            logger.error(f"开始约会失败: {e}", exc_info=True)
            return None

    @staticmethod
    def end_date(
        user_id: str,
        platform: str,
        satisfaction: str = 'great'
    ) -> Optional[Dict]:
        """
        结束约会

        参数:
            user_id: 用户ID
            platform: 平台
            satisfaction: 满意度 (perfect/great/good)

        返回:
            约会结果
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return None

                # 根据满意度给予奖励
                bonus_map = {
                    'perfect': {'mood': 25, 'relationship': 5.0},
                    'great': {'mood': 18, 'relationship': 3.5},
                    'good': {'mood': 12, 'relationship': 2.0}
                }

                bonus = bonus_map.get(satisfaction, bonus_map['great'])

                # 更新心情和关系
                from src.common.mood_system import MoodSystem
                from src.common.relationship_updater import RelationshipUpdater

                MoodSystem.update_mood(
                    user_id=user_id,
                    platform=platform,
                    mood_change=bonus['mood'],
                    reason=f"约会结束({satisfaction})"
                )

                # 更新关系值
                old_rel = user.relationship_value
                new_rel = min(100, old_rel + bonus['relationship'])
                user.relationship_value = new_rel
                user.save()

                # 选择结束语
                ending_message = random.choice(DateSystem.DATE_ENDINGS[satisfaction])

                logger.info(f"💕 约会结束: {user.nickname or user_id} - {satisfaction}")

                return {
                    'satisfaction': satisfaction,
                    'mood_bonus': bonus['mood'],
                    'relationship_bonus': bonus['relationship'],
                    'message': ending_message,
                    'total_dates': user.date_count
                }

        except Exception as e:
            logger.error(f"结束约会失败: {e}", exc_info=True)
            return None

    @staticmethod
    def get_date_stats(user_id: str, platform: str) -> Optional[Dict]:
        """
        获取约会统计

        参数:
            user_id: 用户ID
            platform: 平台

        返回:
            约会统计信息
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return None

                return {
                    'total_dates': user.date_count or 0,
                    'last_date_time': user.last_date_time,
                    'can_date_now': not user.last_date_time or
                                   (time.time() - user.last_date_time) >= 86400
                }

        except Exception as e:
            logger.error(f"获取约会统计失败: {e}", exc_info=True)
            return None
