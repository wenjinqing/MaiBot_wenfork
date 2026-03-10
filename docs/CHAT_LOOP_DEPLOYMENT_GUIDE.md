# ChatLoop 部署指南

## 概述

ChatLoop（持续运行的聊天循环）已经完成开发，本文档说明如何在 MaiBot 系统中部署和使用这个功能。

## 当前状态

### 已完成
- ✅ ChatLoop 核心实现（`src/chat_v2/loop/chat_loop.py`）
- ✅ 完整的文档和示例
- ✅ 三个机器人实例都已同步代码

### 待集成
- ⏳ 在实际的 Bot 启动流程中集成 ChatLoop
- ⏳ 配置定时任务
- ⏳ 与现有的主动对话系统协调

## 部署选项

### 选项 1：替换现有的主动对话系统（推荐）

当前系统使用 `ProactiveChatManager`，可以用 ChatLoop 替换以获得更强大的功能。

**优势：**
- 统一的架构
- 更灵活的定时任务
- 与 chat_v2 架构完全集成
- 支持多种主动发言策略

**步骤：**

1. 在 `src/chat_v2/agent/unified_agent.py` 中添加 ChatLoop 支持：

```python
class UnifiedChatAgent:
    def __init__(self, chat_stream):
        # ... 现有代码 ...

        # 创建 ChatLoop（可选）
        self.chat_loop = None
        if global_config.enable_chat_loop:  # 需要在配置中添加此选项
            from src.chat_v2.loop.chat_loop import chat_loop_manager
            self.chat_loop = chat_loop_manager.create_loop(
                chat_id=chat_stream.stream_id,
                agent=self,
                chat_stream=chat_stream,
                loop_interval=5.0,
                enable_proactive_speak=True,
                enable_scheduled_tasks=True,
                enable_observation=True
            )

    async def start_loop(self):
        """启动聊天循环"""
        if self.chat_loop:
            await self.chat_loop.start()

    async def stop_loop(self):
        """停止聊��循环"""
        if self.chat_loop:
            await self.chat_loop.stop()
```

2. 在 `src/main.py` 的初始化流程中启动 ChatLoop：

```python
async def _init_shared_components(self):
    # ... 现有代码 ...

    # 替换 ProactiveChatManager 为 ChatLoop
    if global_config.enable_chat_loop:
        from src.chat_v2.loop.chat_loop import chat_loop_manager

        # 为每个活跃的聊天创建循环
        # 这里需要根据实际情况调整
        logger.info("ChatLoop 系统已启动")
    else:
        # 保留原有的 ProactiveChatManager
        from src.proactive_system.proactive_chat_manager import ProactiveChatManager
        proactive_chat_manager = ProactiveChatManager()
        if proactive_chat_manager.enabled:
            await async_task_manager.add_task(proactive_chat_manager)
            logger.info("主动对话管理器已启动")
```

### 选项 2：与现有系统并存（保守）

保留 `ProactiveChatManager`，ChatLoop 作为可选功能。

**优势：**
- 风险较低
- 可以逐步迁移
- 保持向后兼容

**步骤：**

1. 添加配置选项到 `config.toml`：

```toml
[chat_loop]
enabled = false  # 默认禁用
loop_interval = 5.0
enable_proactive_speak = true
enable_scheduled_tasks = true
enable_observation = true
```

2. 在需要的地方手动创建 ChatLoop：

```python
# 在特定的聊天中启用 ChatLoop
from src.chat_v2.loop.chat_loop import chat_loop_manager

loop = chat_loop_manager.create_loop(
    chat_id=chat_stream.stream_id,
    agent=agent,
    chat_stream=chat_stream
)
await loop.start()
```

### 选项 3：仅用于定时任务（最小化）

只使用 ChatLoop 的定时任务功能，不启用主动发言。

**优势：**
- 最小化影响
- 专注于定时任务
- 资源占用少

**步骤：**

```python
from src.chat_v2.loop.chat_loop import chat_loop_manager, ScheduledTask

# 创建仅用于定时任务的循环
loop = chat_loop_manager.create_loop(
    chat_id=chat_stream.stream_id,
    agent=None,
    chat_stream=chat_stream,
    enable_proactive_speak=False,  # 禁用主动发言
    enable_scheduled_tasks=True,   # 只启用定时任务
    enable_observation=False       # 禁用观察
)

# 添加定时任务
async def morning_greeting():
    await chat_stream.send_message("早上好！")

loop.add_scheduled_task(ScheduledTask(
    name="morning_greeting",
    callback=morning_greeting,
    cron_hour=9,
    cron_minute=0
))

await loop.start()
```

## 配置示例

### 定时任务配置

