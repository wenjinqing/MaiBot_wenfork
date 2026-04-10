"""
好感度查询工具

允许用户查询自己的好感度、心情值等信息
"""

from typing import Optional, Dict
from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger
from src.common.person_info_resolve import get_person_by_user_platform
from src.common.relationship_updater import RelationshipUpdater

logger = get_logger("relationship_query")


class RelationshipQuery:
    """好感度查询工具"""

    @staticmethod
    def query_relationship(user_id: str, platform: str) -> Optional[Dict]:
        """
        查询用户的好感度信息

        参数:
            user_id: 用户ID
            platform: 平台

        返回:
            好感度信息字典
        """
        try:
            with db:
                user = get_person_by_user_platform(user_id, platform)

                if not user:
                    return None

                # 获取关系等级
                relationship_level = RelationshipUpdater.get_relationship_level(user.relationship_value)

                # 计算到下一等级的进度
                level_ranges = {
                    '陌生人': (0, 20),
                    '初识': (20, 40),
                    '熟人': (40, 60),
                    '好友': (60, 80),
                    '挚友': (80, 95),
                    '恋人': (95, 100)
                }

                current_range = level_ranges.get(relationship_level, (0, 100))
                if relationship_level != '恋人':
                    progress_in_level = ((user.relationship_value - current_range[0]) /
                                       (current_range[1] - current_range[0])) * 100
                else:
                    progress_in_level = 100

                # 心情描述
                mood_desc = RelationshipQuery._get_mood_description(user.mood_value)

                # 关系状态
                relationship_status = "💕 恋人" if user.is_in_love else f"👥 {relationship_level}"

                return {
                    'nickname': user.nickname or user_id,
                    'relationship_value': user.relationship_value,
                    'relationship_level': relationship_level,
                    'progress_in_level': progress_in_level,
                    'mood_value': user.mood_value,
                    'mood_description': mood_desc,
                    'total_messages': user.total_messages,
                    'chat_frequency': user.chat_frequency,
                    'is_in_love': user.is_in_love,
                    'relationship_status': relationship_status,
                    'memory_points': user.memory_points or [],
                }

        except Exception as e:
            logger.error(f"查询好感度失败: {e}", exc_info=True)
            return None

    @staticmethod
    def _get_mood_description(mood_value: int) -> str:
        """获取心情描述"""
        if mood_value >= 90:
            return "😊 非常开心"
        elif mood_value >= 75:
            return "😄 心情很好"
        elif mood_value >= 60:
            return "🙂 心情不错"
        elif mood_value >= 40:
            return "😐 心情一般"
        elif mood_value >= 25:
            return "😔 有点低落"
        else:
            return "😢 心情很差"

    @staticmethod
    def format_relationship_info(info: Dict) -> str:
        """
        格式化好感度信息为可读文本

        参数:
            info: 好感度信息字典

        返回:
            格式化的文本
        """
        if not info:
            return "查询失败：未找到用户信息"

        # 进度条
        progress_bar = RelationshipQuery._create_progress_bar(info['relationship_value'], 100)
        level_progress_bar = RelationshipQuery._create_progress_bar(info['progress_in_level'], 100)

        # 构建消息
        message = f"""📊 关系信息查询

👤 用户：{info['nickname']}
{info['relationship_status']}

💖 好感度：{info['relationship_value']:.1f}/100
{progress_bar}

📈 当前等级：{info['relationship_level']}
等级进度：{info['progress_in_level']:.1f}%
{level_progress_bar}

😊 心情值：{info['mood_value']}/100
{info['mood_description']}

💬 总消息数：{info['total_messages']}
📊 聊天频率：{info['chat_frequency']:.1f}/10
"""

        # 如果是恋人，添加特殊信息
        if info['is_in_love']:
            message += "\n💕 我们已经是恋人啦~"

        return message

    @staticmethod
    def _create_progress_bar(value: float, max_value: float, length: int = 10) -> str:
        """创建进度条"""
        filled = int((value / max_value) * length)
        empty = length - filled
        return f"[{'█' * filled}{'░' * empty}] {value:.1f}/{max_value}"

    @staticmethod
    def check_query_keywords(message_text: str, bot_name: str = "") -> bool:
        """
        检查消息是否包含查询关键词
        响应以下格式：
        - @bot名 查看好感度
        - 查看好感度@bot名
        """
        if not bot_name:
            from src.config.config import global_config
            bot_name = global_config.bot.nickname or ""

        return (
            f"@{bot_name} 查看好感度" in message_text or
            f"查看好感度@{bot_name}" in message_text
        )


# 使用示例
if __name__ == "__main__":
    # 查询好感度
    info = RelationshipQuery.query_relationship(
        user_id="test_user",
        platform="qq"
    )

    if info:
        print(RelationshipQuery.format_relationship_info(info))
