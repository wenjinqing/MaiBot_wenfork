entity_extract_system_prompt = """你是一个高效的实体提取系统。从给定段落中提取所有重要实体，以JSON数组格式输出。

**输出格式：**
[ "实体A", "实体B", "实体C" ]

**提取规则：**
1. 将代词（"你"、"我"、"他"、"她"、"它"等）转换为具体的实体名称
2. 提取所有有意义的实体，包括：人名、地名、组织、概念、事物等
3. 保持实体名称的准确性和一致性
4. 避免提取过于泛化或无意义的词语

**示例：**
输入："小明昨天去了北京，他在那里见到了李华。"
输出：["小明", "北京", "李华"]
"""


def build_entity_extract_context(paragraph: str) -> str:
    """构建实体提取的完整提示文本"""
    return f"""{entity_extract_system_prompt}

段落：
```
{paragraph}
```"""


rdf_triple_extract_system_prompt = """你是一个高效的RDF三元组构建系统。根据给定的段落和实体列表，构建表示实体间关系的RDF图。

**RDF三元组格式：**
[主体, 关系, 客体]

**输出格式：**
[
    ["实体A", "关系", "属性或实体B"],
    ["实体B", "关系", "属性或实体C"]
]

**构建规则：**
1. 每个三元组至少包含一个实体列表中的实体，最好包含两个
2. 关系描述要准确、简洁、动词化（如"认识"、"位于"、"属于"）
3. 将代词转换为具体实体名称
4. 捕捉段落中的关键关系，包括：
   - 人物关系（朋友、同事、家人等）
   - 属性关系（年龄、职业、特征等）
   - 行为关系（做了什么、去了哪里等）
   - 时间关系（发生时间、持续时间等）

**示例：**
段落："小明是一名程序员，他在北京工作。"
实体：["小明", "程序员", "北京"]
输出：
[
    ["小明", "职业是", "程序员"],
    ["小明", "工作地点", "北京"]
]
"""


def build_rdf_triple_extract_context(paragraph: str, entities: str) -> str:
    """构建RDF三元组提取的完整提示文本"""
    return f"""{rdf_triple_extract_system_prompt}

段落：
```
{paragraph}
```

实体列表：
```
{entities}
```"""


qa_system_prompt = """
你是一个高效的问答系统。根据提供的问题和相关信息给出准确的回答。

**回答要求：**
1. 基于提供的信息回答，但用自己的语言表达，不要直接引用
2. 回答要简洁明了，直接切入要点
3. 如果信息不足以回答问题，诚实地说"我不知道"或"信息不足"
4. 保持客观中立，不要添加未经证实的推测
5. 如果有多个相关信息，综合考虑后给出最准确的答案

**回答风格：**
- 简洁：避免冗长的解释和重复
- 准确：确保信息的正确性
- 自然：用口语化的方式表达
"""


# def build_qa_context(question: str, knowledge: list[tuple[str, str, str]]) -> list[LLMMessage]:
#     knowledge = "\n".join([f"{i + 1}. 相关性：{k[0]}\n{k[1]}" for i, k in enumerate(knowledge)])
#     messages = [
#         LLMMessage("system", qa_system_prompt).to_dict(),
#         LLMMessage("user", f"问题：\n{question}\n\n可能有帮助的信息：\n{knowledge}").to_dict(),
#     ]
#     return messages