```python
# 每天早上 9 点发送早安
async def morning_greeting():
    await chat_stream.send_message("早上好！新的一天开始了！☀️")

loop.add_scheduled_task(ScheduledTask(
    name="morning_greeting",
    callback=morning_greeting,
    cron_hour=9,
    cron_minute=0
))

# 每天晚上 21 点发送晚安
async def night_greeting():
    await chat_stream.send_message("晚安！做个好梦！🌙")

loop.add_scheduled_task(ScheduledTask(
    name="night_greeting",
    callback=night_greeting,
    cron_hour=21,
    cron_minute=0
))

# 每小时检查一次空闲时间
async def check_idle():
    idle_time = loop.observation_data.get("idle_time", 0)
    if idle_time > 7200:  # 超过 2 小时
        await chat_stream.send_message("好久没人说话了，大家都在忙吗？")

loop.add_scheduled_task(ScheduledTask(
    name="check_idle",
    callback=check_idle,
    interval=3600  # 每小时
))
```

## 性能考虑

### 资源占用

- **循环间隔**：默认 5 秒，可根据需要调整
  - 高频（1-2 秒）：响应快，资源占用高
  - 正常（5-10 秒）：平衡，推荐
  - 低频（30-60 秒）：节省资源，响应慢

- **并发循环数**：每个聊天一个循环
  - 10 个聊天：可忽略
  - 100 个聊天：需要监控
  - 1000+ 个聊天：建议优化或分批启动

### 优化建议

1. **按需启动**：只为活跃的聊天创建循环
2. **动态调整**：根据活跃度调整循环间隔
3. **延迟启动**：系统启动后延迟创建循环
4. **批量管理**：使用 ChatLoopManager 统一管理

```python
# 只为最近活跃的聊天创建循环
from datetime import datetime, timedelta

async def start_loops_for_active_chats():
    chat_manager = get_chat_manager()
    active_threshold = datetime.now() - timedelta(days=7)

    for chat in chat_manager.get_active_chats(since=active_threshold):
        loop = chat_loop_manager.create_loop(
            chat_id=chat.stream_id,
            agent=UnifiedChatAgent(chat),
            chat_stream=chat
        )
        await loop.start()
```

## 监控和调试

### 日志

ChatLoop 会输出详细的日志：

```
[chat_loop] [chat_123] 聊天循环已初始化
[chat_loop] [chat_123] 聊天循环已启动
[chat_loop] [chat_123] 执行定时任务: morning_greeting
[chat_loop] [chat_123] 定时任务执行成功: morning_greeting
[chat_loop] [chat_123] 主动发言: 群聊长时间没人说话
```

### 状态检查

```python
# 检查循环状态
loop = chat_loop_manager.get_loop(chat_id)
if loop:
    print(f"运行中: {loop.running}")
    print(f"定时任务数: {len(loop.scheduled_tasks)}")
    print(f"空闲时间: {loop.observation_data.get('idle_time', 0)}")
```

## 迁移路径

### 阶段 1：测试（1-2 周）
- 在少数测试群中启用 ChatLoop
- 观察性能和稳定性
- 收集用户反馈

### 阶段 2：试点（2-4 周）
- 扩展到更多群组
- 优化配置参数
- 完善定时任务

### 阶段 3：全面部署（1-2 周）
- 替换 ProactiveChatManager
- 更新文档
- 培训用户

## 回滚计划

如果遇到问题，可以快速回滚：

1. 停止所有 ChatLoop：
```python
await chat_loop_manager.stop_all()
```

2. 恢复 ProactiveChatManager：
```python
# 在配置中禁用 ChatLoop
global_config.enable_chat_loop = False
```

3. 重启系统

## 常见问题

### Q: ChatLoop 和 ProactiveChatManager 有什么区别？

A:
- ChatLoop 是新架构的一部分，与 chat_v2 完全集成
- 支持更灵活的定时任务（cron 和 interval）
- 提供持续观察功能
- 更好的性能和可扩展性

### Q: 是否必须使用 ChatLoop？

A: 不是必须的。ChatLoop 是可选功能，可以根据需求选择是否启用。

### Q: 如何避免主动发言过于频繁？

A: ChatLoop 内置了冷却机制（默认 1 小时），并且使用 Planner 智能判断是否需要发言。

### Q: 可以为不同的聊天配置不同的定时任务吗？

A: 可以。每个聊天都有独立的 ChatLoop 实例，可以配置不同的任务。

## 下一步

1. 决定使用哪个部署选项
2. 在测试环境中验证
3. 逐步推广到生产环境
4. 收集反馈并优化

## 相关文档

- [ChatLoop 集成指南](../MaiM-with-u/MaiBot/src/chat_v2/docs/CHAT_LOOP_INTEGRATION.md)
- [ChatLoop 示例](../MaiM-with-u/MaiBot/src/chat_v2/examples/chat_loop_example.py)
- [新架构总结](./NEW_ARCHITECTURE_SUMMARY.md)
