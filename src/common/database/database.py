import os
from peewee import SqliteDatabase
from rich.traceback import install

install(extra_lines=3)


# 定义数据库文件路径
ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DB_DIR = os.path.join(ROOT_PATH, "data")

# 根据 BOT_ID 环境变量选择不同的数据库文件
BOT_ID = os.environ.get('BOT_ID', 'maimai_main')

# 为不同的机器人使用不同的数据库文件
if BOT_ID == 'yiyi_bot':
    _DB_FILE = os.path.join(_DB_DIR, "MaiBot_yiyi.db")
elif BOT_ID == 'junjun_main':
    _DB_FILE = os.path.join(_DB_DIR, "MaiBot_junjun.db")
else:
    # 默认数据库（向后兼容）
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
        "synchronous": 0,  # 异步写入提高性能
        "busy_timeout": 1000,  # 1秒超时而不是3秒
    },
)
