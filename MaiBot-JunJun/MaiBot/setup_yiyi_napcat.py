#!/usr/bin/env python3
"""
伊伊Napcat适配器自动配置脚本

功能：
1. 复制适配器目录
2. 修改配置文件
3. 创建Napcat配置文件
4. 生成启动脚本

使用方法：
    python setup_yiyi_napcat.py --qq 你的伊伊QQ号
"""

import os
import sys
import shutil
import json
import argparse
from pathlib import Path


def setup_yiyi_adapter(yiyi_qq: str, base_dir: str = None):
    """设置伊伊的Napcat适配器"""

    if base_dir is None:
        base_dir = Path(__file__).parent.parent
    else:
        base_dir = Path(base_dir)

    print("=" * 60)
    print("伊伊Napcat适配器自动配置")
    print("=" * 60)
    print()

    # 路径定义
    junjun_adapter = base_dir / "MaiBot-Napcat-Adapter"
    yiyi_adapter = base_dir / "MaiBot-Napcat-Adapter-Yiyi"

    # 步骤1: 复制适配器目录
    print("步骤1: 复制适配器目录...")
    if yiyi_adapter.exists():
        print(f"  ⚠ 目录已存在: {yiyi_adapter}")
        response = input("  是否覆盖? (y/n): ")
        if response.lower() != 'y':
            print("  跳过复制")
        else:
            shutil.rmtree(yiyi_adapter)
            shutil.copytree(junjun_adapter, yiyi_adapter)
            print(f"  ✓ 已复制到: {yiyi_adapter}")
    else:
        shutil.copytree(junjun_adapter, yiyi_adapter)
        print(f"  ✓ 已复制到: {yiyi_adapter}")

    print()

    # 步骤2: 修改适配器配置
    print("步骤2: 修改适配器配置...")
    config_file = yiyi_adapter / "config.toml"

    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 修改端口
        content = content.replace('port = 8096', 'port = 8097')

        # 清空白名单（用户可以后续手动配置）
        content = content.replace(
            'group_list = [1158561385]',
            'group_list = []  # 请根据需要配置伊伊的群组白名单'
        )
        content = content.replace(
            'private_list = [2215368145,3155572670,2991064865]',
            'private_list = []  # 请根据需要配置伊伊的私聊白名单'
        )

        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  ✓ 已修改配置文件: {config_file}")
        print("  - Napcat端口: 8096 -> 8097")
        print("  - 已清空白名单（请手动配置）")
    else:
        print(f"  ✗ 配置文件不存在: {config_file}")

    print()

    # 步骤3: 创建Napcat配置文件
    print("步骤3: 创建Napcat配置文件...")

    napcat_config = {
        "http": {
            "enable": False,
            "host": "0.0.0.0",
            "port": 3001
        },
        "ws": {
            "enable": True,
            "host": "0.0.0.0",
            "port": 8097
        },
        "reverseWs": {
            "enable": False
        },
        "heartInterval": 30000,
        "token": "",
        "debug": False,
        "log": {
            "level": "info"
        }
    }

    napcat_config_file = base_dir / "napcat_yiyi.json"
    with open(napcat_config_file, 'w', encoding='utf-8') as f:
        json.dump(napcat_config, f, indent=2, ensure_ascii=False)

    print(f"  ✓ 已创建Napcat配置: {napcat_config_file}")
    print(f"  - WebSocket端口: 8097")
    print(f"  - QQ账号: {yiyi_qq}")

    print()

    # 步骤4: 创建启动脚本
    print("步骤4: 创建启动脚本...")

    # Windows批处理脚本
    bat_script = f"""@echo off
echo Starting YiYi's Napcat and Adapter...

echo Starting Napcat for YiYi...
start "Napcat-YiYi" napcat --config napcat_yiyi.json --qq {yiyi_qq}

timeout /t 5

echo Starting Adapter for YiYi...
start "Adapter-YiYi" cmd /k "cd MaiBot-Napcat-Adapter-Yiyi && python main.py"

echo YiYi's services started!
pause
"""

    bat_file = base_dir / "start_yiyi.bat"
    with open(bat_file, 'w', encoding='utf-8') as f:
        f.write(bat_script)

    print(f"  ✓ 已创建Windows启动脚本: {bat_file}")

    # Linux/Mac Shell脚本
    sh_script = f"""#!/bin/bash

echo "Starting YiYi's Napcat and Adapter..."

echo "Starting Napcat for YiYi..."
napcat --config napcat_yiyi.json --qq {yiyi_qq} &

sleep 5

echo "Starting Adapter for YiYi..."
cd MaiBot-Napcat-Adapter-Yiyi && python main.py &

echo "YiYi's services started!"
"""

    sh_file = base_dir / "start_yiyi.sh"
    with open(sh_file, 'w', encoding='utf-8') as f:
        f.write(sh_script)

    # 添加执行权限
    os.chmod(sh_file, 0o755)

    print(f"  ✓ 已创建Linux/Mac启动脚本: {sh_file}")

    print()
    print("=" * 60)
    print("配置完成！")
    print("=" * 60)
    print()
    print("下一步操作：")
    print()
    print("1. 配置白名单（可选）")
    print(f"   编辑: {config_file}")
    print("   添加允许伊伊聊天的群组和用户")
    print()
    print("2. 启动伊伊的服务")
    print("   Windows: 双击 start_yiyi.bat")
    print("   Linux/Mac: ./start_yiyi.sh")
    print()
    print("3. 启动MaiBot主程序")
    print("   cd MaiBot && python src/main.py")
    print()
    print("4. 访问管理界面")
    print("   http://localhost:8001/bot-management.html")
    print()
    print("注意事项：")
    print("- 确保伊伊的QQ账号已登录Napcat")
    print("- 确保端口8097未被占用")
    print("- 确保MaiBot配置中伊伊的QQ账号正确")
    print()


def main():
    parser = argparse.ArgumentParser(description='伊伊Napcat适配器自动配置脚本')
    parser.add_argument('--qq', required=True, help='伊伊的QQ账号')
    parser.add_argument('--base-dir', help='项目根目录（默认为脚本所在目录的父目录）')

    args = parser.parse_args()

    try:
        setup_yiyi_adapter(args.qq, args.base_dir)
    except Exception as e:
        print(f"✗ 配置失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
