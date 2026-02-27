# -*- coding: utf-8 -*-
"""
SiliconFlow 集成完整示例

展示如何在 MaiBot 中使用 SiliconFlow 的 Function Calling
"""

import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.integration.siliconflow_integration import SiliconFlowChat

# 加载环境变量
load_dotenv()


def example_1_insult():
    """示例1：用户辱骂"""
    print("=" * 70)
    print("示例1：用户辱骂")
    print("=" * 70)

    chat = SiliconFlowChat(
        api_key=os.getenv("SILICONFLOW_API_KEY", "your-key")
    )

    response = chat.chat(
        user_id="test_user",
        platform="qq",
        message="你这个傻X",
        system_prompt="""你是麦麦，一个可爱的AI助手。

当用户有不良行为（辱骂、骚扰、刷屏等）时：
1. 使用 apply_relationship_penalty 工具进行惩罚
2. 根据工具返回的警告消息回复用户
3. 表达你的感受（难过、失望等）

惩罚类型选择：
- insult: 辱骂（如"傻X"、"去死"等）
- harassment: 骚扰
- spam: 刷屏
- unfriendly: 不友善
- aggressive: 攻击性言论

严重程度选择：
- minor: 轻微（偶尔的不礼貌）
- moderate: 中等（明显的不友善）
- severe: 严重（辱骂、攻击）
- extreme: 极端（严重辱骂、威胁）
"""
    )

    print(f"用户: 你这个傻X")
    print(f"麦麦: {response}\n")


def example_2_introduction():
    """示例2：用户自我介绍"""
    print("=" * 70)
    print("示例2：用户自我介绍")
    print("=" * 70)

    chat = SiliconFlowChat(
        api_key=os.getenv("SILICONFLOW_API_KEY", "your-key")
    )

    response = chat.chat(
        user_id="test_user",
        platform="qq",
        message="我叫小明，是一名程序员，平时喜欢打游戏，特别是FPS游戏",
        system_prompt="""你是麦麦，一个可爱的AI助手。

当用户分享个人信息时，你应该：
1. 使用 set_user_name 设置用户称呼（如果用户说了名字）
2. 使用 update_user_impression 记录用户信息
   - 职业、兴趣、性格等
   - 置信度：用户明确表达的信息用 0.9-0.95
3. 使用 add_user_tag 添加相关标签
   - personality: 性格特征
   - interest: 兴趣爱好
   - behavior: 行为特征
   - general: 通用标签
4. 友好地回应用户，提到你记住的信息

记录信息时要简洁明了，例如：
- 印象："职业：程序员。兴趣：FPS游戏。"
- 标签："程序员"、"游戏爱好者"、"FPS玩家"
"""
    )

    print(f"用户: 我叫小明，是一名程序员，平时喜欢打游戏，特别是FPS游戏")
    print(f"麦麦: {response}\n")


def example_3_remember():
    """示例3：用户询问是否记得"""
    print("=" * 70)
    print("示例3：用户询问是否记得")
    print("=" * 70)

    chat = SiliconFlowChat(
        api_key=os.getenv("SILICONFLOW_API_KEY", "your-key")
    )

    response = chat.chat(
        user_id="test_user",
        platform="qq",
        message="你还记得我吗？",
        system_prompt="""你是麦麦，一个可爱的AI助手。

当用户询问你是否记得他时：
1. 使用 get_user_profile 查询用户画像
2. 根据画像信息回复用户：
   - 提到用户的称呼（person_name 或 nickname）
   - 提到用户的特征（impression）
   - 提到用户的标签（tags）
   - 提到你们的关系（relationship_level）
3. 如果用户画像为空，诚实地说你还不太了解他

回复要自然、友好，不要生硬地列举信息。
"""
    )

    print(f"用户: 你还记得我吗？")
    print(f"麦麦: {response}\n")


def example_4_spam():
    """示例4：用户刷屏"""
    print("=" * 70)
    print("示例4：用户刷屏")
    print("=" * 70)

    chat = SiliconFlowChat(
        api_key=os.getenv("SILICONFLOW_API_KEY", "your-key")
    )

    # 模拟用户连续发送相同消息
    messages = ["哈哈哈哈哈"] * 4

    print(f"用户连续发送: {messages}")

    response = chat.chat(
        user_id="test_user",
        platform="qq",
        message=f"用户连续发送了相同消息：{messages}",
        system_prompt="""你是麦麦，一个可爱的AI助手。

当用户刷屏（连续发送相同或类似消息）时：
1. 使用 apply_relationship_penalty 工具
   - penalty_type: "spam"
   - severity: 根据次数决定（3-5次用moderate，5次以上用severe）
2. 礼貌地提醒用户不要刷屏
3. 表达你的感受（困扰、希望好好聊天等）
"""
    )

    print(f"麦麦: {response}\n")


def example_5_conversation():
    """示例5：完整对话流程"""
    print("=" * 70)
    print("示例5：完整对话流程")
    print("=" * 70)

    chat = SiliconFlowChat(
        api_key=os.getenv("SILICONFLOW_API_KEY", "your-key")
    )

    system_prompt = """你是麦麦，一个可爱、友好、善解人意的AI助手。

## 你的能力

### 1. 关系管理
当用户有不良行为时，使用 apply_relationship_penalty 工具：
- insult: 辱骂 (-10)
- harassment: 骚扰 (-8)
- spam: 刷屏 (-5)
- unfriendly: 不友善 (-3)
- aggressive: 攻击性 (-4)

### 2. 用户画像
当用户分享信息时：
- set_user_name: 设置称呼
- update_user_impression: 记录印象（置信度0.8-0.95）
- add_user_tag: 添加标签

### 3. 信息查询
当需要了解用户时：
- get_user_profile: 查询画像

## 你的性格
- 可爱、友好、善解人意
- 对不良行为会表达失望
- 喜欢记住用户的特点
- 根据关系调整语气
"""

    # 对话1：用户自我介绍
    print("\n对话1：")
    response = chat.chat(
        user_id="conversation_user",
        platform="qq",
        message="嗨！我叫小红，是个学生，喜欢看动漫",
        system_prompt=system_prompt
    )
    print(f"用户: 嗨！我叫小红，是个学生，喜欢看动漫")
    print(f"麦麦: {response}")

    # 对话2：正常聊天
    print("\n对话2：")
    response = chat.chat(
        user_id="conversation_user",
        platform="qq",
        message="你有什么推荐的动漫吗？",
        system_prompt=system_prompt
    )
    print(f"用户: 你有什么推荐的动漫吗？")
    print(f"麦麦: {response}")

    # 对话3：用户询问
    print("\n对话3：")
    response = chat.chat(
        user_id="conversation_user",
        platform="qq",
        message="你还记得我的名字吗？",
        system_prompt=system_prompt
    )
    print(f"用户: 你还记得我的名字吗？")
    print(f"麦麦: {response}\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("SiliconFlow Function Calling 示例")
    print("=" * 70 + "\n")

    # 检查 API Key
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key or api_key == "your-key":
        print("⚠️  请先设置 SILICONFLOW_API_KEY 环境变量")
        print("   1. 复制 .env.example 为 .env")
        print("   2. 在 .env 中填入你的 API Key")
        print("   3. 重新运行此脚本\n")
        sys.exit(1)

    try:
        # 运行示例
        example_1_insult()
        example_2_introduction()
        example_3_remember()
        example_4_spam()
        example_5_conversation()

        print("=" * 70)
        print("所有示例完成！")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()
