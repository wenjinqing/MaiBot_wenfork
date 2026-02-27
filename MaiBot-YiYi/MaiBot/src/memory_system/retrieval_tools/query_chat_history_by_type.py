"""
按聊天类型查询聊天记录 - 支持区分群聊和私聊
"""

import json
from typing import Optional
from src.common.logger import get_logger
from src.common.database.database_model import ChatHistory
from src.chat.utils.utils import parse_keywords_string
from src.memory_system.retrieval_tools.tool_registry import register_memory_retrieval_tool
from datetime import datetime

logger = get_logger("memory_retrieval_tools")


async def search_chat_history_by_type(
    chat_id: str,
    chat_type: str = "all",
    keyword: Optional[str] = None,
    participant: Optional[str] = None
) -> str:
    """根据聊天类型、关键词或参与人查询记忆

    Args:
        chat_id: 聊天ID
        chat_type: 聊天类型（group=群聊，private=私聊，all=全部）
        keyword: 关键词（可选）
        participant: 参与人昵称（可选）

    Returns:
        str: 查询结果
    """
    try:
        # 检查参数
        if not keyword and not participant:
            return "未指定查询参数（需要提供keyword或participant之一）"

        # 构建查询条件
        query = ChatHistory.select().where(ChatHistory.chat_id == chat_id)

        # 根据聊天类型筛选
        # 注意：这里需要根据实际的数据库字段来判断是群聊还是私聊
        # 假设 ChatHistory 表中有 is_group 字段或者可以通过其他字段判断
        # 如果没有，需要通过 chat_id 或其他方式判断

        # 执行查询
        records = list(query.order_by(ChatHistory.start_time.desc()).limit(50))

        filtered_records = []

        for record in records:
            # 根据 chat_type 筛选
            # 这里需要根据实际情况判断记录是群聊还是私聊
            # 暂时跳过类型筛选，因为 ChatHistory 表可能没有明确的字段
            # 可以通过 participants 数量来判断：>2 为群聊，=2 为私聊

            if chat_type != "all":
                participants_count = 0
                if record.participants:
                    try:
                        participants_data = (
                            json.loads(record.participants)
                            if isinstance(record.participants, str)
                            else record.participants
                        )
                        if isinstance(participants_data, list):
                            participants_count = len(participants_data)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass

                # 判断是否符合聊天类型
                is_group = participants_count > 2
                if chat_type == "group" and not is_group:
                    continue
                if chat_type == "private" and is_group:
                    continue

            participant_matched = True
            keyword_matched = True

            # 检查参与人匹配
            if participant:
                participant_matched = False
                participants_list = []
                if record.participants:
                    try:
                        participants_data = (
                            json.loads(record.participants)
                            if isinstance(record.participants, str)
                            else record.participants
                        )
                        if isinstance(participants_data, list):
                            participants_list = [str(p).lower() for p in participants_data]
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass

                participant_lower = participant.lower().strip()
                if participant_lower and any(participant_lower in p for p in participants_list):
                    participant_matched = True

            # 检查关键词匹配
            if keyword:
                keyword_matched = False
                keywords_list = parse_keywords_string(keyword)
                if not keywords_list:
                    keywords_list = [keyword.strip()] if keyword.strip() else []

                keywords_lower = [kw.lower() for kw in keywords_list if kw.strip()]

                if keywords_lower:
                    theme = (record.theme or "").lower()
                    summary = (record.summary or "").lower()
                    original_text = (record.original_text or "").lower()

                    record_keywords_list = []
                    if record.keywords:
                        try:
                            keywords_data = (
                                json.loads(record.keywords) if isinstance(record.keywords, str) else record.keywords
                            )
                            if isinstance(keywords_data, list):
                                record_keywords_list = [str(k).lower() for k in keywords_data]
                        except (json.JSONDecodeError, TypeError, ValueError):
                            pass

                    matched_count = 0
                    for kw in keywords_lower:
                        kw_matched = (
                            kw in theme
                            or kw in summary
                            or kw in original_text
                            or any(kw in rk for rk in record_keywords_list)
                        )
                        if kw_matched:
                            matched_count += 1

                    required_matches = len(keywords_lower) if len(keywords_lower) <= 2 else len(keywords_lower) - 1
                    keyword_matched = matched_count >= required_matches

            if participant_matched and keyword_matched:
                filtered_records.append(record)

        if not filtered_records:
            return f"未找到匹配的记忆（聊天类型：{chat_type}）"

        # 格式化结果
        results = []
        for record in filtered_records[:10]:
            start_time_str = datetime.fromtimestamp(record.start_time).strftime("%Y-%m-%d %H:%M")
            end_time_str = datetime.fromtimestamp(record.end_time).strftime("%Y-%m-%d %H:%M")

            participants_str = "未知"
            if record.participants:
                try:
                    participants_data = (
                        json.loads(record.participants) if isinstance(record.participants, str) else record.participants
                    )
                    if isinstance(participants_data, list):
                        participants_str = ", ".join(str(p) for p in participants_data[:5])
                        if len(participants_data) > 5:
                            participants_str += f" 等{len(participants_data)}人"
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass

            result_item = {
                "memory_id": record.id,
                "theme": record.theme or "无主题",
                "summary": record.summary or "无摘要",
                "time_range": f"{start_time_str} ~ {end_time_str}",
                "participants": participants_str,
                "keywords": record.keywords or "[]",
            }
            results.append(result_item)

        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"按聊天类型查询记忆失败: {e}", exc_info=True)
        return f"查询失败: {str(e)}"


# 注册工具
register_memory_retrieval_tool(
    name="search_chat_history_by_type",
    description="根据聊天类型（群聊/私聊）、关键词或参与人查询历史聊天记录",
    parameters=[
        {
            "name": "chat_id",
            "type": "string",
            "description": "聊天ID（必填）",
            "required": True
        },
        {
            "name": "chat_type",
            "type": "string",
            "description": "聊天类型：group=群聊，private=私聊，all=全部（默认all）",
            "required": False,
            "enum": ["group", "private", "all"]
        },
        {
            "name": "keyword",
            "type": "string",
            "description": "关键词（可选，支持多个关键词用空格或逗号分隔）",
            "required": False
        },
        {
            "name": "participant",
            "type": "string",
            "description": "参与人昵称（可选）",
            "required": False
        }
    ],
    execute_func=search_chat_history_by_type
)
