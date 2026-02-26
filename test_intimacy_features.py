"""
测试好感度功能
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.relationship_query import RelationshipQuery


async def test_intimacy_query():
    """测试好感度查询"""
    print("=" * 60)
    print("测试好感度查询功能")
    print("=" * 60)

    # 测试关键词检测
    test_messages = [
        "好感度",
        "查询亲密度",
        "我们的关系",
        "喜欢我吗",
        "今天天气真好",  # 不应该触发
    ]

    print("\n1. 测试关键词检测:")
    for msg in test_messages:
        result = RelationshipQuery.check_query_keywords(msg)
        status = "[触发]" if result else "[不触发]"
        print(f"  '{msg}' -> {status}")

    # 测试查询功能（需要数据库中有数据）
    print("\n2. 测试查询功能:")
    print("  注意：需要数据库中有用户数据才能看到结果")
    print("  可以在 MaiBot 运行时与机器人聊天后再测试")


if __name__ == "__main__":
    asyncio.run(test_intimacy_query())
