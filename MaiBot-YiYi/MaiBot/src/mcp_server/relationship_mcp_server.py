"""
MCP 服务器 - 亲密度与用户画像管理

提供给大模型使用的 MCP 工具服务器
"""

import asyncio
import json
from typing import Any, Sequence
from mcp.server import Server
from mcp.types import Tool, TextContent
from pydantic import AnyUrl

# 导入工具函数
from src.common.relationship_penalty import mcp_apply_relationship_penalty
from src.common.user_profile_manager import (
    mcp_update_user_impression,
    mcp_add_user_tag,
    mcp_get_user_profile,
    mcp_set_user_name
)

# 创建 MCP 服务器
app = Server("maibot-relationship")


# 定义工具
@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用的工具"""
    return [
        Tool(
            name="apply_relationship_penalty",
            description="""
应用亲密度惩罚。当检测到用户的不良行为时使用此工具。

使用场景：
- 用户辱骂、骚扰
- 刷屏、无脑复制
- 不友善、攻击性言论
- 不尊重、消极态度

惩罚类型：
- insult: 辱骂 (-10.0)
- harassment: 骚扰 (-8.0)
- spam: 刷屏 (-5.0)
- unfriendly: 不友善 (-3.0)
- inappropriate: 不当内容 (-5.0)
- aggressive: 攻击性 (-4.0)
- disrespect: 不尊重 (-3.0)
- negative_attitude: 消极态度 (-2.0)
- ignore_response: 无视回复 (-1.0)
- cold_response: 冷淡回复 (-0.5)

严重程度：
- minor: 轻微 (0.5x)
- moderate: 中等 (1.0x)
- severe: 严重 (1.5x)
- extreme: 极端 (2.0x)

注意：extreme 级别可能导致恋爱关系破裂！
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "用户ID"
                    },
                    "platform": {
                        "type": "string",
                        "description": "平台 (qq/wechat等)"
                    },
                    "penalty_type": {
                        "type": "string",
                        "enum": [
                            "insult", "harassment", "spam", "unfriendly",
                            "inappropriate", "aggressive", "disrespect",
                            "negative_attitude", "ignore_response", "cold_response"
                        ],
                        "description": "惩罚类型"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["minor", "moderate", "severe", "extreme"],
                        "description": "严重程度",
                        "default": "moderate"
                    },
                    "reason": {
                        "type": "string",
                        "description": "惩罚原因（供日志记录）"
                    }
                },
                "required": ["user_id", "platform", "penalty_type"]
            }
        ),
        Tool(
            name="update_user_impression",
            description="""
更新用户印象。当你对用户有新的认识时使用此工具。

使用场景：
- 用户分享了个人信息（兴趣、爱好、性格等）
- 通过多次对话了解到用户的特点
- 用户的行为模式显示出某种特征

置信度指南：
- 0.9-1.0: 非常确定（用户明确表达，或多次验证）
- 0.7-0.9: 比较确定（基于明确的行为或陈述）
- 0.5-0.7: 一般确定（基于推测或单次观察）
- <0.5: 不确定（不会更新）

示例：
- "喜欢玩FPS游戏，特别是《三角洲行动》" (confidence=0.9)
- "性格温和，说话礼貌" (confidence=0.8)
- "可能是学生，经常晚上聊天" (confidence=0.6)
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "用户ID"
                    },
                    "platform": {
                        "type": "string",
                        "description": "平台"
                    },
                    "impression": {
                        "type": "string",
                        "description": "印象描述（简洁的文字描述）"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "置信度 (0-1)",
                        "minimum": 0,
                        "maximum": 1,
                        "default": 0.8
                    }
                },
                "required": ["user_id", "platform", "impression"]
            }
        ),
        Tool(
            name="add_user_tag",
            description="""
添加用户标签。用简短的标签来标记用户特征。

标签分类：
- personality: 性格特征（温和、活泼、内向、外向、幽默等）
- interest: 兴趣爱好（游戏、动漫、音乐、运动、编程等）
- behavior: 行为特征（话痨、夜猫子、早起、秒回、慢热等）
- relationship: 关系特征（好友、熟人、陌生人、闺蜜等）
- general: 通用标签

示例：
- personality: "温和", "活泼", "内向", "幽默"
- interest: "游戏爱好者", "动漫迷", "音乐发烧友"
- behavior: "夜猫子", "话痨", "秒回消息"
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "用户ID"
                    },
                    "platform": {
                        "type": "string",
                        "description": "平台"
                    },
                    "tag": {
                        "type": "string",
                        "description": "标签名称"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["personality", "interest", "behavior", "relationship", "general"],
                        "description": "标签分类",
                        "default": "general"
                    }
                },
                "required": ["user_id", "platform", "tag"]
            }
        ),
        Tool(
            name="get_user_profile",
            description="""
获取用户的完整画像。在需要了解用户背景信息时使用。

返回信息包括：
- 基本信息（昵称、称呼）
- 关系信息（亲密度、关系等级、是否恋爱中）
- 互动信息（总消息数、聊天频率、认识天数）
- 印象和标签
- 心情值

使用场景：
- 需要根据用户特征调整回复风格
- 需要了解用户的兴趣爱好
- 需要查看与用户的关系状态
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "用户ID"
                    },
                    "platform": {
                        "type": "string",
                        "description": "平台"
                    }
                },
                "required": ["user_id", "platform"]
            }
        ),
        Tool(
            name="set_user_name",
            description="""
设置用户的特殊称呼。当用户自我介绍或你想给用户起昵称时使用。

使用场景：
- 用户自我介绍："我叫小明"
- 用户要求特定称呼："叫我阿伟就好"
- 根据特征起昵称："游戏大神"、"夜猫子"

注意：
- 称呼应该友好、尊重
- 如果用户明确表示不喜欢某个称呼，应该更改
- 恋爱模式下可以使用更亲密的称呼
            """.strip(),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "用户ID"
                    },
                    "platform": {
                        "type": "string",
                        "description": "平台"
                    },
                    "name": {
                        "type": "string",
                        "description": "称呼名称"
                    },
                    "reason": {
                        "type": "string",
                        "description": "设置原因"
                    }
                },
                "required": ["user_id", "platform", "name"]
            }
        )
    ]


# 处理工具调用
@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """处理工具调用"""

    try:
        if name == "apply_relationship_penalty":
            result = mcp_apply_relationship_penalty(
                user_id=arguments["user_id"],
                platform=arguments["platform"],
                penalty_type=arguments["penalty_type"],
                severity=arguments.get("severity", "moderate"),
                reason=arguments.get("reason", "")
            )

        elif name == "update_user_impression":
            result = mcp_update_user_impression(
                user_id=arguments["user_id"],
                platform=arguments["platform"],
                impression=arguments["impression"],
                confidence=arguments.get("confidence", 0.8)
            )

        elif name == "add_user_tag":
            result = mcp_add_user_tag(
                user_id=arguments["user_id"],
                platform=arguments["platform"],
                tag=arguments["tag"],
                category=arguments.get("category", "general")
            )

        elif name == "get_user_profile":
            result = mcp_get_user_profile(
                user_id=arguments["user_id"],
                platform=arguments["platform"]
            )

        elif name == "set_user_name":
            result = mcp_set_user_name(
                user_id=arguments["user_id"],
                platform=arguments["platform"],
                name=arguments["name"],
                reason=arguments.get("reason", "")
            )

        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "success": False
            }, ensure_ascii=False)
        )]


# 运行服务器
async def main():
    """运行 MCP 服务器"""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
