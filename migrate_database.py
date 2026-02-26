"""
数据库迁移脚本：为多机器人支持添加 bot_id 字段

此脚本将为以下表添加 bot_id 字段：
1. PersonInfo - 用户信息（关系、亲密度等）
2. ChatStreams - 聊天流
3. Messages - 消息记录
4. Expression - 表达学习
5. Jargon - 黑话学习
6. RelationshipHistory - 关系历史
7. ReminderTasks - 提醒任务

执行前会自动备份数据库。
"""

import sys
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.common.logger import get_logger

logger = get_logger("migrate_db")

# 数据库路径
DB_PATH = PROJECT_ROOT / "MaiBot.db"
BACKUP_DIR = PROJECT_ROOT / "database_backups"

# 默认 bot_id（用于现有数据）
DEFAULT_BOT_ID = "maimai_main"


def backup_database():
    """备份数据库"""
    if not DB_PATH.exists():
        logger.error(f"数据库文件不存在: {DB_PATH}")
        return None

    # 创建备份目录
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"MaiBot_before_multi_bot_{timestamp}.db"

    # 复制数据库文件
    shutil.copy2(DB_PATH, backup_path)
    logger.info(f"✅ 数据库已备份到: {backup_path}")

    return backup_path


def check_column_exists(cursor, table_name, column_name):
    """检查表中是否已存在指定列"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def add_bot_id_column(cursor, table_name, default_value=DEFAULT_BOT_ID):
    """为指定表添加 bot_id 列"""
    # 检查列是否已存在
    if check_column_exists(cursor, table_name, "bot_id"):
        logger.info(f"⚠️  表 {table_name} 已存在 bot_id 列，跳过")
        return False

    try:
        # 添加 bot_id 列，默认值为 maimai_main
        cursor.execute(f"""
            ALTER TABLE {table_name}
            ADD COLUMN bot_id TEXT DEFAULT '{default_value}'
        """)
        logger.info(f"✅ 表 {table_name} 已添加 bot_id 列")
        return True
    except sqlite3.OperationalError as e:
        logger.error(f"❌ 添加 bot_id 列到 {table_name} 失败: {e}")
        return False


def create_indexes(cursor):
    """创建复合索引以优化查询性能"""
    indexes = [
        # PersonInfo: (bot_id, platform, user_id) 复合索引
        ("idx_person_bot_platform_user", "person_info", ["bot_id", "platform", "user_id"]),

        # ChatStreams: (bot_id, stream_id) 复合索引
        ("idx_chatstreams_bot_stream", "chat_streams", ["bot_id", "stream_id"]),

        # Messages: (bot_id, chat_id) 复合索引
        ("idx_messages_bot_chat", "messages", ["bot_id", "chat_id"]),

        # Expression: (bot_id, chat_id) 复合索引
        ("idx_expression_bot_chat", "expression", ["bot_id", "chat_id"]),

        # Jargon: (bot_id, chat_id) 复合索引
        ("idx_jargon_bot_chat", "jargon", ["bot_id", "chat_id"]),

        # RelationshipHistory: (bot_id, user_id, platform) 复合索引
        ("idx_relationship_bot_user", "relationship_history", ["bot_id", "user_id", "platform"]),

        # ReminderTasks: (bot_id, person_id) 复合索引
        ("idx_reminder_bot_person", "reminder_tasks", ["bot_id", "person_id"]),
    ]

    for index_name, table_name, columns in indexes:
        try:
            # 检查索引是否已存在
            cursor.execute(f"""
                SELECT name FROM sqlite_master
                WHERE type='index' AND name='{index_name}'
            """)
            if cursor.fetchone():
                logger.info(f"⚠️  索引 {index_name} 已存在，跳过")
                continue

            # 创建索引
            columns_str = ", ".join(columns)
            cursor.execute(f"""
                CREATE INDEX {index_name}
                ON {table_name}({columns_str})
            """)
            logger.info(f"✅ 已创建索引: {index_name} on {table_name}({columns_str})")
        except sqlite3.OperationalError as e:
            logger.warning(f"⚠️  创建索引 {index_name} 失败: {e}")


def migrate_database():
    """执行数据库迁移"""
    logger.info("=" * 60)
    logger.info("开始数据库迁移：添加多机器人支持")
    logger.info("=" * 60)
    logger.info("")

    # 1. 备份数据库
    logger.info("步骤 1/4: 备份数据库")
    backup_path = backup_database()
    if not backup_path:
        logger.error("❌ 数据库备份失败，迁移中止")
        return False
    logger.info("")

    # 2. 连接数据库
    logger.info("步骤 2/4: 连接数据库")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        logger.info(f"✅ 已连接到数据库: {DB_PATH}")
    except Exception as e:
        logger.error(f"❌ 连接数据库失败: {e}")
        return False
    logger.info("")

    # 3. 添加 bot_id 列
    logger.info("步骤 3/4: 添加 bot_id 列")
    tables_to_migrate = [
        "person_info",
        "chat_streams",
        "messages",
        "expression",
        "jargon",
        "relationship_history",
        "reminder_tasks",
    ]

    success_count = 0
    for table_name in tables_to_migrate:
        if add_bot_id_column(cursor, table_name):
            success_count += 1

    conn.commit()
    logger.info(f"✅ 成功为 {success_count}/{len(tables_to_migrate)} 个表添加 bot_id 列")
    logger.info("")

    # 4. 创建索引
    logger.info("步骤 4/4: 创建复合索引")
    create_indexes(cursor)
    conn.commit()
    logger.info("")

    # 5. 验证迁移
    logger.info("验证迁移结果:")
    for table_name in tables_to_migrate:
        if check_column_exists(cursor, table_name, "bot_id"):
            # 统计该表的记录数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            logger.info(f"  ✅ {table_name}: bot_id 列已存在，共 {count} 条记录")
        else:
            logger.warning(f"  ⚠️  {table_name}: bot_id 列不存在")

    # 关闭连接
    conn.close()

    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ 数据库迁移完成！")
    logger.info("=" * 60)
    logger.info("")
    logger.info("📝 迁移总结:")
    logger.info(f"  - 备份文件: {backup_path}")
    logger.info(f"  - 已迁移表: {len(tables_to_migrate)} 个")
    logger.info(f"  - 默认 bot_id: {DEFAULT_BOT_ID}")
    logger.info("")
    logger.info("📝 下一步:")
    logger.info("  1. 检查数据库是否正常")
    logger.info("  2. 重启机器人")
    logger.info("  3. 如需添加第二个机器人，请修改配置文件")
    logger.info("")
    logger.info("⚠️  注意:")
    logger.info("  - 所有现有数据的 bot_id 已设置为 'maimai_main'")
    logger.info("  - 如果迁移失败，可以从备份恢复数据库")
    logger.info("")

    return True


def rollback_migration(backup_path):
    """回滚迁移（从备份恢复）"""
    if not backup_path or not Path(backup_path).exists():
        logger.error("❌ 备份文件不存在，无法回滚")
        return False

    try:
        # 关闭所有数据库连接
        logger.info("正在回滚迁移...")

        # 删除当前数据库
        if DB_PATH.exists():
            DB_PATH.unlink()

        # 从备份恢复
        shutil.copy2(backup_path, DB_PATH)
        logger.info(f"✅ 已从备份恢复数据库: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"❌ 回滚失败: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("MaiBot 多机器人数据库迁移工具")
    print("=" * 60)
    print()
    print("此工具将为数据库添加多机器人支持。")
    print()
    print("⚠️  重要提示:")
    print("  1. 迁移前会自动备份数据库")
    print("  2. 所有现有数据将关联到默认机器人 'maimai_main'")
    print("  3. 迁移过程不可逆（除非从备份恢复）")
    print()

    # 检查数据库是否存在
    if not DB_PATH.exists():
        print(f"❌ 错误: 数据库文件不存在: {DB_PATH}")
        print("   请确保机器人至少运行过一次以创建数据库。")
        sys.exit(1)

    # 确认迁移
    response = input("是否继续迁移？(yes/no): ").strip().lower()
    if response not in ["yes", "y"]:
        print("已取消迁移")
        sys.exit(0)

    print()

    # 执行迁移
    success = migrate_database()

    if not success:
        print()
        print("❌ 迁移失败！")
        print()
        response = input("是否从备份恢复数据库？(yes/no): ").strip().lower()
        if response in ["yes", "y"]:
            # 查找最新的备份
            if BACKUP_DIR.exists():
                backups = sorted(BACKUP_DIR.glob("MaiBot_before_multi_bot_*.db"))
                if backups:
                    latest_backup = backups[-1]
                    rollback_migration(latest_backup)
        sys.exit(1)
    else:
        print("✅ 迁移成功完成！")
        sys.exit(0)
