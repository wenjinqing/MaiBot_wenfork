"""
亲密度与表白系统集成示例

展示如何在消息处理流程中集成亲密度更新和表白触发
"""

import time
from typing import Optional, Dict, Any
from src.common.relationship_updater import RelationshipUpdater
from src.common.confession_system import ConfessionSystem
from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger

logger = get_logger("relationship_integration")


class RelationshipManager:
    """亲密度与表白系统管理器"""

    @staticmethod
    def process_message(
        user_id: str,
        platform: str,
        message_text: str,
        message_length: int = 0,
        has_emoji: bool = False,
        has_image: bool = False,
        is_at_bot: bool = False,
        is_reply_bot: bool = False
    ) -> Dict[str, Any]:
        """
        处理消息并更新亲密度

        返回:
        {
            'relationship_updated': bool,           # 是否更新了亲密度
            'relationship_info': dict,              # 亲密度信息
            'confession_triggered': bool,           # 是否触发表白
            'confession_message': str,              # 表白文案
            'is_confession_response': bool,         # 是否是对表白的回应
            'confession_response_type': str,        # 回应类型
            'special_reply': str,                   # 特殊回复
            'should_use_love_mode': bool,          # 是否应该使用恋爱模式
        }
        """
        result = {
            'relationship_updated': False,
            'relationship_info': None,
            'confession_triggered': False,
            'confession_message': None,
            'is_confession_response': False,
            'confession_response_type': None,
            'special_reply': None,
            'should_use_love_mode': False,
        }

        try:
            # 1. 检查用户是否存在
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    logger.warning(f"用户不存在: {user_id}@{platform}")
                    return result

                # 2. 检查是否是对表白的回应
                if user.confession_time and not user.love_response:
                    # 用户已被表白但还未回应
                    response_type = ConfessionSystem.detect_confession_response(message_text)

                    if response_type:
                        result['is_confession_response'] = True
                        result['confession_response_type'] = response_type

                        # 更新用户的回应状态
                        user.love_response = response_type

                        if response_type == 'accepted':
                            user.is_in_love = True
                            user.anniversary_date = time.time()
                            logger.info(f"💕 用户 {user.nickname or user_id} 接受了表白！")

                        user.save()

                        # 生成特殊回复
                        result['special_reply'] = ConfessionSystem.generate_special_reply(response_type)

                # 3. 更新亲密度
                relationship_info = RelationshipUpdater.update_on_message(
                    user_id=user_id,
                    platform=platform,
                    message_length=message_length,
                    message_text=message_text,
                    has_emoji=has_emoji,
                    has_image=has_image,
                    is_at_bot=is_at_bot,
                    is_reply_bot=is_reply_bot
                )

                if relationship_info:
                    result['relationship_updated'] = True
                    result['relationship_info'] = relationship_info

                    # 4. 检查是否触发表白
                    if relationship_info.get('confession_triggered'):
                        result['confession_triggered'] = True

                        # 计算认识天数
                        days_known = 0
                        if user.first_meet_time:
                            days_known = int((time.time() - user.first_meet_time) / 86400)

                        # 生成表白文案
                        confession = ConfessionSystem.generate_confession(
                            nickname=user.nickname,
                            total_messages=user.total_messages,
                            days_known=days_known,
                            style='random'  # 随机风格
                        )

                        result['confession_message'] = confession

                        # 记录表白时间
                        user.confession_time = time.time()
                        user.save()

                        logger.info(f"💌 向用户 {user.nickname or user_id} 发送表白")

                # 5. 检查是否应该使用恋爱模式
                if user.is_in_love:
                    result['should_use_love_mode'] = True

        except Exception as e:
            logger.error(f"处理消息时出错: {e}", exc_info=True)

        return result

    @staticmethod
    def get_reply_context(user_id: str, platform: str) -> Dict[str, Any]:
        """
        获取回复上下文（用于生成回复时参考）

        返回:
        {
            'relationship_value': int,
            'relationship_level': str,
            'reply_style': dict,
            'is_in_love': bool,
            'special_title': str,  # 特殊称呼
            'mood_value': int,
        }
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if not user:
                    return {
                        'relationship_value': 0,
                        'relationship_level': '陌生人',
                        'reply_style': RelationshipUpdater.get_reply_style(0),
                        'is_in_love': False,
                        'special_title': None,
                        'mood_value': 50,
                    }

                # 获取回复风格
                reply_style = RelationshipUpdater.get_reply_style(user.relationship_value)

                # 特殊称呼
                special_title = None
                if user.is_in_love:
                    special_title = random.choice(['亲爱的', '宝贝', '小可爱', user.nickname or '你'])
                elif user.relationship_value >= 80:
                    special_title = user.nickname or '朋友'

                return {
                    'relationship_value': user.relationship_value,
                    'relationship_level': RelationshipUpdater.get_relationship_level(user.relationship_value),
                    'reply_style': reply_style,
                    'is_in_love': user.is_in_love,
                    'special_title': special_title,
                    'mood_value': user.mood_value,
                    'total_messages': user.total_messages,
                    'chat_frequency': user.chat_frequency,
                }

        except Exception as e:
            logger.error(f"获取回复上下文失败: {e}")
            return {}

    @staticmethod
    def get_love_mode_greeting(user_id: str, platform: str) -> Optional[str]:
        """
        获取恋爱模式的特殊问候语

        返回:
            问候语，如果不在恋爱模式则返回 None
        """
        try:
            with db:
                user = PersonInfo.get_or_none(
                    (PersonInfo.user_id == user_id) &
                    (PersonInfo.platform == platform)
                )

                if user and user.is_in_love:
                    return ConfessionSystem.get_love_mode_greeting()

        except Exception as e:
            logger.error(f"获取恋爱模式问候语失败: {e}")

        return None


# 使用示例
if __name__ == "__main__":
    import random

    # 模拟消息处理
    def simulate_message_handling():
        """模拟消息处理流程"""

        user_id = "test_user_123"
        platform = "qq"
        message_text = "麦麦，我今天好开心啊！想和你分享一下~"

        # 1. 处理消息并更新亲密度
        result = RelationshipManager.process_message(
            user_id=user_id,
            platform=platform,
            message_text=message_text,
            message_length=len(message_text),
            has_emoji=False,
            has_image=False,
            is_at_bot=True,
            is_reply_bot=False
        )

        print("=" * 60)
        print("消息处理结果:")
        print("=" * 60)

        if result['relationship_updated']:
            info = result['relationship_info']
            print(f"✅ 亲密度已更新:")
            print(f"   当前值: {info['relationship_value']:.1f}")
            print(f"   变化: {info['delta']:+.2f}")
            print(f"   等级: {info['level']}")

        if result['confession_triggered']:
            print(f"\n💕 触发表白！")
            print(f"\n{result['confession_message']}")

        if result['is_confession_response']:
            print(f"\n💌 检测到表白回应: {result['confession_response_type']}")
            print(f"\n回复: {result['special_reply']}")

        # 2. 获取回复上下文
        context = RelationshipManager.get_reply_context(user_id, platform)

        print(f"\n" + "=" * 60)
        print("回复上下文:")
        print("=" * 60)
        print(f"亲密度: {context.get('relationship_value', 0)}")
        print(f"等级: {context.get('relationship_level', '未知')}")
        print(f"恋爱模式: {'是' if context.get('is_in_love') else '否'}")

        if context.get('special_title'):
            print(f"特殊称呼: {context['special_title']}")

        style = context.get('reply_style', {})
        if style:
            print(f"\n回复风格建议:")
            print(f"  语气: {style.get('tone')}")
            print(f"  表情使用率: {style.get('emoji_rate', 0)*100:.0f}%")
            print(f"  正式程度: {style.get('formality', 0)*100:.0f}%")
            print(f"  说明: {style.get('description')}")

        # 3. 如果在恋爱模式，获取特殊问候
        if context.get('is_in_love'):
            greeting = RelationshipManager.get_love_mode_greeting(user_id, platform)
            if greeting:
                print(f"\n💕 恋爱模式问候: {greeting}")

    # 运行模拟
    simulate_message_handling()
