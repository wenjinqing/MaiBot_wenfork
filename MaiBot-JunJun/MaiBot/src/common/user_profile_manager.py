"""
用户画像系统 - MCP 工具

提供给大模型使用的工具，用于更新和管理用户印象
"""

import time
import json
from typing import Optional, Dict, List
from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger

logger = get_logger("user_profile")


class UserProfileManager:
    """用户画像管理器"""

    @staticmethod
    def update_user_impression(
        user_id: str,
        platform: str,
        impression: str,
        confidence: float = 0.8,
        source: str = "conversation"
    ) -> Optional[Dict]:
        """
        更新用户印象

        参数:
            user_id: 用户ID
            platform: 平台
            impression: 新的印象描述
            confidence: 置信度 (0-1)，表示这个印象的可靠程度
            source: 印象来源 (conversation/behavior/long_term等)

        返回:
            {
                'success': bool,
                'user_id': str,
                'nickname': str,
                'old_impression': str,
                'new_impression': str,
                'impression_updated': bool
            }
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

                old_impression = user.memory_points or ""

                # 如果置信度高，直接更新
                if confidence >= 0.8:
                    user.memory_points = impression
                    impression_updated = True
                # 如果置信度中等，追加到现有印象
                elif confidence >= 0.5:
                    if old_impression:
                        user.memory_points = f"{old_impression}\n\n[新增印象] {impression}"
                    else:
                        user.memory_points = impression
                    impression_updated = True
                else:
                    # 置信度太低，不更新
                    impression_updated = False

                if impression_updated:
                    user.last_know = time.time()
                    user.save()

                    logger.info(
                        f"📝 更新用户印象: {user.nickname or user_id} "
                        f"(置信度: {confidence:.2f}, 来源: {source})"
                    )

                return {
                    'success': True,
                    'user_id': user_id,
                    'nickname': user.nickname,
                    'old_impression': old_impression,
                    'new_impression': user.memory_points,
                    'impression_updated': impression_updated,
                    'confidence': confidence
                }

        except Exception as e:
            logger.error(f"更新用户印象失败: {e}", exc_info=True)
            return None

    @staticmethod
    def add_user_tag(
        user_id: str,
        platform: str,
        tag: str,
        category: str = "general"
    ) -> Optional[Dict]:
        """
        添加用户标签

        参数:
            user_id: 用户ID
            platform: 平台
            tag: 标签名称
            category: 标签分类 (personality/interest/behavior/relationship等)

        返回:
            {
                'success': bool,
                'tags': List[str],
                'tag_added': bool
            }
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return None

                # 解析现有标签
                if user.special_tags:
                    try:
                        tags_data = json.loads(user.special_tags)
                        if not isinstance(tags_data, dict):
                            tags_data = {'general': tags_data if isinstance(tags_data, list) else []}
                    except:
                        tags_data = {'general': []}
                else:
                    tags_data = {'general': []}

                # 添加新标签
                if category not in tags_data:
                    tags_data[category] = []

                if tag not in tags_data[category]:
                    tags_data[category].append(tag)
                    tag_added = True
                else:
                    tag_added = False

                # 保存
                user.special_tags = json.dumps(tags_data, ensure_ascii=False)
                user.save()

                logger.info(f"🏷️ 添加用户标签: {user.nickname or user_id} - {category}:{tag}")

                return {
                    'success': True,
                    'tags': tags_data,
                    'tag_added': tag_added,
                    'category': category,
                    'tag': tag
                }

        except Exception as e:
            logger.error(f"添加用户标签失败: {e}", exc_info=True)
            return None

    @staticmethod
    def get_user_profile(
        user_id: str,
        platform: str
    ) -> Optional[Dict]:
        """
        获取完整的用户画像

        返回:
            {
                'user_id': str,
                'nickname': str,
                'person_name': str,
                'relationship_value': float,
                'relationship_level': str,
                'total_messages': int,
                'chat_frequency': float,
                'impression': str,
                'tags': dict,
                'is_in_love': bool,
                'mood_value': int,
                'first_meet_time': float,
                'last_chat_time': float,
                'days_known': int
            }
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return None

                # 解析标签
                tags = {}
                if user.special_tags:
                    try:
                        tags = json.loads(user.special_tags)
                    except:
                        tags = {'general': []}

                # 计算认识天数
                days_known = 0
                if user.first_meet_time:
                    days_known = int((time.time() - user.first_meet_time) / 86400)

                # 获取关系等级
                from src.common.relationship_updater import RelationshipUpdater
                level = RelationshipUpdater.get_relationship_level(user.relationship_value)

                return {
                    'user_id': user.user_id,
                    'nickname': user.nickname,
                    'person_name': user.person_name,
                    'relationship_value': user.relationship_value,
                    'relationship_level': level,
                    'total_messages': user.total_messages,
                    'chat_frequency': user.chat_frequency,
                    'impression': user.memory_points or "",
                    'tags': tags,
                    'is_in_love': user.is_in_love,
                    'mood_value': user.mood_value,
                    'first_meet_time': user.first_meet_time,
                    'last_chat_time': user.last_chat_time,
                    'days_known': days_known,
                    'is_known': user.is_known
                }

        except Exception as e:
            logger.error(f"获取用户画像失败: {e}", exc_info=True)
            return None

    @staticmethod
    def set_user_name(
        user_id: str,
        platform: str,
        name: str,
        reason: str = ""
    ) -> Optional[Dict]:
        """
        设置用户的特殊称呼

        参数:
            user_id: 用户ID
            platform: 平台
            name: 称呼名称
            reason: 设置原因

        返回:
            {
                'success': bool,
                'old_name': str,
                'new_name': str
            }
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return None

                old_name = user.person_name
                user.person_name = name
                user.name_reason = reason
                user.is_known = True
                user.save()

                logger.info(f"📛 设置用户称呼: {user.nickname or user_id} -> {name} (原因: {reason})")

                return {
                    'success': True,
                    'old_name': old_name,
                    'new_name': name,
                    'reason': reason
                }

        except Exception as e:
            logger.error(f"设置用户称呼失败: {e}", exc_info=True)
            return None


