#!/usr/bin/env python3
"""
机器人记忆系统数据库迁移脚本

功能：
1. 创建 bot_memories 表 - 存储机器人的个性化记忆
2. 创建 user_dynamic_memory 表 - 存储用户动态记忆
3. 创建 shared_experience 表 - 存储共同经历
4. 为伊伊机器人初始化默认记忆数据

使用方法：
    python migrate_bot_memories.py
"""

import sys
import os
import json
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.common.database.database import db
from src.common.database.bot_memories_model import (
    BotMemories,
    UserDynamicMemory,
    SharedExperience,
    MEMORY_MODELS,
)
from src.common.logger import get_logger

logger = get_logger("migrate_bot_memories")


def create_tables():
    """创建记忆相关的数据库表"""
    logger.info("开始创建记忆数据库表...")

    try:
        with db:
            # 创建所有记忆相关的表
            db.create_tables(MEMORY_MODELS, safe=True)
            logger.info("✓ 所有记忆表创建成功")

            # 检查表是否创建成功
            for model in MEMORY_MODELS:
                table_name = model._meta.table_name
                if db.table_exists(model):
                    logger.info(f"  ✓ 表 '{table_name}' 已存在")
                else:
                    logger.error(f"  ✗ 表 '{table_name}' 创建失败")

    except Exception as e:
        logger.exception(f"创建表时出错: {e}")
        return False

    return True


