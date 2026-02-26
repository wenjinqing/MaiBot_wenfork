"""
测试好感度查询的自然回复生成
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_intimacy_reply_generation():
    """测试好感度查询回复生成"""
    print("=" * 60)
    print("测试好感度查询自然回复生成")
    print("=" * 60)

    # 模拟不同好感度等级的数据
    test_cases = [
        {
            "name": "挚友关系",
            "info": {
                "nickname": "张三",
                "relationship_value": 92.0,
                "relationship_level": "挚友",
                "mood_value": 85,
                "total_messages": 500,
                "is_in_love": False,
            }
        },
        {
            "name": "好友关系",
            "info": {
                "nickname": "李四",
                "relationship_value": 68.0,
                "relationship_level": "好友",
                "mood_value": 75,
                "total_messages": 150,
                "is_in_love": False,
            }
        },
        {
            "name": "熟人关系",
            "info": {
                "nickname": "王五",
                "relationship_value": 52.0,
                "relationship_level": "熟人",
                "mood_value": 60,
                "total_messages": 50,
                "is_in_love": False,
            }
        },
        {
            "name": "陌生关系",
            "info": {
                "nickname": "赵六",
                "relationship_value": 28.0,
                "relationship_level": "认识",
                "mood_value": 50,
                "total_messages": 10,
                "is_in_love": False,
            }
        },
        {
            "name": "恋人关系",
            "info": {
                "nickname": "小美",
                "relationship_value": 98.0,
                "relationship_level": "恋人",
                "mood_value": 95,
                "total_messages": 800,
                "is_in_love": True,
            }
        },
    ]

    print("\n测试用例：")
    for i, case in enumerate(test_cases, 1):
        info = case["info"]
        print(f"\n{i}. {case['name']}")
        print(f"   - 昵称：{info['nickname']}")
        print(f"   - 好感度：{info['relationship_value']:.1f}/100")
        print(f"   - 关系等级：{info['relationship_level']}")
        print(f"   - 心情值：{info['mood_value']}/100")
        print(f"   - 消息数：{info['total_messages']}")
        print(f"   - 恋人：{'是' if info['is_in_love'] else '否'}")

    print("\n" + "=" * 60)
    print("说明：")
    print("1. 这些是模拟数据，用于展示不同关系等级的回复风格")
    print("2. 实际使用时，机器人会根据真实的好感度数据生成回复")
    print("3. 每次查询的回复都会略有不同，因为是由大模型生成的")
    print("4. 要测试实际效果，请在 MaiBot 运行时向机器人发送'好感度'")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_intimacy_reply_generation())