# MCP 工具定义

def mcp_update_user_impression(
    user_id: str,
    platform: str,
    impression: str,
    confidence: float = 0.8
) -> Dict:
    """
    MCP 工具：更新用户印象

    大模型可以调用此工具来记录对用户的印象

    参数:
        user_id: 用户ID
        platform: 平台
        impression: 印象描述（简洁的文字描述）
        confidence: 置信度 (0-1)
            - 0.9-1.0: 非常确定（基于多次互动）
            - 0.7-0.9: 比较确定（基于明确的行为）
            - 0.5-0.7: 一般确定（基于推测）
            - <0.5: 不确定（不会更新）

    返回:
        {
            'success': bool,
            'impression_updated': bool,
            'message': str
        }

    示例:
        # 用户表现出对游戏的兴趣
        result = mcp_update_user_impression(
            user_id="123456",
            platform="qq",
            impression="喜欢玩游戏，特别是FPS类游戏。经常提到《三角洲行动》。",
            confidence=0.9
        )

        # 用户性格温和
        result = mcp_update_user_impression(
            user_id="123456",
            platform="qq",
            impression="性格温和，说话礼貌，很少发脾气。",
            confidence=0.8
        )
    """
    result = UserProfileManager.update_user_impression(
        user_id=user_id,
        platform=platform,
        impression=impression,
        confidence=confidence
    )

    if result and result['impression_updated']:
        return {
            'success': True,
            'impression_updated': True,
            'message': f"已更新对 {result['nickname'] or user_id} 的印象"
        }
    elif result:
        return {
            'success': True,
            'impression_updated': False,
            'message': f"置信度不足，未更新印象"
        }
    else:
        return {
            'success': False,
            'impression_updated': False,
            'message': "更新失败"
        }


