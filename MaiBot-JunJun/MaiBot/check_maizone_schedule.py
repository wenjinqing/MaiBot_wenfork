"""
Maizone 定时任务诊断脚本
用于检查定时发送说说功能是否正常工作
"""
import sys
import os
import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_config():
    """检查配置文件"""
    print("=" * 60)
    print("1. 检查 Maizone 配置文件")
    print("=" * 60)

    try:
        import toml
        config_path = "plugins/Maizone/config.toml"

        if not os.path.exists(config_path):
            print(f"[错误] 配置文件不存在: {config_path}")
            return False

        with open(config_path, 'r', encoding='utf-8') as f:
            config = toml.load(f)

        # 检查插件是否启用
        plugin_enabled = config.get('plugin', {}).get('enable', False)
        print(f"插件启用状态: {'已启用' if plugin_enabled else '未启用'}")

        # 检查定时任务是否启用
        schedule_enabled = config.get('schedule', {}).get('enable_schedule', False)
        print(f"定时任务启用状态: {'已启用' if schedule_enabled else '未启用'}")

        if not schedule_enabled:
            print("\n[警告] 定时任务未启用，请在配置文件中设置 enable_schedule = true")
            return False

        # 显示定时配置
        schedule_config = config.get('schedule', {})
        probability = schedule_config.get('probability', 1.0)
        schedule_times = schedule_config.get('schedule_times', [])
        fluctuation = schedule_config.get('fluctuation_minutes', 0)
        random_topic = schedule_config.get('random_topic', True)

        print(f"\n定时配置:")
        print(f"  - 发送概率: {probability * 100:.0f}%")
        print(f"  - 定时时间: {', '.join(schedule_times)}")
        print(f"  - 时间波动: +/-{fluctuation} 分钟")
        print(f"  - 随机主题: {'是' if random_topic else '否'}")

        # 计算今天的实际发送时间范围
        print(f"\n今天可能的发送时间范围:")
        for time_str in schedule_times:
            hour, minute = map(int, time_str.split(':'))
            base_minutes = hour * 60 + minute

            # 计算波动范围
            min_minutes = max(0, base_minutes - fluctuation)
            max_minutes = min(24 * 60 - 1, base_minutes + fluctuation)

            min_time = f"{min_minutes // 60:02d}:{min_minutes % 60:02d}"
            max_time = f"{max_minutes // 60:02d}:{max_minutes % 60:02d}"

            print(f"  - {time_str} -> {min_time} ~ {max_time}")

        print(f"\n[重要] 由于概率设置为 {probability * 100:.0f}%，今天有 {(1-probability) * 100:.0f}% 的概率不发送说说")
        print(f"[重要] 时间波动为 +/-{fluctuation} 分钟，实际发送时间会在上述范围内随机选择")

        return True

    except Exception as e:
        print(f"[错误] 检查配置文件失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_cookies():
    """检查 Cookie 状态"""
    print("\n" + "=" * 60)
    print("2. 检查 QQ 空间 Cookie 状态")
    print("=" * 60)

    try:
        cookie_file = "plugins/Maizone/cookies.json"

        if not os.path.exists(cookie_file):
            print("[警告] Cookie 文件不存在，首次发送时会自动获取")
            return True

        import json
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)

        if cookies:
            print(f"[正常] Cookie 文件存在，包含 {len(cookies)} 个 Cookie")
        else:
            print("[警告] Cookie 文件为空")

        return True

    except Exception as e:
        print(f"[警告] 检查 Cookie 失败: {e}")
        return True

def main():
    print("\n" + "=" * 60)
    print("Maizone 定时任务诊断工具")
    print("=" * 60)
    print(f"当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 检查配置
    config_ok = check_config()

    if not config_ok:
        print("\n" + "=" * 60)
        print("诊断结果: 配置问题")
        print("=" * 60)
        print("请检查配置文件并确保定时任务已启用")
        return

    # 检查 Cookie
    check_cookies()

    # 总结
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)

    print("\n可能导致不发空间的原因:")
    print("1. 今天的概率决定不发送（每天 0 点会重新随机决定是否发送）")
    print("2. 发送时间有波动，可能在你没注意的时候发送了")
    print("3. Cookie 过期导致发送失败（需要查看 MaiBot 运行日志）")
    print("4. MaiBot 进程没有运行或定时任务没有启动")

    print("\n建议:")
    print("1. 查看 MaiBot 启动日志，确认是否有 '定时发送说说任务已启动' 的消息")
    print("2. 如果想确保每天都发送，将 probability 设置为 1.0")
    print("3. 如果想减少时间波动，将 fluctuation_minutes 设置为较小的值（如 10）")
    print("4. 可以手动执行 /发说说 命令测试功能是否正常")
    print("5. 检查 QQ 空间是否有最近发送的说说（可能在你没注意时发送了）")

if __name__ == "__main__":
    main()
