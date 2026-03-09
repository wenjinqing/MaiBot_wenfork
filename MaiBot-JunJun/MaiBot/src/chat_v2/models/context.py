"""
核心数据模型：AgentContext 和相关数据结构
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    TOOL_EXECUTION = "tool_execution"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ToolCall:
    """工具调用信息"""
    tool_name: str
    arguments: Dict[str, Any]
    call_id: Optional[str] = None


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_name: str
    success: bool
    content: Any
    error: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class AgentContext:
    """Agent 执行上下文"""
    # 输入数据
    message: Any  # DatabaseMessages
    chat_history: List[Any] = field(default_factory=list)
    available_tools: List[Dict[str, Any]] = field(default_factory=list)
    bot_config: Dict[str, Any] = field(default_factory=dict)

    # 用户信息
    relationship_info: Optional[Dict[str, Any]] = None  # 关系信息
    mood_info: Optional[Dict[str, Any]] = None  # 心情信息
    memory_info: Optional[str] = None  # 记忆检索信息（新增）

    # 执行状态
    status: ExecutionStatus = ExecutionStatus.PENDING

    # 第一次 LLM 调用结果
    need_tools: bool = False
    tool_calls: List[ToolCall] = field(default_factory=list)
    initial_response: str = ""
    reasoning: str = ""

    # 工具执行结果
    tool_results: List[ToolResult] = field(default_factory=list)

    # 最终回复
    final_response: str = ""

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 性能指标
    llm_calls: int = 0
    total_time: float = 0.0
    tool_execution_time: float = 0.0


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    context: Optional[AgentContext] = None

    # 统计信息
    llm_calls: int = 0
    tool_calls: int = 0
    total_time: float = 0.0

    # 频率控制标志
    no_reply: bool = False  # True 表示因频率控制而不回复
