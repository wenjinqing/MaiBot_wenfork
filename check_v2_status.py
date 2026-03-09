"""
检查新架构状态
"""

import sys
from pathlib import Path

print("=" * 60)
print("检查 MaiBot 新架构状态")
print("=" * 60)

# 检查配置文件
print("\n[1] 检查配置文件...")
junjun_config = Path("MaiBot-JunJun/MaiBot/config/bot_config.toml")
yiyi_config = Path("MaiBot-YiYi/MaiBot/config/bot_config.toml")

for name, config_file in [("君君", junjun_config), ("伊伊", yiyi_config)]:
    if config_file.exists():
        content = config_file.read_text(encoding='utf-8')

        import re
        match = re.search(r'use_v2_architecture\s*=\s*(\w+)', content)

        if match:
            enabled = match.group(1).lower() == 'true'
            status = "[OK] 已启用" if enabled else "[FAIL] 未启用"
            print(f"  {name}: use_v2_architecture = {match.group(1)} {status}")
        else:
            print(f"  {name}: [FAIL] 未找到 use_v2_architecture 配置")
    else:
        print(f"  {name}: [FAIL] 配置文件不存在")

# 检查新架构文件
print("\n[2] 检查新架构文件...")
required_files = [
    "MaiBot-JunJun/MaiBot/src/chat_v2/handler/__init__.py",
    "MaiBot-JunJun/MaiBot/src/chat_v2/handler/message_handler.py",
    "MaiBot-JunJun/MaiBot/src/chat_v2/agent/unified_agent.py",
    "MaiBot-JunJun/MaiBot/src/chat_v2/models/context.py",
    "MaiBot-JunJun/MaiBot/src/chat_v2/executor/tool_executor.py",
]

all_exist = True
for file_path in required_files:
    exists = Path(file_path).exists()
    status = "[OK]" if exists else "[FAIL]"
    print(f"  {status} {file_path}")
    if not exists:
        all_exist = False

# 检查入口点
print("\n[3] 检查消息处理入口...")
bot_file = Path("MaiBot-JunJun/MaiBot/src/chat/message_receive/bot.py")

if bot_file.exists():
    content = bot_file.read_text(encoding='utf-8')

    checks = {
        "检查 use_v2_architecture 配置": "hasattr(global_config.inner, 'use_v2_architecture')" in content,
        "导入新架构 handler": "from src.chat_v2.handler import get_message_handler" in content,
        "调用新架构处理": "handler = get_message_handler()" in content,
        "发送回复": "await sender.send_message(reply)" in content,
    }

    for check, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check}")
else:
    print("  [FAIL] bot.py 文件不存在")

# 检查伊伊的文件
print("\n[4] 检查伊伊的新架构文件...")
yiyi_files = [
    "MaiBot-YiYi/MaiBot/src/chat_v2/handler/message_handler.py",
    "MaiBot-YiYi/MaiBot/src/chat_v2/agent/unified_agent.py",
    "MaiBot-YiYi/MaiBot/src/chat_v2/models/context.py",
]

yiyi_all_exist = True
for file_path in yiyi_files:
    exists = Path(file_path).exists()
    status = "[OK]" if exists else "[FAIL]"
    print(f"  {status} {file_path}")
    if not exists:
        yiyi_all_exist = False

print("\n" + "=" * 60)
print("状态总结")
print("=" * 60)

if all_exist and yiyi_all_exist:
    print("\n[OK] 所有新架构文件都存在")
    print("\n新架构应该已经在运行。如果没有看到效果，可能的原因：")
    print("  1. 机器人没有重启")
    print("  2. 日志级别设置过高，看不到 '使用新架构 (chat_v2) 处理消息' 日志")
    print("  3. 消息没有触发回复（talk_value 设置、planner 判断等）")
    print("\n建议操作：")
    print("  1. 重启机器人")
    print("  2. 在配置文件中设置 console_log_level = 'INFO'")
    print("  3. 发送消息后查看日志，应该能看到：")
    print("     - '使用新架构 (chat_v2) 处理消息'")
    print("     - '为聊天 xxx 创建新的 Agent'")
    print("     - '消息处理成功 [chat=xxx] LLM调用=X次 工具调用=X次'")
else:
    print("\n[FAIL] 部分新架构文件缺失")
    print("\n需要补充缺失的文件")

print("\n" + "=" * 60)
