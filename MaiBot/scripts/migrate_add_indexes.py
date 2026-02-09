"""
数据库索引迁移脚本

为现有数据库添加索引以提升查询性能。

运行方式：
    python scripts/migrate_add_indexes.py

注意：
    - 此脚本会为现有表添加索引
    - 在大型数据库上运行可能需要一些时间
    - 建议在运行前备份数据库
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.database.database import db
from src.common.logger import get_logger

logger = get_logger("migrate_indexes")


def add_indexes():
    """添加数据库索引"""
    logger.info("开始添加数据库索引...")

    try:
        with db:
            # Messages 表索引
            logger.info("添加 Messages 表索引...")
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_messages_time ON messages(time)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_messages_chat_info_stream_id ON messages(chat_info_stream_id)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_messages_chat_info_user_id ON messages(chat_info_user_id)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_messages_chat_id_time ON messages(chat_id, time)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_messages_user_id_time ON messages(user_id, time)')
            logger.info("✓ Messages 表索引添加完成")

            # ActionRecords 表索引
            logger.info("添加 ActionRecords 表索引...")
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_action_records_time ON action_records(time)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_action_records_chat_info_stream_id ON action_records(chat_info_stream_id)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_action_records_chat_id_time ON action_records(chat_id, time)')
            logger.info("✓ ActionRecords 表索引添加完成")

            # PersonInfo 表索引
            logger.info("添加 PersonInfo 表索引...")
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_person_info_person_name ON person_info(person_name)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_person_info_platform ON person_info(platform)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_person_info_platform_user_id ON person_info(platform, user_id)')
            logger.info("✓ PersonInfo 表索引添加完成")

            # ThinkingBack 表索引
            logger.info("添加 ThinkingBack 表索引...")
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_thinking_back_found_answer ON thinking_back(found_answer)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_thinking_back_update_time ON thinking_back(update_time)')
            logger.info("✓ ThinkingBack 表索引添加完成")

            # LLMUsage 表索引
            logger.info("添加 LLMUsage 表索引...")
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_llm_usage_model_assign_name ON llm_usage(model_assign_name)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_llm_usage_model_api_provider ON llm_usage(model_api_provider)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_llm_usage_user_id_timestamp ON llm_usage(user_id, timestamp)')
            db.execute_sql('CREATE INDEX IF NOT EXISTS idx_llm_usage_model_name_timestamp ON llm_usage(model_name, timestamp)')
            logger.info("✓ LLMUsage 表索引添加完成")

        logger.info("=" * 60)
        logger.info("✓ 所有索引添加完成！")
        logger.info("=" * 60)
        logger.info("索引统计：")
        logger.info("  - Messages: 6 个索引（4 个单列 + 2 个复合）")
        logger.info("  - ActionRecords: 3 个索引（2 个单列 + 1 个复合）")
        logger.info("  - PersonInfo: 3 个索引（2 个单列 + 1 个复合）")
        logger.info("  - ThinkingBack: 2 个索引")
        logger.info("  - LLMUsage: 4 个索引（2 个单列 + 2 个复合）")
        logger.info("  总计: 18 个新索引")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"添加索引时发生错误: {e}")
        raise


def verify_indexes():
    """验证索引是否创建成功"""
    logger.info("验证索引...")

    try:
        with db:
            # 获取所有表的索引信息
            tables = ['messages', 'action_records', 'person_info', 'thinking_back', 'llm_usage']

            for table in tables:
                result = db.execute_sql(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table}'")
                indexes = [row[0] for row in result.fetchall()]
                logger.info(f"{table} 表的索引: {len(indexes)} 个")
                for idx in indexes:
                    logger.info(f"  - {idx}")

    except Exception as e:
        logger.error(f"验证索引时发生错误: {e}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='数据库索引迁移脚本')
    parser.add_argument('--verify', action='store_true', help='验证索引是否存在')
    args = parser.parse_args()

    if args.verify:
        verify_indexes()
    else:
        logger.info("=" * 60)
        logger.info("数据库索引迁移脚本")
        logger.info("=" * 60)
        logger.info("注意：建议在运行前备份数据库")
        logger.info("")

        response = input("是否继续？(y/n): ")
        if response.lower() == 'y':
            add_indexes()
            logger.info("")
            logger.info("运行 'python scripts/migrate_add_indexes.py --verify' 来验证索引")
        else:
            logger.info("操作已取消")
