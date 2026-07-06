import os
from peewee import SqliteDatabase
from rich.traceback import install

install(extra_lines=3)


# 定义数据库文件路径
ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DB_DIR = os.path.join(ROOT_PATH, "data")
_DB_FILE = os.path.join(_DB_DIR, "MaiBot.db")

# 确保数据库目录存在
os.makedirs(_DB_DIR, exist_ok=True)

# 全局 Peewee SQLite 数据库访问点
db = SqliteDatabase(
    _DB_FILE,
    pragmas={
        "journal_mode": "wal",  # WAL模式提高并发性能
        "cache_size": -64 * 1000,  # 64MB缓存
        "foreign_keys": 1,
        "ignore_check_constraints": 0,
        # synchronous=NORMAL：WAL 模式下的官方推荐组合。相比 0(OFF) 在断电/崩溃时
        # 几乎不损失性能，却能避免数据库损坏风险（对齐原项目做法）。
        "synchronous": 1,  # NORMAL
        # 锁住时最多等 5 秒再报错（而非立即失败）。配合后台清理已批量化，写锁占用极短，
        # 几乎不会再出现 database is locked；偶发争用也能在等待窗口内自动拿到锁。
        "busy_timeout": 5000,
    },
)
