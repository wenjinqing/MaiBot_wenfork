from src.chat.utils.prompt_builder import Prompt
# from src.memory_system.memory_activator import MemoryActivator


def init_rewrite_prompt():
    Prompt("你正在qq群里聊天，下面是群里正在聊的内容:", "chat_target_group1")
    Prompt("你正在和{sender_name}聊天，这是你们之前聊的内容：", "chat_target_private1")
    Prompt("正在群里聊天", "chat_target_group2")
    Prompt("和{sender_name}聊天", "chat_target_private2")

    Prompt(
        """
{expression_habits_block}
{chat_target}
{chat_info}
{identity}

**场景：**
你正在{chat_target_2}，{reply_target_block}

**改写任务：**
原始内容：{raw_reply}
改写原因：{reason}

**改写要求：**
1. 将原始内容改写成适合当前聊天场景的回复
2. 使用自然、口语化的表达方式
3. 符合你的表达风格和语言习惯
4. 参考聊天上下文，确保回复贴合话题
5. 可以完全重组句子结构，但保留核心含义
6. 保持语意通顺、表达自然
7. {reply_style}
8. {keywords_reaction_prompt}

**输出规范：**
{moderation_prompt}
- 只输出改写后的回复内容
- 不要添加冒号、引号、表情包、emoji、@符号等
- 不要过度思考，保持简洁
- 直接输出改写后的一句话

改写后的回复：
""",
        "default_expressor_prompt",
    )
