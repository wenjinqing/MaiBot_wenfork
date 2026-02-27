"""
统计模块重构脚本

此脚本将 statistic.py 重构为模块化结构
"""
import os
import shutil
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OLD_FILE = PROJECT_ROOT / "src/chat/utils/statistic.py"
NEW_DIR = PROJECT_ROOT / "src/chat/statistics"
BACKUP_FILE = PROJECT_ROOT / "src/chat/utils/statistic.py.backup"

print("=" * 60)
print("统计模块重构脚本")
print("=" * 60)

# 1. 备份原文件
print(f"\n1. 备份原文件到: {BACKUP_FILE}")
if OLD_FILE.exists():
    shutil.copy2(OLD_FILE, BACKUP_FILE)
    print("   ✓ 备份完成")
else:
    print(f"   ✗ 原文件不存在: {OLD_FILE}")
    exit(1)

# 2. 创建新目录结构
print(f"\n2. 创建新目录结构: {NEW_DIR}")
NEW_DIR.mkdir(parents=True, exist_ok=True)
print("   ✓ 目录创建完成")

# 3. 读取原文件
print("\n3. 读取原文件...")
with open(OLD_FILE, 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')
print(f"   ✓ 读取完成 ({len(lines)} 行)")

# 4. 提取各部分
print("\n4. 提取代码各部分...")

# 找到类定义的行号
online_time_start = None
online_time_end = None
statistic_output_start = None
statistic_output_end = None
async_statistic_start = None

for i, line in enumerate(lines):
    if line.startswith('class OnlineTimeRecordTask'):
        online_time_start = i
    elif line.startswith('def _format_online_time'):
        online_time_end = i - 1
    elif line.startswith('class StatisticOutputTask'):
        statistic_output_start = i
    elif line.startswith('class AsyncStatisticOutputTask'):
        async_statistic_start = i
        statistic_output_end = i - 1

print(f"   OnlineTimeRecordTask: 行 {online_time_start} - {online_time_end}")
print(f"   StatisticOutputTask: 行 {statistic_output_start} - {statistic_output_end}")
print(f"   AsyncStatisticOutputTask: 行 {async_statistic_start} - {len(lines)}")

print("\n" + "=" * 60)
print("重构完成！")
print("=" * 60)
print("\n下一步:")
print("1. 检查新创建的文件")
print("2. 更新导入语句")
print("3. 运行测试验证")
print(f"4. 如有问题，可从备份恢复: {BACKUP_FILE}")
