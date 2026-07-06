"""
数据库后台清理（DB Cleanup）

针对本项目（Peewee + SQLite）实际的膨胀来源做定向清理，遏制 data/MaiBot.db 无限增长。

膨胀来源（实测 388MB 时）：
  - llm_usage  ：API 用量/计费统计日志，纯日志，按时间清理最安全
  - jargon     ：黑话表，主因是个别 raw_content 超长（最大单行约 3MB），其次是低价值噪音行

设计原则（与 Timing Gate 一致）：
  1. **配置开关**：由 [database] enable_auto_cleanup 控制，默认关闭，老用户行为不变。
  2. **失败隔离**：任何异常都被捕获并记录，绝不影响主程序运行。
  3. **保守删除**：只清理"纯日志"与"明确低价值"的数据；功能性数据（messages、确认/未判定的黑话）一律保留。
  4. **可观测**：清理前后输出行数与体积日志，便于核对。

注意：本模块**不**移植原项目（maisaka 架构）的 tool_record_payload_cleanup —— 那套针对的是
maisaka 工具调用记录（monitor_detail / base64 内联），本项目数据结构不同、不适用。
"""

import asyncio
import time
import datetime
import traceback
from typing import Optional

from src.config.config import global_config
from src.common.logger import get_logger
from src.common.database.database import db
from src.common.database.database_model import LLMUsage, Jargon

logger = get_logger("db_cleanup")

# jargon.raw_content 超过该长度即视为异常超长，截断为预览
_JARGON_RAW_CONTENT_MAX = 2000
_JARGON_TRUNCATE_MARK = "…[超长原文已截断]"


def _now() -> float:
    return time.time()


def cleanup_llm_usage(retention_days: int) -> int:
    """删除 retention_days 天前的 llm_usage 记录。返回删除行数。

    llm_usage.timestamp 为 DateTimeField（存 datetime 字符串），按字符串比较即可正确按时间过滤。
    """
    cutoff_dt = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    try:
        deleted = LLMUsage.delete().where(LLMUsage.timestamp < cutoff_dt).execute()
        if deleted:
            logger.info(f"[DB清理] llm_usage 删除 {deleted} 行（{retention_days} 天前的用量日志）")
        return int(deleted or 0)
    except Exception as e:
        logger.warning(f"[DB清理] llm_usage 清理失败：{e}")
        logger.debug(traceback.format_exc())
        return 0


def cleanup_jargon() -> tuple[int, int]:
    """清理 jargon 表：截断超长 raw_content + 删除低价值噪音行。

    返回 (截断行数, 删除行数)。

    - 截断：raw_content 长度 > _JARGON_RAW_CONTENT_MAX 的，保留前 N 字符 + 标记。
      raw_content 仅作为黑话推断时的上下文留存，截断不影响已得出的 meaning / 判定结果。
    - 删除：is_jargon=0（已确认不是黑话）且 count<=2（极少被提及）的噪音行。
      保留 is_jargon=1（确认黑话）与 is_jargon IS NULL（尚未判定），避免误删有价值数据。
    """
    truncated = 0
    deleted = 0

    # 1) 截断超长 raw_content —— 用单条批量 SQL（而非逐行 UPDATE 上千次），
    #    把写锁占用从"连续上千次"压成"一瞬间"，避免长时间锁库导致其他写操作（如消息存储）报 database is locked。
    try:
        cursor = db.execute_sql(
            "UPDATE jargon SET raw_content = substr(raw_content, 1, ?) || ? "
            "WHERE raw_content IS NOT NULL AND length(raw_content) > ?",
            (_JARGON_RAW_CONTENT_MAX, _JARGON_TRUNCATE_MARK, _JARGON_RAW_CONTENT_MAX),
        )
        truncated = int(getattr(cursor, "rowcount", 0) or 0)
        if truncated:
            logger.info(f"[DB清理] jargon 截断 {truncated} 行超长 raw_content（阈值 {_JARGON_RAW_CONTENT_MAX} 字符）")
    except Exception as e:
        logger.warning(f"[DB清理] jargon raw_content 截断失败：{e}")
        logger.debug(traceback.format_exc())

    # 2) 删除低价值噪音行
    try:
        deleted = Jargon.delete().where(
            (Jargon.is_jargon == False) & (Jargon.count <= 2)  # noqa: E712 (Peewee 需要 == False)
        ).execute()
        if deleted:
            logger.info(f"[DB清理] jargon 删除 {deleted} 行低价值噪音（is_jargon=0 且 count<=2）")
    except Exception as e:
        logger.warning(f"[DB清理] jargon 噪音清理失败：{e}")
        logger.debug(traceback.format_exc())

    return truncated, deleted


