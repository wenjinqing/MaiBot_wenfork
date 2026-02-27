"""
伊伊机器人的详细记忆数据库模型
存储游戏、动漫、小说、音乐等兴趣爱好的详细记忆
"""

from peewee import Model, TextField, IntegerField, FloatField
from .database import db
from src.common.logger import get_logger

logger = get_logger("bot_memories_model")


class BaseModel(Model):
    class Meta:
        database = db


class BotMemories(BaseModel):
    """
    机器人个性化记忆表
    存储每个机器人的兴趣爱好、个人癖好等详细记忆
    """

    # 机器人ID
    bot_id = TextField(index=True)  # 机器人唯一标识

    # 游戏记忆 (JSON格式存储)
    game_memories = TextField(null=True)  # 游戏相关记忆，如泰拉瑞亚、戴森球计划等

    # 动漫记忆 (JSON格式存储)
    anime_memories = TextField(null=True)  # 动漫相关记忆，追番习惯、喜欢的角色等

    # 小说记忆 (JSON格式存储)
    novel_memories = TextField(null=True)  # 小说阅读记忆，喜欢的书籍、段落等

    # 音乐记忆 (JSON格式存储)
    music_memories = TextField(null=True)  # 音乐相关记忆，歌单、喜欢的歌曲等

    # 个人特质 (JSON格式存储)
    personal_traits = TextField(null=True)  # 个人癖好，如发呆、养猫、窗边等

    # 创建时间
    created_at = FloatField()  # 记录创建时间戳

    # 更新时间
    updated_at = FloatField()  # 最后更新时间戳

    class Meta:
        table_name = "bot_memories"
        indexes = (
            # 为bot_id创建唯一索引
            (('bot_id',), True),  # True表示唯一索引
        )


class UserDynamicMemory(BaseModel):
    """
    用户动态记忆表
    存储机器人对特定用户的动态记忆（如共同经历、特殊事件等）
    """

    # 机器人ID
    bot_id = TextField(index=True)

    # 用户标识
    platform = TextField(index=True)  # 平台
    user_id = TextField(index=True)  # 用户ID

    # 记忆类型
    memory_type = TextField(index=True)  # 记忆类型：game_event, anime_discussion, music_share, personal_moment等

    # 记忆内容
    memory_content = TextField()  # 记忆的详细内容

    # 记忆标签
    memory_tags = TextField(null=True)  # 记忆标签，逗号分隔，如"泰拉瑞亚,联机,有趣"

    # 重要程度
    importance = IntegerField(default=5)  # 重要程度 1-10，影响记忆检索优先级

    # 情感色彩
    emotion = TextField(null=True)  # 情感色彩：happy, sad, funny, touching等

    # 关联的聊天流ID
    chat_id = TextField(null=True, index=True)

    # 创建时间
    created_at = FloatField(index=True)

    # 最后访问时间
    last_accessed = FloatField(null=True)

    # 访问次数
    access_count = IntegerField(default=0)

    class Meta:
        table_name = "user_dynamic_memory"
        indexes = (
            # 复合索引用于按机器人和用户查询
            (('bot_id', 'platform', 'user_id'), False),
            # 按记忆类型和时间查询
            (('memory_type', 'created_at'), False),
        )


class SharedExperience(BaseModel):
    """
    共同经历表
    记录机器人与用户的共同经历（如一起玩游戏、看番、听歌等）
    """

    # 机器人ID
    bot_id = TextField(index=True)

    # 用户标识
    platform = TextField(index=True)
    user_id = TextField(index=True)

    # 经历类型
    experience_type = TextField(index=True)  # game, anime, music, chat等

    # 经历标题
    title = TextField()  # 如"一起玩泰拉瑞亚"、"讨论咒术回战"

    # 经历描述
    description = TextField()  # 详细描述

    # 开始时间
    start_time = FloatField(index=True)

    # 结束时间
    end_time = FloatField(null=True)

    # 是否进行中
    is_ongoing = IntegerField(default=0)  # 0=已结束, 1=进行中

    # 相关数据 (JSON格式)
    related_data = TextField(null=True)  # 如游戏存档信息、番剧集数等

    # 情感评价
    emotion_rating = IntegerField(null=True)  # 1-10，这段经历的情感评分

    class Meta:
        table_name = "shared_experience"
        indexes = (
            # 复合索引
            (('bot_id', 'platform', 'user_id', 'experience_type'), False),
        )


# 导出所有模型
MEMORY_MODELS = [
    BotMemories,
    UserDynamicMemory,
    SharedExperience,
]


def create_memory_tables():
    """创建记忆相关的数据库表"""
    with db:
        db.create_tables(MEMORY_MODELS)
        logger.info("记忆数据库表创建成功")


def initialize_memory_database():
    """初始化记忆数据库，检查表是否存在，不存在则创建"""
    try:
        with db:
            for model in MEMORY_MODELS:
                table_name = model._meta.table_name
                if not db.table_exists(model):
                    logger.warning(f"表 '{table_name}' 未找到，正在创建...")
                    db.create_tables([model])
                    logger.info(f"表 '{table_name}' 创建成功")
        logger.info("记忆数据库初始化完成")
    except Exception as e:
        logger.exception(f"初始化记忆数据库时出错: {e}")
