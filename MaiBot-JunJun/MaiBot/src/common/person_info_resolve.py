"""
同一 user_id + platform 可能对应多行 PersonInfo（历史 MD5 person_id 与多机器人 bot_scoped 并存等）。
get_or_none 只取一行时可能拿到亲密度为 0 的「新行」，导致关系系统像失效。
此处统一解析为「应使用」的一行。
"""

from __future__ import annotations

from typing import List, Optional

from src.common.database.database_model import PersonInfo, db
from src.common.logger import get_logger

logger = get_logger("person_info_resolve")


def get_person_by_user_platform(user_id: str, platform: str) -> Optional[PersonInfo]:
    """按 user_id + platform 解析 PersonInfo；多行时优先当前 bot_id，其次 maimai_main，否则取亲密度最高。"""
    uid = str(user_id).strip()
    plat = (platform or "").strip()
    if not uid or not plat:
        return None

    with db:
        rows: List[PersonInfo] = list(
            PersonInfo.select().where((PersonInfo.user_id == uid) & (PersonInfo.platform == plat))
        )

    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]

    logger.debug(
        f"PersonInfo 重复行 user_id={uid} platform={plat} count={len(rows)}，按 bot_id/亲密度择优"
    )

    try:
        from src.core.bot_context import get_current_bot_id

        bid = get_current_bot_id()
    except Exception:
        bid = "maimai_main"

    for r in rows:
        if r.bot_id == bid:
            return r
    for r in rows:
        if r.bot_id == "maimai_main":
            return r

    return max(
        rows,
        key=lambda x: ((x.relationship_value or 0.0), (x.total_messages or 0)),
    )