def mcp_add_user_tag(
    user_id: str,
    platform: str,
    tag: str,
    category: str = "general"
) -> Dict:
    """
    MCP 工具：添加用户标签

    大模型可以调用此工具来给用户打标签

    参数:
        user_id: 用户ID
        platform: 平台
        tag: 标签名称
        category: 标签分类
            - personality: 性格特征（温和、活泼、内向等）
            - interest: 兴趣爱好（游戏、动漫、音乐等）
            - behavior: 行为特征（话痨、夜猫子、早起等）
            - relationship: 关系特征（好友、熟人、陌生人等）
            - general: 通用标签

    返回:
        {
            'success': bool,
            'tag_added': bool,
            'message': str
        }

    示例:
        # 添加性格标签
        mcp_add_user_tag(
            user_id="123456",
            platform="qq",
            tag="温和",
            category="personality"
        )

        # 添加兴趣标签
        mcp_add_user_tag(
            user_id="123456",
            platform="qq",
            tag="游戏爱好者",
            category="interest"
        )

        # 添加行为标签
        mcp_add_user_tag(
            user_id="123456",
            platform="qq",
            tag="夜猫子",
            category="behavior"
        )
    """
    result = UserProfileManager.add_user_tag(
        user_id=user_id,
        platform=platform,
        tag=tag,
        category=category
    )

    if result and result['tag_added']:
        return {
            'success': True,
            'tag_added': True,
            'message': f"已为用户添加标签: {category}:{tag}"
        }
    elif result:
        return {
            'success': True,
            'tag_added': False,
            'message': "标签已存在"
        }
    else:
        return {
            'success': False,
            'tag_added': False,
            'message': "添加失败"
        }


def mcp_get_user_profile(
    user_id: str,
    platform: str
) -> Dict:
    """
    MCP 工具：获取用户画像

    大模型可以调用此工具来查看用户的完整画像

    参数:
        user_id: 用户ID
        platform: 平台

    返回:
        {
            'success': bool,
            'profile': {
                'nickname': str,
                'person_name': str,
                'relationship_level': str,
                'relationship_value': float,
                'impression': str,
                'tags': dict,
                'is_in_love': bool,
                'days_known': int,
                'total_messages': int
            }
        }

    示例:
        profile = mcp_get_user_profile(
            user_id="123456",
            platform="qq"
        )

        if profile['success']:
            print(f"昵称: {profile['profile']['nickname']}")
            print(f"关系: {profile['profile']['relationship_level']}")
            print(f"印象: {profile['profile']['impression']}")
            print(f"标签: {profile['profile']['tags']}")
    """
    result = UserProfileManager.get_user_profile(
        user_id=user_id,
        platform=platform
    )

    if result:
        return {
            'success': True,
            'profile': result
        }
    else:
        return {
            'success': False,
            'profile': None
        }


def mcp_set_user_name(
    user_id: str,
    platform: str,
    name: str,
    reason: str = ""
) -> Dict:
    """
    MCP 工具：设置用户称呼

    大模型可以调用此工具来给用户设置特殊的称呼

    参数:
        user_id: 用户ID
        platform: 平台
        name: 称呼名称
        reason: 设置原因

    返回:
        {
            'success': bool,
            'message': str
        }

    示例:
        # 用户自我介绍叫"小明"
        mcp_set_user_name(
            user_id="123456",
            platform="qq",
            name="小明",
            reason="用户自我介绍"
        )

        # 根据互动给用户起昵称
        mcp_set_user_name(
            user_id="123456",
            platform="qq",
            name="游戏大神",
            reason="用户游戏技术很好"
        )
    """
    result = UserProfileManager.set_user_name(
        user_id=user_id,
        platform=platform,
        name=name,
        reason=reason
    )

    if result:
        return {
            'success': True,
            'message': f"已设置称呼: {name}"
        }
    else:
        return {
            'success': False,
            'message': "设置失败"
        }


# 使用示例
if __name__ == "__main__":
    # 测试更新印象
    result = mcp_update_user_impression(
        user_id="test_user",
        platform="qq",
        impression="喜欢玩游戏，性格开朗，经常分享生活趣事。",
        confidence=0.9
    )
    print(f"更新印象: {result}")

    # 测试添加标签
    result = mcp_add_user_tag(
        user_id="test_user",
        platform="qq",
        tag="游戏爱好者",
        category="interest"
    )
    print(f"添加标签: {result}")

    # 测试获取画像
    result = mcp_get_user_profile(
        user_id="test_user",
        platform="qq"
    )
    print(f"用户画像: {result}")
