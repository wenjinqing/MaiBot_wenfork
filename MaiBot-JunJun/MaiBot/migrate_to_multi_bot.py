"""配置文件迁移工具：将单机器人配置迁移到多机器人格式"""
import sys
import os
import shutil
import tomlkit
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.common.logger import get_logger

logger = get_logger("migrate")


def migrate_single_to_multi_bot():
    """将单机器人配置迁移到多机器人格式"""
    config_path = PROJECT_ROOT / "config" / "bot_config.toml"
    backup_dir = PROJECT_ROOT / "config" / "backup"

    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        return False

    # 读取旧配置
    logger.info("正在读取现有配置文件...")
    with open(config_path, "r", encoding="utf-8") as f:
        old_config = tomlkit.load(f)

    # 检查是否已经是多机器人格式
    if "bots" in old_config:
        logger.info("配置文件已经是多机器人格式，无需迁移")
        return True

    # 备份旧配置
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"bot_config_before_multi_bot_{timestamp}.toml"
    shutil.copy2(config_path, backup_path)
    logger.info(f"已备份旧配置到: {backup_path}")

    # 创建新配置
    logger.info("正在转换为多机器人格式...")
    new_config = tomlkit.document()

    # 保留 inner 部分
    if "inner" in old_config:
        new_config["inner"] = old_config["inner"]

    # 创建 bots 数组
    bots_array = tomlkit.array()
    bots_array.multiline(True)

    # 创建第一个机器人实例（从旧配置迁移）
    bot_instance = tomlkit.table()
    bot_instance.add("bot_id", "maimai_main")
    bot_instance.add("enabled", True)
    bot_instance.add(tomlkit.nl())
    bot_instance.add(tomlkit.comment("机器人基础配置"))

    # 迁移各个配置段
    config_sections = [
        "bot", "personality", "relationship", "chat",
        "emoji", "expression", "keyword_reaction",
        "proactive_chat", "reminder", "repeat"
    ]

    for section in config_sections:
        if section in old_config:
            # 添加到 bots 表中，使用 [bots.section] 格式
            bot_instance[section] = old_config[section]

    bots_array.append(bot_instance)
    new_config["bots"] = bots_array

    # 添加共享配置段
    new_config.add(tomlkit.nl())
    new_config.add(tomlkit.comment("共享配置（所有机器人共用）"))

    shared_sections = [
        "message_receive", "chinese_typo", "response_post_process",
        "response_splitter", "telemetry", "experimental",
        "maim_message", "lpmm_knowledge", "tool", "memory",
        "debug", "mood", "voice", "jargon"
    ]

    for section in shared_sections:
        if section in old_config:
            new_config[section] = old_config[section]

    # 保存新配置
    logger.info("正在保存新配置文件...")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(new_config))

    logger.info("✅ 配置迁移完成！")
    logger.info(f"   - 旧配置已备份到: {backup_path}")
    logger.info(f"   - 新配置已保存到: {config_path}")
    logger.info("   - 已创建默认机器人实例: maimai_main")
    logger.info("")
    logger.info("📝 下一步：")
    logger.info("   1. 检查新配置文件，确认迁移正确")
    logger.info("   2. 如需添加第二个机器人，复制 [[bots]] 段并修改 bot_id 和 QQ 账号")
    logger.info("   3. 重启机器人")

    return True


def create_second_bot_example():
    """在配置文件中添加第二个机器人的示例"""
    config_path = PROJECT_ROOT / "config" / "bot_config.toml"

    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        return False

    # 读取配置
    with open(config_path, "r", encoding="utf-8") as f:
        config = tomlkit.load(f)

    if "bots" not in config:
        logger.error("配置文件不是多机器人格式，请先运行迁移")
        return False

    # 检查是否已经有第二个机器人
    if len(config["bots"]) >= 2:
        logger.info("配置文件中已经有多个机器人")
        return True

    # 创建第二个机器人实例（示例）
    logger.info("正在添加第二个机器人示例...")

    second_bot = tomlkit.table()
    second_bot.add("bot_id", "maimai_second")
    second_bot.add("enabled", False)  # 默认禁用，需要用户手动启用
    second_bot.add(tomlkit.nl())
    second_bot.add(tomlkit.comment("第二个机器人 - 请修改以下配置"))

    # 复制第一个机器人的配置作为模板
    first_bot = config["bots"][0]

    # Bot 配置
    bot_config = tomlkit.table()
    bot_config["platform"] = "qq"
    bot_config["qq_account"] = "请填写第二个机器人的QQ号"
    bot_config["nickname"] = "小麦"
    bot_config["alias_names"] = ["麦麦", "小麦子"]
    second_bot["bot"] = bot_config

    # Personality 配置
    personality_config = tomlkit.table()
    personality_config["personality"] = "我是一个温柔体贴的助手，喜欢帮助他人解决问题。"
    personality_config["reply_style"] = "语气温和友善，回复简洁明了。"
    personality_config["interest"] = "对技术、学习、生活话题感兴趣。"
    second_bot["personality"] = personality_config

    # 其他配置段复制第一个机器人的
    for section in ["relationship", "chat", "emoji", "expression",
                    "keyword_reaction", "proactive_chat", "reminder", "repeat"]:
        if section in first_bot:
            second_bot[section] = first_bot[section]

    config["bots"].append(second_bot)

    # 保存配置
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(config))

    logger.info("✅ 已添加第二个机器人示例！")
    logger.info("")
    logger.info("📝 下一步：")
    logger.info("   1. 打开配置文件，找到 [[bots]] 的第二个段落")
    logger.info("   2. 修改 qq_account 为实际的 QQ 号")
    logger.info("   3. 根据需要修改 nickname、personality 等配置")
    logger.info("   4. 将 enabled 改为 true")
    logger.info("   5. 重启机器人")

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("MaiBot 多机器人配置迁移工具")
    print("=" * 60)
    print()
    print("请选择操作：")
    print("1. 迁移现有配置到多机器人格式")
    print("2. 添加第二个机器人示例")
    print("3. 退出")
    print()

    choice = input("请输入选项 (1/2/3): ").strip()

    if choice == "1":
        migrate_single_to_multi_bot()
    elif choice == "2":
        create_second_bot_example()
    elif choice == "3":
        print("已退出")
    else:
        print("无效的选项")
