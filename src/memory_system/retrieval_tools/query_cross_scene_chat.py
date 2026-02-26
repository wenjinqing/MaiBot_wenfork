"""
跨场景聊天记录查询工具
允许机器人查询与同一用户在其他场景（群聊/私聊）的聊天记录
"""

import time
from typing import Optional, List
from src.common.logger import get_logger
from src.common.database.database_model import Messages, db
from src.common.data_models.database_data_model import DatabaseMessages
from src.chat.utils.chat_message_builder import build_readable_messages
from src.chat.message_receive.chat_stream import get_chat_manager
from src.person_info.person_info import Person
from .tool_registry import register_memory_retrieval_tool

logger = get_logger("memory_retrieval_tools")


async def query_cross_scene_chat(
    user_name: str,
    scene_type: Optional[str] = None,
    keyword: Optional[str] = None,
    time_range_days: int = 30,
    limit: int = 20,
    chat_id: Optional[str] = None
) -> str:
    """查询与指定用户在其他场景的聊天记录

    Args:
        user_name: 用户名称（可以是昵称或person_name）
        scene_type: 场景类型，可选值：
            - "private": 只查询私聊记录
            - "group": 只查询群聊记录
            - None: 查询所有场景（默认）
        keyword: 关键词过滤（可选）
        time_range_days: 查询时间范围（天数），默认30天
        limit: 返回的最大消息数，默认20条
        chat_id: 当前聊天ID（由系统自动传入）

    Returns:
        str: 格式化的聊天记录，包含时间、场景、内容
    """
    try:
        # 如果没有提供 chat_id，返回错误
        if not chat_id:
            return "无法获取当前聊天ID，请确保在聊天上下文中调用此工具"

        # 1. 根据用户名查找用户
        person = Person(person_name=user_name)
        if not person.is_known:
            return f"未找到用户 {user_name} 的信息"

        user_id = person.user_id
        platform = person.platform

        logger.info(f"[跨场景查询] 查询参数: user_name={user_name}, user_id={user_id}, platform={platform}, scene_type={scene_type}, chat_id={chat_id}")

        # 2. 获取当前聊天流信息（用于排除当前聊天）
        chat_manager = get_chat_manager()
        current_stream = chat_manager.get_stream(chat_id)
        if not current_stream:
            return "无法获取当前聊天信息"

        # 3. 构建查询条件
        time_start = time.time() - (time_range_days * 86400)

        with db:
            # 查询该用户的所有消息
            query = Messages.select().where(
                (Messages.chat_info_user_id == user_id) &
                (Messages.chat_info_platform == platform) &
                (Messages.time > time_start)
            )

            # 过滤场景类型
            if scene_type == "private":
                # 私聊：chat_info_group_id 为 NULL
                query = query.where(Messages.chat_info_group_id.is_null())
                logger.info(f"[跨场景查询] 筛选私聊消息")
            elif scene_type == "group":
                # 群聊：chat_info_group_id 不为 NULL
                query = query.where(Messages.chat_info_group_id.is_null(False))
                logger.info(f"[跨场景查询] 筛选群聊消息")

            # 排除当前聊天
            query = query.where(Messages.chat_id != chat_id)
            logger.info(f"[跨场景查询] 排除当前聊天: {chat_id}")

            # 关键词过滤
            if keyword:
                query = query.where(
                    (Messages.processed_plain_text.contains(keyword)) |
                    (Messages.display_message.contains(keyword))
                )
                logger.info(f"[跨场景查询] 关键词过滤: {keyword}")

            # 按时间倒序，限制数量
            messages = list(query.order_by(Messages.time.desc()).limit(limit))
            logger.info(f"[跨场景查询] 查询结果: 找到 {len(messages)} 条消息")

            # 如果没有找到消息，输出调试信息
            if not messages:
                # 查询该用户的所有消息（不限制场景和chat_id）
                debug_query = Messages.select().where(
                    (Messages.chat_info_user_id == user_id) &
                    (Messages.chat_info_platform == platform) &
                    (Messages.time > time_start)
                ).limit(5)
                debug_messages = list(debug_query)
                logger.info(f"[跨场景查询] 调试: 该用户总共有 {len(debug_messages)} 条消息（前5条）")
                for msg in debug_messages:
                    logger.info(f"[跨场景查询] 调试消息: chat_id={msg.chat_id}, group_id={msg.chat_info_group_id}, text={msg.processed_plain_text[:50] if msg.processed_plain_text else 'None'}")

        if not messages:
            scene_desc = {
                "private": "私聊",
                "group": "群聊",
                None: "其他场景"
            }.get(scene_type, "其他场景")

            keyword_desc = f"包含'{keyword}'的" if keyword else ""
            return f"未找到与 {user_name} 在{scene_desc}中{keyword_desc}聊天记录（最近{time_range_days}天）"

        # 4. 按聊天场景分组
        scene_messages = {}
        for msg in messages:
            msg_chat_id = msg.chat_id
            if msg_chat_id not in scene_messages:
                scene_messages[msg_chat_id] = []
            # 转换为 DatabaseMessages 类型
            db_msg = DatabaseMessages(**msg.__data__)
            scene_messages[msg_chat_id].append(db_msg)

        # 5. 格式化输出
        result_parts = []
        result_parts.append(f"找到与 {user_name} 在其他场景的 {len(messages)} 条聊天记录：\n")

        for msg_chat_id, msgs in scene_messages.items():
            # 获取场景信息
            stream = chat_manager.get_stream(msg_chat_id)
            if stream:
                if stream.group_info:
                    scene_name = f"群聊【{stream.group_info.group_name}】"
                else:
                    scene_name = "私聊"
            else:
                scene_name = "未知场景"

            result_parts.append(f"\n## {scene_name}（{len(msgs)}条消息）")

            # 反转消息顺序（从旧到新）
            msgs.reverse()

            # 格式化消息
            formatted_msgs = build_readable_messages(
                msgs,
                replace_bot_name=True,
                timestamp_mode="relative",
                truncate=False,
                show_actions=False
            )

            result_parts.append(formatted_msgs)

        return "\n".join(result_parts)

    except Exception as e:
        logger.error(f"查询跨场景聊天记录失败: {e}", exc_info=True)
        return f"查询失败: {str(e)}"


