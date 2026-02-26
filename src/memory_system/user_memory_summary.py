"""
用户记忆摘要生成器 - 为每个用户生成详细的记忆摘要
"""
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from src.common.logger import get_logger
from src.common.database.database_model import ChatHistory, PersonInfo
from src.person_info.person_info import Person
from src.config.config import global_config

logger = get_logger("用户记忆摘要")


async def generate_user_memory_summary(
    person_id: str,
    chat_id: Optional[str] = None,
    days_limit: int = 30,
    max_topics: int = 10,
    max_memories: int = 10,
    max_chat_history: int = 5,
) -> str:
    """
    为指定用户生成记忆摘要

    Args:
        person_id: 用户的person_id
        chat_id: 当前聊天的chat_id（可选，用于过滤相关聊天）
        days_limit: 检索最近几天的记忆（默认30天）
        max_topics: 最多显示几个话题（默认10个）
        max_memories: 最多显示几条记忆点（默认10条）
        max_chat_history: 最多显示几条聊天历史（默认5条）

    Returns:
        str: 格式化的记忆摘要文本
    """
    try:
        # 获取用户信息
        person = Person(person_id=person_id)
        if not person.is_known:
            return ""

        person_name = person.person_name or "该用户"

        # 构建记忆摘要
        summary_parts = []
        summary_parts.append(f"=== 关于 {person_name} 的记忆 ===\n")

        # 1. 基本信息和记忆点
        memory_points_text = _format_memory_points(person, max_memories)
        if memory_points_text:
            summary_parts.append(memory_points_text)

        # 2. 聊过的话题
        topics_text = await _get_chat_topics(person_id, days_limit, max_topics)
        if topics_text:
            summary_parts.append(topics_text)

        # 3. 有趣的记忆片段
        interesting_memories = await _get_interesting_memories(person_id, days_limit, max_chat_history)
        if interesting_memories:
            summary_parts.append(interesting_memories)

        # 4. 最近的互动情况
        recent_interaction = await _get_recent_interaction(person_id, days_limit)
        if recent_interaction:
            summary_parts.append(recent_interaction)

        if len(summary_parts) <= 1:  # 只有标题，没有实际内容
            return ""

        summary_parts.append("=== 记忆摘要结束 ===\n")

        result = "\n".join(summary_parts)
        logger.debug(f"成功生成 {person_name} 的记忆摘要")
        return result

    except Exception as e:
        logger.error(f"生成用户记忆摘要失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return ""


def _format_memory_points(person: Person, max_memories: int = 0) -> str:
    """
    格式化记忆点（全部展示，不限制数量）

    Args:
        person: Person对象
        max_memories: 已废弃，保留参数兼容性

    Returns:
        str: 格式化的记忆点文本
    """
    if not person.memory_points:
        return ""

    memory_points = person.memory_points  # 不截断，全部展示

    # 按类别分组
    categorized_memories: Dict[str, List[str]] = {}
    for memory in memory_points:
        parts = memory.split(":", 2)
        if len(parts) >= 2:
            category = parts[0]
            content = parts[1]
            if category not in categorized_memories:
                categorized_memories[category] = []
            categorized_memories[category].append(content)
        else:
            if "其他" not in categorized_memories:
                categorized_memories["其他"] = []
            categorized_memories["其他"].append(memory)

    # 格式化输出
    result = "【基本印象】\n"
    for category, contents in categorized_memories.items():
        result += f"  {category}：{', '.join(contents)}\n"

    return result


async def _get_chat_topics(person_id: str, days_limit: int, max_topics: int) -> str:
    """
    获取与该用户聊过的话题

    Args:
        person_id: 用户的person_id
        days_limit: 检索最近几天的话题
        max_topics: 最多显示几个话题

    Returns:
        str: 格式化的话题文本
    """
    try:
        # 计算时间范围
        now = datetime.now()
        start_time = (now - timedelta(days=days_limit)).timestamp()

        # 从ChatHistory中查询与该用户相关的聊天
        # 注意：participants字段是JSON格式，需要模糊匹配
        query = (
            ChatHistory.select()
            .where(
                (ChatHistory.start_time >= start_time) &
                (ChatHistory.theme.is_null(False))  # 只查询有主题的记录
            )
            .order_by(ChatHistory.start_time.desc())
            .limit(max_topics * 2)  # 多查询一些，后续过滤
        )

        # 过滤出与该用户相关的聊天
        topics = []
        seen_themes = set()

        for chat in query:
            # 检查participants是否包含该person_id
            try:
                participants = json.loads(chat.participants) if chat.participants else []
                # participants可能是[{"person_id": "xxx", "name": "xxx"}]格式
                participant_ids = []
                for p in participants:
                    if isinstance(p, dict) and "person_id" in p:
                        participant_ids.append(p["person_id"])
                    elif isinstance(p, str):
                        participant_ids.append(p)

                if person_id not in participant_ids:
                    continue

                # 避免重复话题
                theme = chat.theme
                if theme and theme not in seen_themes:
                    seen_themes.add(theme)
                    # 格式化时间
                    chat_time = datetime.fromtimestamp(chat.start_time).strftime("%m-%d")
                    topics.append(f"  - {theme} ({chat_time})")

                    if len(topics) >= max_topics:
                        break
            except:
                continue

        if not topics:
            return ""

        result = "【聊过的话题】\n"
        result += "\n".join(topics) + "\n"
        return result

    except Exception as e:
        logger.error(f"获取聊天话题失败: {str(e)}")
        return ""


async def _get_interesting_memories(person_id: str, days_limit: int, max_memories: int) -> str:
    """
    获取有趣的记忆片段

    Args:
        person_id: 用户的person_id
        days_limit: 检索最近几天的记忆
        max_memories: 最多显示几条记忆

    Returns:
        str: 格式化的有趣记忆文本
    """
    try:
        # 计算时间范围
        now = datetime.now()
        start_time = (now - timedelta(days=days_limit)).timestamp()

        # 从ChatHistory中查询与该用户相关的聊天
        query = (
            ChatHistory.select()
            .where(
                (ChatHistory.start_time >= start_time) &
                (ChatHistory.key_point.is_null(False))  # 只查询有关键信息点的记录
            )
            .order_by(ChatHistory.start_time.desc())
            .limit(max_memories * 2)
        )

        # 过滤出与该用户相关的聊天
        memories = []

        for chat in query:
            try:
                participants = json.loads(chat.participants) if chat.participants else []
                participant_ids = []
                for p in participants:
                    if isinstance(p, dict) and "person_id" in p:
                        participant_ids.append(p["person_id"])
                    elif isinstance(p, str):
                        participant_ids.append(p)

                if person_id not in participant_ids:
                    continue

                # 获取关键信息点
                key_point = chat.key_point
                if key_point and len(key_point) > 10:  # 过滤太短的内容
                    # 格式化时间
                    chat_time = datetime.fromtimestamp(chat.start_time).strftime("%m-%d")
                    # 截断过长的内容
                    if len(key_point) > 100:
                        key_point = key_point[:100] + "..."
                    memories.append(f"  - {key_point} ({chat_time})")

                    if len(memories) >= max_memories:
                        break
            except:
                continue

        if not memories:
            return ""

        result = "【有趣的记忆片段】\n"
        result += "\n".join(memories) + "\n"
        return result

    except Exception as e:
        logger.error(f"获取有趣记忆失败: {str(e)}")
        return ""


async def _get_recent_interaction(person_id: str, days_limit: int) -> str:
    """
    获取最近的互动情况

    Args:
        person_id: 用户的person_id
        days_limit: 检索最近几天的互动

    Returns:
        str: 格式化的互动情况文本
    """
    try:
        # 计算时间范围
        now = datetime.now()
        start_time = (now - timedelta(days=days_limit)).timestamp()

        # 统计与该用户的聊天次数
        query = (
            ChatHistory.select()
            .where(ChatHistory.start_time >= start_time)
        )

        chat_count = 0
        last_chat_time = None

        for chat in query:
            try:
                participants = json.loads(chat.participants) if chat.participants else []
                participant_ids = []
                for p in participants:
                    if isinstance(p, dict) and "person_id" in p:
                        participant_ids.append(p["person_id"])
                    elif isinstance(p, str):
                        participant_ids.append(p)

                if person_id in participant_ids:
                    chat_count += 1
                    if last_chat_time is None or chat.start_time > last_chat_time:
                        last_chat_time = chat.start_time
            except:
                continue

        if chat_count == 0:
            return ""

        result = "【最近互动】\n"
        result += f"  最近{days_limit}天内聊过 {chat_count} 次\n"

        if last_chat_time:
            last_time = datetime.fromtimestamp(last_chat_time)
            time_diff = now - last_time
            if time_diff.days == 0:
                result += f"  最后一次聊天：今天\n"
            elif time_diff.days == 1:
                result += f"  最后一次聊天：昨天\n"
            else:
                result += f"  最后一次聊天：{time_diff.days}天前\n"

        return result

    except Exception as e:
        logger.error(f"获取最近互动失败: {str(e)}")
        return ""


async def get_user_memory_for_reply(
    person_id: str,
    chat_id: Optional[str] = None,
    enable_detailed_memory: bool = True,
) -> str:
    """
    获取用于回复的用户记忆（简化版）

    Args:
        person_id: 用户的person_id
        chat_id: 当前聊天的chat_id
        enable_detailed_memory: 是否启用详细记忆

    Returns:
        str: 格式化的记忆文本
    """
    if not enable_detailed_memory:
        return ""

    try:
        # 获取配置
        days_limit = global_config.memory.memory_days_limit if hasattr(global_config.memory, 'memory_days_limit') else 30
        max_topics = global_config.memory.max_topics if hasattr(global_config.memory, 'max_topics') else 5
        max_memories = global_config.memory.max_memories if hasattr(global_config.memory, 'max_memories') else 5
        max_chat_history = global_config.memory.max_chat_history if hasattr(global_config.memory, 'max_chat_history') else 3

        # 生成记忆摘要
        summary = await generate_user_memory_summary(
            person_id=person_id,
            chat_id=chat_id,
            days_limit=days_limit,
            max_topics=max_topics,
            max_memories=max_memories,
            max_chat_history=max_chat_history,
        )

        return summary

    except Exception as e:
        logger.error(f"获取用户记忆失败: {str(e)}")
        return ""