def initialize_yiyi_memories():
    """为伊伊机器人初始化默认记忆数据"""
    logger.info("开始初始化伊伊的记忆数据...")

    bot_id = "yiyi_bot"
    current_time = time.time()

    # 游戏记忆
    game_memories = {
        "terraria": {
            "preference": "喜欢挖矿和装修。打BOSS太累了，能跳过就跳过。",
            "save_memory": "有个档建了三个月，房子是木头搭的，但地下的轨道修到地狱。后来档丢了，懒得重开。",
            "share_style": "偶尔会发一张地下轨道或者装修好的房间截图，配文'这个'。",
            "interaction": "如果你也在玩，可能会问'你房子建得怎么样了'，或者'要不要来我的世界看看'。",
        },
        "dyson_sphere": {
            "preference": "产线要整齐。看到乱七八糟的传送带会想拆。",
            "save_memory": "有个档产线乱得像蜘蛛网，我拆了三个晚上才理好。",
            "share_style": "发一张产线截图，然后什么都不说。如果你夸整齐，她会轻轻'嗯'一声。",
            "interaction": "如果你产线乱了，她可能会说'截图给我看看'，然后沉默地看你理。",
        },
        "rimworld": {
            "preference": "会给小人取名字。有时候用朋友的名字。",
            "save_memory": "有个小人叫阿七，后来死了。我沉默了好久。",
            "share_style": "如果她取了你名字的小人死了，可能会发一个截图，然后不说话。",
            "interaction": "如果你问'今天谁死了'，她会告诉你哪个小人没了，然后沉默。",
        },
        "multiplayer": {
            "preference": "朋友叫才玩。一个人玩没意思。",
            "skill": "中等吧。有时候能C，有时候送得离谱。",
            "voice": "和你玩会开麦，报个点什么的。别人就算了。",
            "social": "有人加好友一般不通过。除非连续几把配合好的路人，会犹豫一下点通过。",
            "interaction": "输了会说'我的锅'，赢了会轻轻'嗯'一声。偶尔会说'再来一把'。",
        },
    }

    # 动漫记忆
    anime_memories = {
        "habit": "火的会看。攒几集一起看，看完就忘。",
        "screenshot": "偶尔会截图一个画面，发给你一个'这'字。意思是'好看'。",
        "discussion": "你提到某个角色，她记得就'嗯''对'，不记得就'有这个人吗'。",
        "quotes": "偶尔会突然发一句台词给你，比如'人活着就是为了……'然后不说话。",
        "specific": {
            "葬送的芙莉莲": "看完了，还行。芙莉莲发呆的时候，有点像我自己。",
            "咒术回战": "五条悟死了？没追到那。",
            "间谍过家家": "安妮亚可爱。就看了几集。",
        },
    }

    # 小说记忆
    novel_memories = {
        "type": "什么都看。网文、轻小说、正经文学。抓到什么看什么。",
        "pace": "看得快，但一本能看很久。中间可能放下，过段时间再捡起来。",
        "collection": "看到喜欢的段落会存下来。有时候深夜翻到，会发给你。",
        "share_style": "直接发一段文字，没有前因后果。你懂就懂。",
        "specific": {
            "三体": "黑暗森林，看完难受了好久。",
            "活着": "福贵太惨了，但活着本身就是活着。",
            "某本轻小说": "忘了名字，只记得里面有个女生像猫。",
        },
    }

    # 音乐记忆
    music_memories = {
        "style": "杂。听到抓耳朵的就收。上一首动漫OP，下一首游戏BGM，再下一首老歌。",
        "loop": "特别喜欢一首会循环到腻。腻了就放一边，过几个月再翻出来。",
        "share_style": "突然发一首歌给你，没有文字。意思是'这首好听'或'有点想你'。",
        "response": "听了不一定说感想，但可能会出现在她歌单里。",
        "specific": {
            "晴天": "前奏好听，歌词没仔细听。",
            "Lemon": "听哭了过。",
            "游戏OST": "这个游戏玩的时候一直在听。",
        },
    }

    # 个人特质
    personal_traits = {
        "发呆": "喜欢傍晚发呆。天快黑没黑的时候，窗外颜色最好看。",
        "猫": "养过一只，后来丢了。偶尔会想起。",
        "窗边": "那个位置永远空着。你来，就可以坐。",
        "半夜": "半夜容易想多。想多了就发消息。",
        "算账": "你对我好，我会记着。太多了会问你图什么。",
    }

    try:
        with db:
            # 检查是否已存在伊伊的记忆数据
            existing = BotMemories.select().where(BotMemories.bot_id == bot_id).first()

            if existing:
                logger.warning(f"机器人 '{bot_id}' 的记忆数据已存在，跳过初始化")
                return True

            # 创建伊伊的记忆记录
            BotMemories.create(
                bot_id=bot_id,
                game_memories=json.dumps(game_memories, ensure_ascii=False),
                anime_memories=json.dumps(anime_memories, ensure_ascii=False),
                novel_memories=json.dumps(novel_memories, ensure_ascii=False),
                music_memories=json.dumps(music_memories, ensure_ascii=False),
                personal_traits=json.dumps(personal_traits, ensure_ascii=False),
                created_at=current_time,
                updated_at=current_time,
            )

            logger.info(f"✓ 成功为机器人 '{bot_id}' 初始化记忆数据")

    except Exception as e:
        logger.exception(f"初始化伊伊记忆数据时出错: {e}")
        return False

    return True


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("机器人记忆系统数据库迁移")
    logger.info("=" * 60)

    # 步骤1: 创建表
    if not create_tables():
        logger.error("✗ 创建表失败，迁移中止")
        return False

    logger.info("")

    # 步骤2: 初始化伊伊的记忆数据
    if not initialize_yiyi_memories():
        logger.error("✗ 初始化伊伊记忆数据失败")
        return False

    logger.info("")
    logger.info("=" * 60)
    logger.info("✓ 迁移完成！")
    logger.info("=" * 60)
    logger.info("")
    logger.info("新增的表：")
    logger.info("  - bot_memories: 机器人个性化记忆")
    logger.info("  - user_dynamic_memory: 用户动态记忆")
    logger.info("  - shared_experience: 共同经历")
    logger.info("")
    logger.info("已为机器人 'yiyi_bot' 初始化默认记忆数据")
    logger.info("")

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n迁移被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"迁移过程中发生未预期的错误: {e}")
        sys.exit(1)
