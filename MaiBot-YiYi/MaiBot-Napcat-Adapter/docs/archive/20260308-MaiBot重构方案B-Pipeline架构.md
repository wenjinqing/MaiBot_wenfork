# MaiBot 重构方案 B：中等改动方案

## 目标
引入统一的执行管道（Pipeline），解耦各个处理阶段，提升可维护性和可扩展性。

## 核心设计

### 1. Pipeline 架构

```python
# src/chat/pipeline/pipeline.py

from typing import List, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class PipelineContext:
    """流水线上下文，在各个阶段之间传递数据"""
    message: DatabaseMessages
    chat_stream: ChatStream

    # 阶段 1 输出
    execution_plan: Optional['ExecutionPlan'] = None

    # 阶段 2 输出
    tool_results: Optional[List[Dict[str, Any]]] = None
    tool_context: str = ""

    # 阶段 3 输出
    reply_text: Optional[str] = None
    sent: bool = False

    # 元数据
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ExecutionPlan:
    """执行计划"""
    need_reply: bool
    need_tools: List[str]  # 需要的工具名称列表
    action_type: str
    reasoning: str
    action_message: Optional[DatabaseMessages] = None


class PipelineStage(ABC):
    """流水线阶段基类"""

    @abstractmethod
    async def process(self, context: PipelineContext) -> PipelineContext:
        """处理上下文并返回更新后的上下文"""
        pass

    @abstractmethod
    def name(self) -> str:
        """阶段名称"""
        pass


class ChatPipeline:
    """聊天处理流水线"""

    def __init__(self):
        self.stages: List[PipelineStage] = []
        self.logger = get_logger("pipeline")

    def add_stage(self, stage: PipelineStage):
        """添加处理阶段"""
        self.stages.append(stage)
        return self

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行流水线"""
        self.logger.info(f"开始执行流水线，共 {len(self.stages)} 个阶段")

        for stage in self.stages:
            stage_name = stage.name()
            self.logger.debug(f"执行阶段: {stage_name}")

            try:
                context = await stage.process(context)
                self.logger.debug(f"阶段 {stage_name} 完成")
            except Exception as e:
                self.logger.error(f"阶段 {stage_name} 失败: {e}")
                raise

        self.logger.info("流水线执行完成")
        return context
```

### 2. 三个核心阶段

#### 阶段 1: 规划阶段（PlanningStage）

```python
# src/chat/pipeline/stages/planning_stage.py

class PlanningStage(PipelineStage):
    """规划阶段：分析消息并决定执行计划"""

    def __init__(self, action_planner: ActionPlanner):
        self.planner = action_planner
        self.logger = get_logger("planning_stage")

    def name(self) -> str:
        return "Planning"

    async def process(self, context: PipelineContext) -> PipelineContext:
        """执行规划"""
        # 调用现有的 ActionPlanner
        action_plan_infos = await self.planner.plan(
            chat_stream=context.chat_stream,
            available_actions=context.metadata.get("available_actions", {}),
            is_mentioned=context.metadata.get("is_mentioned", False)
        )

        # 转换为 ExecutionPlan
        if action_plan_infos and len(action_plan_infos) > 0:
            first_action = action_plan_infos[0]

            # 分析是否需要工具
            need_tools = self._analyze_tool_needs(
                action_type=first_action.action_type,
                message=context.message,
                reasoning=first_action.reasoning
            )

            context.execution_plan = ExecutionPlan(
                need_reply=(first_action.action_type == "reply"),
                need_tools=need_tools,
                action_type=first_action.action_type,
                reasoning=first_action.reasoning or "",
                action_message=first_action.action_message
            )

            self.logger.info(
                f"规划完成: action={first_action.action_type}, "
                f"need_tools={need_tools}"
            )
        else:
            # 无需执行任何动作
            context.execution_plan = ExecutionPlan(
                need_reply=False,
                need_tools=[],
                action_type="no_reply",
                reasoning="无需回复"
            )

        return context

    def _analyze_tool_needs(
        self,
        action_type: str,
        message: DatabaseMessages,
        reasoning: str
    ) -> List[str]:
        """分析是否需要工具（简化版，可以用 LLM 增强）"""
        if action_type != "reply":
            return []

        content = message.content.lower()

        # 简单的关键词匹配
        search_keywords = [
            "是真的吗", "怎么样", "听说", "查", "搜索",
            "最新", "新闻", "消息", "传闻"
        ]

        for keyword in search_keywords:
            if keyword in content:
                return ["web_search"]

        return []
```

#### 阶段 2: 工具执行阶段（ToolExecutionStage）

