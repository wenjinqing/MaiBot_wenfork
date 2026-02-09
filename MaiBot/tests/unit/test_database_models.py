"""测试数据库模型"""
import pytest
from src.common.database.database_model import Messages, PersonInfo, ChatStreams


@pytest.mark.unit
@pytest.mark.database
def test_messages_model_creation(test_db, sample_message):
    """测试 Messages 模型的创建"""
    with test_db.bind_ctx([Messages]):
        msg = Messages.create(**sample_message)
        assert msg.message_id == 'test_msg_001'
        assert msg.chat_id == 'test_chat_001'
        assert msg.user_id == 'user_123'
        assert msg.content == '测试消息内容'


@pytest.mark.unit
@pytest.mark.database
def test_messages_query_by_chat_id(test_db, sample_message):
    """测试按 chat_id 查询消息"""
    with test_db.bind_ctx([Messages]):
        Messages.create(**sample_message)

        results = list(Messages.select().where(Messages.chat_id == 'test_chat_001'))
        assert len(results) == 1
        assert results[0].message_id == 'test_msg_001'


@pytest.mark.unit
@pytest.mark.database
def test_person_info_unique_constraint(test_db, sample_person):
    """测试 PersonInfo 的唯一性约束"""
    with test_db.bind_ctx([PersonInfo]):
        PersonInfo.create(**sample_person)

        # 尝试创建相同 person_id 的记录应该失败
        with pytest.raises(Exception):  # IntegrityError
            PersonInfo.create(
                person_id='person_001',
                person_name='另一个用户',
                platform='qq',
                user_id='user_456'
            )


@pytest.mark.unit
@pytest.mark.database
def test_person_info_query_by_name(test_db, sample_person):
    """测试按名称查询用户"""
    with test_db.bind_ctx([PersonInfo]):
        PersonInfo.create(**sample_person)

        results = list(PersonInfo.select().where(PersonInfo.person_name == '测试用户'))
        assert len(results) == 1
        assert results[0].person_id == 'person_001'


@pytest.mark.unit
@pytest.mark.database
def test_chat_streams_creation(test_db, sample_chat_stream):
    """测试 ChatStreams 模型的创建"""
    with test_db.bind_ctx([ChatStreams]):
        stream = ChatStreams.create(**sample_chat_stream)
        assert stream.stream_id == 'stream_001'
        assert stream.stream_name == '测试群聊'
        assert stream.platform == 'qq'


@pytest.mark.unit
@pytest.mark.database
def test_messages_time_range_query(test_db):
    """测试时间范围查询"""
    with test_db.bind_ctx([Messages]):
        # 创建多条消息
        for i in range(5):
            Messages.create(
                message_id=f'msg_{i}',
                chat_id='chat_001',
                user_id='user_123',
                content=f'消息 {i}',
                time=1704067200 + i * 100
            )

        # 查询时间范围
        results = list(Messages.select().where(
            (Messages.chat_id == 'chat_001') &
            (Messages.time >= 1704067200 + 200)
        ))
        assert len(results) == 3  # msg_2, msg_3, msg_4


@pytest.mark.unit
@pytest.mark.database
def test_messages_count(test_db):
    """测试消息计数"""
    with test_db.bind_ctx([Messages]):
        # 创建多条消息
        for i in range(10):
            Messages.create(
                message_id=f'msg_{i}',
                chat_id='chat_001',
                user_id='user_123',
                content=f'消息 {i}',
                time=1704067200 + i
            )

        count = Messages.select().where(Messages.chat_id == 'chat_001').count()
        assert count == 10
