# 戳一戳功能问题修复

## 问题描述

控制台显示戳一戳发送成功，但实际并未执行。

**日志示例：**
```
[消息发送] 已将消息  '[command:{'name': 'send_poke', 'args': {'qq_id': 3155572670}}]'  发往平台'qq'
[poke_plugin] 戳一戳发送成功
```

但实际没有执行戳一戳操作。

## 问题分析

1. **命令匹配错误**：在 `send_command_handler.py` 中，`match` 语句使用了 `CommandType.SEND_POKE.name`（返回 `"SEND_POKE"`），但命令数据中的 `name` 字段是 `"send_poke"`（枚举的 `.value`）。应该使用 `.value` 而不是 `.name` 来匹配。

2. **日志显示问题**：日志中显示的 `[command:{'name': 'send_poke', ...}]` 是 `processed_plain_text`（用于显示的文本），不是实际传输的命令数据。实际传输的 `message_segment.data` 应该是字典格式。

3. **缺少调试日志**：Napcat Adapter 的命令处理缺少详细的调试日志，无法确定命令是否被正确接收和处理。

4. **错误处理不完善**：如果命令处理失败，可能没有记录详细的错误信息。

## 修复内容

### 1. 修复命令匹配逻辑（`send_command_handler.py`）**（关键修复）**

修复了 `handle_command` 方法中的命令匹配：
- **将所有的 `CommandType.XXX.name` 改为 `CommandType.XXX.value`**
- 原因：命令数据中的 `name` 字段是枚举的值（如 `"send_poke"`），不是枚举名称（如 `"SEND_POKE"`）
- 这导致所有命令都无法正确匹配，现在已修复

### 1.1. 修复 Napcat API 名称（`__init__.py`）**（关键修复）**

修复了 `CommandType.SEND_POKE` 的值：
- **从 `"send_poke"` 改为 `"group_poke"`**
- 原因：根据 Napcat 的 API 定义，群聊戳一戳应该使用 `group_poke` 而不是 `send_poke`
- `send_poke` 可能导致 Napcat 无法识别命令，从而超时

### 2. 添加详细日志（`main_send_handler.py`）

在 `send_command` 方法中添加了详细的调试日志：
- 记录接收到的命令数据
- 记录群信息
- 记录处理后的命令和参数
- 记录 Napcat 的响应
- 添加异常堆栈跟踪

### 3. 修复戳一戳命令处理（`send_command_handler.py`）

修复了 `handle_poke_command` 方法：
- 确保群聊戳一戳必须有有效的 `group_id`
- 添加更严格的参数验证
- 改进错误提示

## 验证方法

修复后，重新运行程序并触发戳一戳功能，应该能看到以下日志：

1. **MaiBot 日志**：
   ```
   [消息发送] 已将消息  '[command:{'name': 'send_poke', ...}]'  发往平台'qq'
   ```

2. **Napcat Adapter 日志**（新增）：
   ```
   接收到来自MaiBot的消息，处理中
   处理命令中
   命令数据: {'name': 'send_poke', 'args': {'qq_id': 3155572670}}
   群信息: 1158561385
   处理后的命令: send_poke, 参数: {'group_id': 1158561385, 'user_id': 3155572670}
   准备发送命令到Napcat: send_poke, 参数: {...}
   Napcat响应: {'status': 'ok', ...}
   命令 send_poke 执行成功
   ```

如果命令执行失败，会看到详细的错误信息，便于进一步诊断。

## 可能的问题原因

如果修复后仍然无法执行，可能的原因包括：

1. **Napcat 连接问题**：检查 Napcat 是否正常运行
2. **权限问题**：检查 Bot 是否有戳一戳的权限
3. **参数格式问题**：检查 Napcat API 是否接受当前的参数格式
4. **消息类型识别问题**：检查命令是否被正确识别为 `command` 类型

## 下一步

如果问题仍然存在，请检查：
1. Napcat Adapter 的完整日志输出
2. Napcat 服务器的日志
3. 确认 Napcat API 的戳一戳接口格式是否正确