```python
# src/chat/pipeline/stages/tool_execution_stage.py

class ToolExecutionStage(PipelineStage):
    """工具执行阶段：执行所需的工具"""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.logger = get_logger("tool_execution_stage")

    def name(self) -> str:
        return "ToolExecution"

    async def process(self, context: PipelineContext) -> PipelineContext:
        """执行工具"""
        if not context.execution_plan or not context.execution_plan.need_tools:
            self.logger.debug("无需执行工具")
            return context

        from src.plugin_system.core.tool_use import ToolExecutor

        # 获取聊天历史
        chat_history = await context.chat_stream.get_raw_msg_before_timestamp_with_chat(
            timestamp=time.time(),
            limit=10
        )

        # 执行工具
        tool_executor = ToolExecutor(chat_id=self.chat_id)
        tool_results, used_tools, _ = await tool_executor.execute_from_chat_message(
            target_message=context.message.content,
            chat_history=chat_history,
            sender=context.message.sender,
            return_details=True
        )

        # 保存结果
        context.tool_results = tool_results

        # 格式化为上下文
        if tool_results:
            tool_context = "以下是你通过工具获取到的实时信息：\n"
            for tool_result in tool_results:
                tool_name = tool_result.get("tool_name", "unknown")
                content = tool_result.get("content", "")
                tool_context += f"- 【{tool_name}】: {content}\n"
            tool_context += "\n请基于以上信息回复用户。\n"

            context.tool_context = tool_context

            self.logger.info(f"工具执行完成，共执行 {len(used_tools)} 个工具: {used_tools}")

        return context
```

#### 阶段 3: 回复生成阶段（ReplyGenerationStage）

```python
# src/chat/pipeline/stages/reply_generation_stage.py

class ReplyGenerationStage(PipelineStage):
    """回复生成阶段：基于工具结果生成回复"""

    def __init__(self):
        self.logger = get_logger("reply_generation_stage")

    def name(self) -> str:
        return "ReplyGeneration"

    async def process(self, context: PipelineContext) -> PipelineContext:
        """生成回复"""
        if not context.execution_plan or not context.execution_plan.need_reply:
            self.logger.debug("无需生成回复")
            return context

        from src.chat.replyer.generator_api import generator_api

        # 调用现有的 Replyer
        success, llm_response = await generator_api.generate_reply(
            chat_stream=context.chat_stream,
            reply_message=context.execution_plan.action_message,
            available_actions=context.metadata.get("available_actions", {}),
            chosen_actions=context.metadata.get("chosen_actions", []),
            reply_reason=context.execution_plan.reasoning,
            extra_info=context.tool_context,  # 传入工具结果
            enable_tool=False,  # 禁用内部工具调用
            request_type="replyer",
            from_plugin=False,
        )

        if success and llm_response:
            context.reply_text = llm_response.content
            context.sent = True
            self.logger.info(f"回复生成成功: {context.reply_text[:50]}...")
        else:
            self.logger.warning("回复生成失败")

        return context
```

### 3. 集成到 BrainChatting

```python
# src/chat/brain_chat/brain_chat.py

class BrainChatting:
    def __init__(self, chat_stream: ChatStream):
        self.chat_stream = chat_stream

        # 初始化流水线
        self.pipeline = ChatPipeline()
        self.pipeline.add_stage(PlanningStage(self.action_planner))
        self.pipeline.add_stage(ToolExecutionStage(chat_id=chat_stream.stream_id))
        self.pipeline.add_stage(ReplyGenerationStage())

    async def _main_chat_loop(self, ...):
        """主循环"""
        # 创建上下文
        context = PipelineContext(
            message=latest_message,
            chat_stream=self.chat_stream,
            metadata={
                "available_actions": available_actions,
                "is_mentioned": is_mentioned,
                "chosen_actions": []
            }
        )

        # 执行流水线
        context = await self.pipeline.execute(context)

        # 处理结果
        if context.sent:
            logger.info("消息已发送")
        else:
            logger.debug("无需发送消息")
```

---

## 优点

1. ✅ **解耦各阶段**：每个阶段独立，易于测试和替换
2. ✅ **清晰的数据流**：PipelineContext 明确了数据在各阶段的传递
3. ✅ **易于扩展**：添加新阶段只需实现 PipelineStage 接口
4. ✅ **统一错误处理**：在 Pipeline 层统一处理异常
5. ✅ **解决工具调用时机问题**：工具在回复前执行

## 缺点

1. ⚠️ 需要创建多个新文件
2. ⚠️ 需要修改 BrainChatting 的主循环
3. ⚠️ 需要充分测试确保兼容性

## 实施步骤

1. 创建 `src/chat/pipeline/` 目录
2. 实现 `pipeline.py`（基础框架）
3. 实现三个 Stage 类
4. 修改 `brain_chat.py` 集成 Pipeline
5. 测试各个阶段
6. 逐步迁移现有功能

## 预期效果

- 代码结构更清晰
- 各模块职责明确
- 易于添加新功能（如缓存、重试、监控）
- 工具调用时机正确

---

## 迁移路径

### 第一步：并行运行
- 保留现有代码
- 新增 Pipeline 代码
- 通过配置开关选择使用哪个

### 第二步：逐步迁移
- 先迁移简单场景
- 验证功能正确性
- 逐步迁移复杂场景

### 第三步：完全替换
- 移除旧代码
- 清理冗余逻辑