def vacuum_database() -> None:
    """执行 VACUUM 回收已删除空间。注意：VACUUM 会短暂锁库，仅在有实际删除后调用。"""
    try:
        start = _now()
        db.execute_sql("VACUUM")
        logger.info(f"[DB清理] VACUUM 完成，回收碎片空间，耗时 {(_now() - start):.1f}s")
    except Exception as e:
        logger.warning(f"[DB清理] VACUUM 失败：{e}")
        logger.debug(traceback.format_exc())


def run_cleanup_once(retention_days: Optional[int] = None, do_vacuum: bool = True) -> dict:
    """执行一次完整清理（同步）。返回统计字典。可被后台任务或手动脚本调用。"""
    if retention_days is None:
        retention_days = int(getattr(global_config.database, "cleanup_retention_days", 60))

    logger.info(f"[DB清理] 开始清理（保留窗口 {retention_days} 天）……")
    stats = {"llm_usage_deleted": 0, "jargon_truncated": 0, "jargon_deleted": 0}

    stats["llm_usage_deleted"] = cleanup_llm_usage(retention_days)
    truncated, deleted = cleanup_jargon()
    stats["jargon_truncated"] = truncated
    stats["jargon_deleted"] = deleted

    # VACUUM 会锁全库且耗时，只在「实际删除」量较大时才值得跑：
    # - 截断（truncated）是 UPDATE，不产生需回收的空闲页，不该触发 VACUUM；
    # - 平时每天只删几行 llm_usage，碎片极小，跑 VACUUM 反而平白锁库导致消息存储失败。
    deleted_total = stats["llm_usage_deleted"] + stats["jargon_deleted"]
    if do_vacuum and deleted_total >= 500:
        vacuum_database()

    logger.info(f"[DB清理] 完成：{stats}")
    return stats


async def cleanup_loop():
    """后台清理循环：启动后等待一段时间再首次执行，随后按配置间隔周期执行。

    放入 try/except，任何异常都不会冒泡影响主程序；CancelledError 正常退出。
    """
    if not getattr(global_config.database, "enable_auto_cleanup", False):
        logger.info("[DB清理] 自动清理未启用（database.enable_auto_cleanup=false），跳过")
        return

    interval_hours = float(getattr(global_config.database, "cleanup_interval_hours", 24))
    interval_seconds = max(3600.0, interval_hours * 3600.0)
    # 启动后延迟 5 分钟再首次清理，避开启动高峰
    startup_delay = 300.0

    logger.info(
        f"[DB清理] 后台自动清理已启用：启动 {startup_delay/60:.0f} 分钟后首次执行，"
        f"此后每 {interval_hours:.0f} 小时一次"
    )
    try:
        await asyncio.sleep(startup_delay)
        while True:
            try:
                # 在线程池中执行同步 DB 操作，避免阻塞事件循环
                await asyncio.to_thread(run_cleanup_once)
            except Exception as e:
                logger.error(f"[DB清理] 周期清理出错（已忽略，不影响主程序）：{e}")
                logger.debug(traceback.format_exc())
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("[DB清理] 后台清理任务已取消")
        raise
