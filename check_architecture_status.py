"""
检查新架构是否被应用的快速脚本
"""

print("=" * 60)
print("新架构应用检查")
print("=" * 60)

print("\n请在机器人日志中查找以下关键信息：")
print("\n1. 启动时应该看到：")
print("   - 配置加载相关日志")
print("   - 没有配置文件解析错误")

print("\n2. 收到消息时应该看到：")
print("   [DEBUG] 检查新架构配置: hasattr=True")
print("   [DEBUG] use_v2_architecture 值: True")
print("   [INFO] 使用新架构 (chat_v2) 处理消息")

print("\n3. 如果看到以下内容，说明使用的是旧架构：")
print("   [bc] [xxx的私聊] 开始第X次思考")
print("   [DEBUG] 使用旧架构 (heartflow) 处理消息")

print("\n4. 新架构的标志：")
print("   [INFO] 为聊天 xxx 创建新的 Agent")
print("   [INFO] 消息处理成功 [chat=xxx] LLM调用=X次 工具调用=X次")

print("\n" + "=" * 60)
print("如何重启机器人：")
print("=" * 60)

print("\n方法1：如果在终端运行")
print("  1. 按 Ctrl+C 停止机器人")
print("  2. 重新运行: python bot.py")

print("\n方法2：如果在后台运行")
print("  1. 找到进程: ps aux | grep bot.py")
print("  2. 停止进程: kill <进程ID>")
print("  3. 重新启动: python bot.py &")

print("\n方法3：Windows 任务管理器")
print("  1. 打开任务管理器")
print("  2. 找到 python.exe 进程（运行 bot.py 的）")
print("  3. 结束进程")
print("  4. 重新启动机器人")

print("\n" + "=" * 60)
print("重启后测试：")
print("=" * 60)

print("\n1. 发送一条消息给机器人")
print("2. 查看日志，确认看到 '使用新架构 (chat_v2) 处理消息'")
print("3. 如果还是看到旧架构的日志，检查配置文件")

print("\n配置文件位置：")
print("  君君: MaiBot-JunJun/MaiBot/config/bot_config.toml")
print("  伊伊: MaiBot-YiYi/MaiBot/config/bot_config.toml")

print("\n确认配置项：")
print("  use_v2_architecture = true  # 第5行左右")

print("\n" + "=" * 60)
