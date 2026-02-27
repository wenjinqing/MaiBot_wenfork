"""pytest 全局配置和共享 fixtures"""
import pytest
import tempfile
from pathlib import Path


@pytest.fixture(scope="session")
def test_db():
    """创建测试数据库"""
    try:
        from peewee import SqliteDatabase
        from src.common.database.database_model import (
            ChatStreams, Messages, LLMUsage, PersonInfo,
            Emoji, ActionRecords, ThinkingBack, KnowledgeBase,
            ExpressionLearning, BlackWords, OnlineTime
        )
    except ImportError as e:
        pytest.skip(f"数据库模块未安装: {e}")

    db = SqliteDatabase(':memory:')

    # 创建表
    with db:
        db.create_tables([
            ChatStreams, Messages, LLMUsage, PersonInfo,
            Emoji, ActionRecords, ThinkingBack, KnowledgeBase,
            ExpressionLearning, BlackWords, OnlineTime
        ])

    yield db

    # 清理
    db.close()


@pytest.fixture
def temp_log_dir():
    """临时日志目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_message():
    """示例消息数据"""
    return {
        'message_id': 'test_msg_001',
        'chat_id': 'test_chat_001',
        'user_id': 'user_123',
        'content': '测试消息内容',
        'time': 1704067200,
    }


@pytest.fixture
def sample_person():
    """示例用户数据"""
    return {
        'person_id': 'person_001',
        'person_name': '测试用户',
        'platform': 'qq',
        'user_id': 'user_123',
    }


@pytest.fixture
def sample_chat_stream():
    """示例聊天流数据"""
    return {
        'stream_id': 'stream_001',
        'stream_name': '测试群聊',
        'platform': 'qq',
    }
