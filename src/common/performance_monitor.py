"""
轻量级性能监控模块
监控内存使用、磁盘空间、LLM 调用统计，定期输出汇报
"""
import os
import time
import asyncio
from datetime import datetime, timedelta

from src.common.logger import get_logger
from src.manager.async_task_manager import AsyncTask

logger = get_logger("performance")

# 监控间隔（秒）
MONITOR_INTERVAL = 600  # 10分钟


def _get_memory_mb() -> float:
    """获取当前进程内存使用量（MB），使用内置模块"""
    try:
        import sys
        # Windows 平台
        if sys.platform == "win32":
            import ctypes
            import ctypes.wintypes
            process = ctypes.windll.kernel32.GetCurrentProcess()
            counters = ctypes.create_string_buffer(72)
            ctypes.windll.psapi.GetProcessMemoryInfo(process, counters, ctypes.sizeof(counters))
            # WorkingSetSize 在偏移量 16 处（64位）
            mem = int.from_bytes(counters[16:24], byteorder='little')
            return mem / 1024 / 1024
        else:
            # Linux/Mac
            with open(f"/proc/{os.getpid()}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024
    except Exception:
        pass
    return 0.0


def _get_disk_usage(path: str = "data") -> tuple[float, float, float]:
    """获取磁盘使用情况，返回 (total_gb, used_gb, free_gb)"""
    try:
        stat = os.statvfs(path) if hasattr(os, 'statvfs') else None
        if stat:
            total = stat.f_blocks * stat.f_frsize / 1024**3
            free = stat.f_bavail * stat.f_frsize / 1024**3
            used = total - free
            return total, used, free
        # Windows fallback
        import shutil
        total, used, free = shutil.disk_usage(path)
        return total / 1024**3, used / 1024**3, free / 1024**3
    except Exception:
        return 0.0, 0.0, 0.0


def _get_data_dir_size(path: str = "data") -> float:
    """获取 data 目录大小（MB）"""
    try:
        total = 0
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
        return total / 1024 / 1024
    except Exception:
        return 0.0


def _get_llm_stats_today() -> dict:
    """获取今日 LLM 调用统计"""
    try:
        from src.common.database.database import db
        from src.common.database.database_model import LLMUsage
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        records = LLMUsage.select().where(LLMUsage.time >= today_start)
        total_calls = 0
        total_tokens = 0
        total_cost = 0.0
        for r in records:
            total_calls += 1
            total_tokens += (r.prompt_tokens or 0) + (r.completion_tokens or 0)
            total_cost += r.total_price or 0.0
        return {"calls": total_calls, "tokens": total_tokens, "cost": total_cost}
    except Exception:
        return {"calls": 0, "tokens": 0, "cost": 0.0}


class PerformanceMonitorTask(AsyncTask):
    """性能监控定时任务"""

    def __init__(self):
        super().__init__(
            task_name="Performance Monitor",
            wait_before_start=60,  # 启动后 60 秒开始
            run_interval=MONITOR_INTERVAL,
        )
        self._start_time = time.time()

    async def run(self):
        try:
            uptime_seconds = int(time.time() - self._start_time)
            uptime_str = str(timedelta(seconds=uptime_seconds))

            mem_mb = _get_memory_mb()
            _, _, free_gb = _get_disk_usage("data")
            data_size_mb = await asyncio.get_event_loop().run_in_executor(None, _get_data_dir_size, "data")
            llm_stats = await asyncio.get_event_loop().run_in_executor(None, _get_llm_stats_today)

            lines = [
                f"[性能监控] 运行时长: {uptime_str}",
            ]
            if mem_mb > 0:
                lines.append(f"  内存占用: {mem_mb:.1f} MB")
            lines.append(f"  data 目录: {data_size_mb:.1f} MB | 磁盘剩余: {free_gb:.2f} GB")
            lines.append(
                f"  今日 LLM: {llm_stats['calls']} 次调用 | "
                f"{llm_stats['tokens']:,} tokens | "
                f"¥{llm_stats['cost']:.4f}"
            )

            # 磁盘空间警告
            if 0 < free_gb < 2:
                logger.warning(f"[性能监控] 磁盘空间不足！剩余: {free_gb:.2f} GB")

            logger.info("\n".join(lines))

        except Exception as e:
            logger.error(f"[性能监控] 监控任务出错: {e}")