# 注册工具
register_memory_retrieval_tool(
    name="query_cross_scene_chat",
    description=(
        "【跨场景查询工具】查询与指定用户在**其他场景**的聊天记录（不包括当前聊天）。"
        "使用场景：当用户问'你还记得我们在私聊里聊过什么吗'、'我之前在XX群和你说过什么'、'你还记得我们在其他地方的对话吗'等跨场景问题时使用。"
        "功能：可以查询该用户在其他群聊或私聊中的历史对话，支持按场景类型（私聊/群聊）、关键词、时间范围筛选。"
        "注意：此工具专门用于查询**其他场景**的记录，会自动排除当前聊天的消息。"
    ),
    parameters=[
        {
            "name": "user_name",
            "type": "string",
            "description": "用户名称（昵称或person_name）",
            "required": True
        },
        {
            "name": "scene_type",
            "type": "string",
            "description": "场景类型：'private'(私聊)、'group'(群聊)、留空(所有场景)",
            "required": False
        },
        {
            "name": "keyword",
            "type": "string",
            "description": "关键词过滤（可选）",
            "required": False
        },
        {
            "name": "time_range_days",
            "type": "integer",
            "description": "查询时间范围（天数），默认30天",
            "required": False
        },
        {
            "name": "limit",
            "type": "integer",
            "description": "返回的最大消息数，默认20条",
            "required": False
        },
    ],
    execute_func=query_cross_scene_chat,
)
