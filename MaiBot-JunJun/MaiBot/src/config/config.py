import os
import tomlkit
import shutil
import sys

from datetime import datetime
from tomlkit import TOMLDocument
from tomlkit.items import Table, KeyType
from dataclasses import field, dataclass
from rich.traceback import install
from typing import List, Optional

from src.common.logger import get_logger
from src.common.toml_utils import format_toml_string
from src.config.config_base import ConfigBase
from src.config.official_configs import (
    BotConfig,
    PersonalityConfig,
    ExpressionConfig,
    ChatConfig,
    EmojiConfig,
    KeywordReactionConfig,
    ChineseTypoConfig,
    ResponsePostProcessConfig,
    ResponseSplitterConfig,
    TelemetryConfig,
    ExperimentalConfig,
    MessageReceiveConfig,
    MaimMessageConfig,
    LPMMKnowledgeConfig,
    RelationshipConfig,
    ToolConfig,
    VoiceConfig,
    MoodConfig,
    MemoryConfig,
    DebugConfig,
    JargonConfig,
    ProactiveChatConfig,
    ReminderConfig,
    RepeatConfig,
    BotInstanceConfig,
)

from .api_ada_configs import (
    ModelTaskConfig,
    ModelInfo,
    APIProvider,
)


install(extra_lines=3)


# 配置主程序日志格式
logger = get_logger("config")

# 获取当前文件所在目录的父目录的父目录（即MaiBot项目根目录）
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "template")

# 考虑到，实际上配置文件中的mai_version是不会自动更新的,所以采用硬编码
# 对该字段的更新，请严格参照语义化版本规范：https://semver.org/lang/zh-CN/
MMC_VERSION = "0.11.6"


def get_key_comment(toml_table, key):
    # 获取key的注释（如果有）
    if hasattr(toml_table, "trivia") and hasattr(toml_table.trivia, "comment"):
        return toml_table.trivia.comment
    if hasattr(toml_table, "value") and isinstance(toml_table.value, dict):
        item = toml_table.value.get(key)
        if item is not None and hasattr(item, "trivia"):
            return item.trivia.comment
    if hasattr(toml_table, "keys"):
        for k in toml_table.keys():
            if isinstance(k, KeyType) and k.key == key:  # type: ignore
                return k.trivia.comment  # type: ignore
    return None


def compare_dicts(new, old, path=None, logs=None):
    # 递归比较两个dict，找出新增和删减项，收集注释
    if path is None:
        path = []
    if logs is None:
        logs = []
    # 新增项
    for key in new:
        if key == "version":
            continue
        if key not in old:
            comment = get_key_comment(new, key)
            logs.append(f"新增: {'.'.join(path + [str(key)])}  注释: {comment or '无'}")
        elif isinstance(new[key], (dict, Table)) and isinstance(old.get(key), (dict, Table)):
            compare_dicts(new[key], old[key], path + [str(key)], logs)
    # 删减项
    for key in old:
        if key == "version":
            continue
        if key not in new:
            comment = get_key_comment(old, key)
            logs.append(f"删减: {'.'.join(path + [str(key)])}  注释: {comment or '无'}")
    return logs


def get_value_by_path(d, path):
    for k in path:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return None
    return d


def set_value_by_path(d, path, value):
    """设置嵌套字典中指定路径的值"""
    for k in path[:-1]:
        if k not in d or not isinstance(d[k], dict):
            d[k] = {}
        d = d[k]

    # 使用 tomlkit.item 来保持 TOML 格式
    try:
        d[path[-1]] = tomlkit.item(value)
    except (TypeError, ValueError):
        # 如果转换失败，直接赋值
        d[path[-1]] = value


def compare_default_values(new, old, path=None, logs=None, changes=None):
    # 递归比较两个dict，找出默认值变化项
    if path is None:
        path = []
    if logs is None:
        logs = []
    if changes is None:
        changes = []
    for key in new:
        if key == "version":
            continue
        if key in old:
            if isinstance(new[key], (dict, Table)) and isinstance(old[key], (dict, Table)):
                compare_default_values(new[key], old[key], path + [str(key)], logs, changes)
            elif new[key] != old[key]:
                logs.append(f"默认值变化: {'.'.join(path + [str(key)])}  旧默认值: {old[key]}  新默认值: {new[key]}")
                changes.append((path + [str(key)], old[key], new[key]))
    return logs, changes


def _get_version_from_toml(toml_path) -> Optional[str]:
    """从TOML文件中获取版本号"""
    if not os.path.exists(toml_path):
        return None
    with open(toml_path, "r", encoding="utf-8") as f:
        doc = tomlkit.load(f)
    if "inner" in doc and "version" in doc["inner"]:  # type: ignore
        return doc["inner"]["version"]  # type: ignore
    return None


def _version_tuple(v):
    """将版本字符串转换为元组以便比较"""
    if v is None:
        return (0,)
    return tuple(int(x) if x.isdigit() else 0 for x in str(v).replace("v", "").split("-")[0].split("."))


def _update_dict(target: TOMLDocument | dict | Table, source: TOMLDocument | dict):
    """
    将source字典的值更新到target字典中（如果target中存在相同的键）
    """
    for key, value in source.items():
        # 跳过version字段的更新
        if key == "version":
            continue
        if key in target:
            target_value = target[key]
            if isinstance(value, dict) and isinstance(target_value, (dict, Table)):
                _update_dict(target_value, value)
            else:
                try:
                    # 统一使用 tomlkit.item 来保持原生类型与转义，不对列表做字符串化处理
                    target[key] = tomlkit.item(value)
                except (TypeError, ValueError):
                    # 如果转换失败，直接赋值
                    target[key] = value


def _update_config_generic(config_name: str, template_name: str):
    """
    通用的配置文件更新函数

    Args:
        config_name: 配置文件名（不含扩展名），如 'bot_config' 或 'model_config'
        template_name: 模板文件名（不含扩展名），如 'bot_config_template' 或 'model_config_template'
    """
    # 获取根目录路径
    old_config_dir = os.path.join(CONFIG_DIR, "old")
    compare_dir = os.path.join(TEMPLATE_DIR, "compare")

    # 定义文件路径
    template_path = os.path.join(TEMPLATE_DIR, f"{template_name}.toml")
    old_config_path = os.path.join(CONFIG_DIR, f"{config_name}.toml")
    new_config_path = os.path.join(CONFIG_DIR, f"{config_name}.toml")
    compare_path = os.path.join(compare_dir, f"{template_name}.toml")

    # 创建compare目录（如果不存在）
    os.makedirs(compare_dir, exist_ok=True)

    template_version = _get_version_from_toml(template_path)
    compare_version = _get_version_from_toml(compare_path)

    # 检查配置文件是否存在
    if not os.path.exists(old_config_path):
        logger.info(f"{config_name}.toml配置文件不存在，从模板创建新配置")
        os.makedirs(CONFIG_DIR, exist_ok=True)  # 创建文件夹
        shutil.copy2(template_path, old_config_path)  # 复制模板文件
        logger.info(f"已创建新{config_name}配置文件，请填写后重新运行: {old_config_path}")
        # 新创建配置文件，退出
        sys.exit(0)

    compare_config = None
    new_config = None
    old_config = None

    # 先读取 compare 下的模板（如果有），用于默认值变动检测
    if os.path.exists(compare_path):
        with open(compare_path, "r", encoding="utf-8") as f:
            compare_config = tomlkit.load(f)

    # 读取当前模板
    with open(template_path, "r", encoding="utf-8") as f:
        new_config = tomlkit.load(f)

    # 检查默认值变化并处理（只有 compare_config 存在时才做）
    if compare_config:
        # 读取旧配置
        with open(old_config_path, "r", encoding="utf-8") as f:
            old_config = tomlkit.load(f)
        logs, changes = compare_default_values(new_config, compare_config)
        if logs:
            logger.info(f"检测到{config_name}模板默认值变动如下：")
            for log in logs:
                logger.info(log)
            # 检查旧配置是否等于旧默认值，如果是则更新为新默认值
            config_updated = False
            for path, old_default, new_default in changes:
                old_value = get_value_by_path(old_config, path)
                if old_value == old_default:
                    set_value_by_path(old_config, path, new_default)
                    logger.info(
                        f"已自动将{config_name}配置 {'.'.join(path)} 的值从旧默认值 {old_default} 更新为新默认值 {new_default}"
                    )
                    config_updated = True

            # 如果配置有更新，立即保存到文件
            if config_updated:
                with open(old_config_path, "w", encoding="utf-8") as f:
                    f.write(format_toml_string(old_config))
                logger.info(f"已保存更新后的{config_name}配置文件")
        else:
            logger.info(f"未检测到{config_name}模板默认值变动")

    # 检查 compare 下没有模板，或新模板版本更高，则复制
    if not os.path.exists(compare_path):
        shutil.copy2(template_path, compare_path)
        logger.info(f"已将{config_name}模板文件复制到: {compare_path}")
    elif _version_tuple(template_version) > _version_tuple(compare_version):
        shutil.copy2(template_path, compare_path)
        logger.info(f"{config_name}模板版本较新，已替换compare下的模板: {compare_path}")
    else:
        logger.debug(f"compare下的{config_name}模板版本不低于当前模板，无需替换: {compare_path}")

    # 读取旧配置文件和模板文件（如果前面没读过 old_config，这里再读一次）
    if old_config is None:
        with open(old_config_path, "r", encoding="utf-8") as f:
            old_config = tomlkit.load(f)
    # new_config 已经读取

    # 检查version是否相同
    if old_config and "inner" in old_config and "inner" in new_config:
        old_version = old_config["inner"].get("version")  # type: ignore
        new_version = new_config["inner"].get("version")  # type: ignore
        if old_version and new_version and old_version == new_version:
            logger.info(f"检测到{config_name}配置文件版本号相同 (v{old_version})，跳过更新")
            return
        else:
            logger.info(
                f"\n----------------------------------------\n检测到{config_name}版本号不同: 旧版本 v{old_version} -> 新版本 v{new_version}\n----------------------------------------"
            )
    else:
        logger.info(f"已有{config_name}配置文件未检测到版本号，可能是旧版本。将进行更新")

    # 创建old目录（如果不存在）
    os.makedirs(old_config_dir, exist_ok=True)  # 生成带时间戳的新文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    old_backup_path = os.path.join(old_config_dir, f"{config_name}_{timestamp}.toml")

    # 移动旧配置文件到old目录
    shutil.move(old_config_path, old_backup_path)
    logger.info(f"已备份旧{config_name}配置文件到: {old_backup_path}")

    # 复制模板文件到配置目录
    shutil.copy2(template_path, new_config_path)
    logger.info(f"已创建新{config_name}配置文件: {new_config_path}")

    # 输出新增和删减项及注释
    if old_config:
        logger.info(f"{config_name}配置项变动如下：\n----------------------------------------")
        if logs := compare_dicts(new_config, old_config):
            for log in logs:
                logger.info(log)
        else:
            logger.info("无新增或删减项")

    # 将旧配置的值更新到新配置中
    logger.info(f"开始合并{config_name}新旧配置...")
    _update_dict(new_config, old_config)

    # 保存更新后的配置（保留注释和格式，数组多行格式化）
    with open(new_config_path, "w", encoding="utf-8") as f:
        f.write(format_toml_string(new_config))
    logger.info(f"{config_name}配置文件更新完成，建议检查新配置文件中的内容，以免丢失重要信息")


def update_config():
    """更新bot_config.toml配置文件"""
    _update_config_generic("bot_config", "bot_config_template")


def update_model_config():
    """更新model_config.toml配置文件"""
    _update_config_generic("model_config", "model_config_template")


@dataclass
class InnerConfig(ConfigBase):
    """内部配置类 - 用于版本管理和实验性功能"""

    version: str = field(default="0.0.0")
    """配置文件版本号"""

    use_v2_architecture: bool = True
    """是否使用 chat_v2 UnifiedAgent；false 为心流 HeartF/Brain。配置未写此项时默认为 true。"""

    v2_enable_legacy_planner_no_reply_gate: bool = True
    """v2 下：先跑旧 ActionPlanner/BrainPlanner（[model_task_config.planner] 模型）判是否发言；若全部为沉默类动作且非 @/提及，则跳过 v2 主 LLM。设为 false 可省一次 planner 调用。"""

    v2_use_native_planner_gate: bool = False
    """v2 下：用专用门闸规划替代旧 plan() 调用——沿用群/私聊 planner 模板与 reply/no_reply 规则，但不向模型注入插件类 Action（由主模型与工具处理），减轻与 UnifiedAgent 的重复决策。须仍开启门闸/摘要之一才会执行；与 v2_execute_legacy_planner_side_actions 同时开启时自动回退旧 planner。"""

    v2_run_legacy_planner_on_mention: bool = False
    """v2 下在已开启门闸/插件/摘要之一时：@ 或昵称提及仍跑一轮旧 planner（群聊用 planner_prompt_mentioned）；提及时不会触发沉默门闸短路。默认关以省一次 planner LLM。"""

    v2_execute_legacy_planner_wait_time: bool = False
    """v2 下旧 planner 返回 wait_time 时，在进主 LLM 前通过 ActionManager 执行（与心流一致）。需已开启门闸/插件/摘要之一以触发 planner。"""

    v2_apply_legacy_planner_smooth_sleep: bool = False
    """v2 下旧 planner.plan 返回后，按 chat.planner_smooth 补足睡眠（与心流规划后平滑间隔一致）。需已触发 planner。"""

    v2_append_legacy_plan_style_to_system_prompt: bool = True
    """v2 下在 UnifiedAgent 系统提示末尾附加与旧 planner 相同的 plan_style / private_plan_style（默认开，无额外 LLM；可在 bot 配置中设为 false 关闭）"""

    v2_execute_legacy_planner_side_actions: bool = False
    """v2 下可选：legacy planner 之后执行插件类 action；可与门闸同时或单独开启，单独开启也会多一次 planner LLM"""

    v2_run_legacy_observe_side_tasks: bool = False
    """v2 下可选：每条入站消息后触发旧 observe 中的轻量化后台任务（表达学习、黑话挖掘），与是否回复无关（默认关）"""

    v2_inject_legacy_planner_summary_into_prompt: bool = False
    """v2 下可选：会触发一轮旧 Planner；未短路时把动作与理由（单条理由截断）注入 v2 提示（决策与工具后回复）（默认关）"""

    v2_use_legacy_prompt_message_scope: bool = False
    """v2 下可选：决策与工具后回复 LLM 调用包在 global_prompt_manager.async_message_scope 内，与旧链路模板作用域一致（默认关）"""

    v2_run_legacy_reflect_side_tasks: bool = False
    """v2 下可选：后台异步执行反思检测与 ReflectTracker（与旧 observe 前段类似，不阻塞主链路）（默认关）"""

    v2_use_replyer_aligned_persona: bool = True
    """v2 下是否按旧 replyer 注入完整人设（身份含状态/别名/能力、关键词反应、表达习惯、黑话、experimental chat_prompt 等）；关则仅用简短 personality 文本"""

    v2_log_full_unified_prompt: bool = True
    """v2 UnifiedAgent：在日志（INFO）分块打印决策轮与工具后回复的完整提示词；也可设 [debug] show_prompt = true；或环境变量 MAI_LOG_FULL_V2_PROMPT=1。关则 inner 下设为 false。"""

    v2_anti_repeat_inject_recent_own_speech: bool = True
    """v2：在决策与终局提示词中注入「你近期已发送过的原文」列表，便于模型逐条对照、减少复述。"""

    v2_anti_repeat_recent_own_max_items: int = 15
    """v2：注入的本人近期发言条数上限（从新到旧）。"""

    v2_anti_repeat_recent_own_max_chars_per_line: int = 500
    """v2：注入时每条本人发言的最大字符数，超出截断。"""

    v2_anti_repeat_llm_rewrite: bool = True
    """v2：在发出前若草稿与近期本人发言高度雷同，则追加一次专用 LLM 改写（多一次调用，偏效果）。"""

    v2_anti_repeat_similarity_threshold: float = 0.86
    """v2：归一化后全文/分段与历史本人发言的 SequenceMatcher 相似度达到该值即视为复读，触发改写。"""

    v2_tool_execution_timeout_seconds: float = 120.0
    """v2 UnifiedAgent 下单个工具的最大等待时间（秒，asyncio.wait_for）。TTS、外网搜索等较慢时可改为 180～300。"""

    v2_inbound_message_dedup_ttl_seconds: float = 180.0
    """chat_v2 入站：同一 platform+会话+message_id 在成功处理后多少秒内视为已处理，用于防 NapCat 重复投递导致两轮回复。设为 0 关闭去重。"""

    v2_serial_process_per_stream: bool = True
    """chat_v2：同一 stream_id（群/私聊会话）内串行执行 process，避免多条入站并发交错导致连发多段回复。设为 false 可恢复并行（吞吐更高、易重复）。"""

    v2_skip_text_when_only_unified_tts_success: bool = True
    """chat_v2：若本轮工具全部成功且仅有 unified_tts（语音已发出），则不再发送终局文字与表情包，避免「语音 + 又长一句说明」重复。"""


@dataclass
class Config(ConfigBase):
    """总配置类 - 支持多机器人模式"""

    MMC_VERSION: str = field(default=MMC_VERSION, repr=False, init=False)  # 硬编码的版本信息

    # 内部配置
    inner: InnerConfig = field(default_factory=InnerConfig)
    """内部配置（版本管理和实验性功能）"""

    # 多机器人模式配置
    bots: List[BotInstanceConfig] = field(default_factory=list)
    """机器人实例列表（多机器人模式）"""

    enable_multi_bot: bool = False
    """是否启用多机器人模式"""

    # 向后兼容：单机器人模式配置（如果 bots 为空，则使用这些配置）
    bot: Optional[BotConfig] = field(default=None)
    personality: Optional[PersonalityConfig] = field(default=None)
    relationship: Optional[RelationshipConfig] = field(default=None)
    chat: Optional[ChatConfig] = field(default=None)
    emoji: Optional[EmojiConfig] = field(default=None)
    expression: Optional[ExpressionConfig] = field(default=None)
    keyword_reaction: Optional[KeywordReactionConfig] = field(default=None)
    proactive_chat: Optional[ProactiveChatConfig] = field(default=None)
    reminder: Optional[ReminderConfig] = field(default=None)
    repeat: Optional[RepeatConfig] = field(default=None)

    # 共享配置（所有机器人共用）
    message_receive: MessageReceiveConfig = field(default_factory=MessageReceiveConfig)
    chinese_typo: ChineseTypoConfig = field(default_factory=ChineseTypoConfig)
    response_post_process: ResponsePostProcessConfig = field(default_factory=ResponsePostProcessConfig)
    response_splitter: ResponseSplitterConfig = field(default_factory=ResponseSplitterConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    experimental: ExperimentalConfig = field(default_factory=ExperimentalConfig)
    maim_message: MaimMessageConfig = field(default_factory=MaimMessageConfig)
    lpmm_knowledge: LPMMKnowledgeConfig = field(default_factory=LPMMKnowledgeConfig)
    tool: ToolConfig = field(default_factory=ToolConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    mood: MoodConfig = field(default_factory=MoodConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    jargon: JargonConfig = field(default_factory=JargonConfig)

    def __post_init__(self):
        """初始化后处理：向后兼容和多机器人模式转换"""
        # 如果没有配置 bots 列表，但配置了单机器人字段，则自动转换为多机器人模式
        if not self.bots and self.bot is not None:
            logger.info("检测到单机器人配置，自动转换为多机器人模式")
            # 创建默认的机器人实例
            default_bot = BotInstanceConfig(
                bot_id="maimai_main",
                enabled=True,
                bot=self.bot,
                personality=self.personality or PersonalityConfig(personality="", reply_style=""),
                relationship=self.relationship or RelationshipConfig(),
                chat=self.chat or ChatConfig(),
                emoji=self.emoji or EmojiConfig(enable=True),
                expression=self.expression or ExpressionConfig(),
                keyword_reaction=self.keyword_reaction or KeywordReactionConfig(),
                proactive_chat=self.proactive_chat or ProactiveChatConfig(),
                reminder=self.reminder or ReminderConfig(),
                repeat=self.repeat or RepeatConfig(),
            )
            self.bots = [default_bot]
            self.enable_multi_bot = False  # 标记为兼容模式
        elif self.bots:
            self.enable_multi_bot = True
            logger.info(f"多机器人模式已启用，共 {len(self.bots)} 个机器人实例")
        else:
            raise ValueError("配置文件错误：既没有配置 bots 列表，也没有配置单机器人字段")

        # 验证机器人配置
        if self.bots:
            bot_ids = [bot.bot_id for bot in self.bots]
            if len(bot_ids) != len(set(bot_ids)):
                raise ValueError("机器人 bot_id 存在重复，请检查配置文件")

            qq_accounts = [bot.bot.qq_account for bot in self.bots if bot.enabled]
            if len(qq_accounts) != len(set(qq_accounts)):
                raise ValueError("机器人 QQ 账号存在重复，请检查配置文件")

    def get_bot_config(self, bot_id: str) -> Optional[BotInstanceConfig]:
        """根据 bot_id 获取机器人配置"""
        for bot in self.bots:
            if bot.bot_id == bot_id:
                return bot
        return None

    def get_bot_by_qq(self, qq_account: str) -> Optional[BotInstanceConfig]:
        """根据 QQ 账号获取机器人配置"""
        for bot in self.bots:
            if bot.bot.qq_account == qq_account and bot.enabled:
                return bot
        return None

    def get_enabled_bots(self) -> List[BotInstanceConfig]:
        """获取所有启用的机器人"""
        return [bot for bot in self.bots if bot.enabled]


@dataclass
class APIAdapterConfig(ConfigBase):
    """API Adapter配置类"""

    models: List[ModelInfo]
    """模型列表"""

    model_task_config: ModelTaskConfig
    """模型任务配置"""

    api_providers: List[APIProvider] = field(default_factory=list)
    """API提供商列表"""

    def __post_init__(self):
        if not self.models:
            raise ValueError("模型列表不能为空，请在配置中设置有效的模型列表。")
        if not self.api_providers:
            raise ValueError("API提供商列表不能为空，请在配置中设置有效的API提供商列表。")

        # 检查API提供商名称是否重复
        provider_names = [provider.name for provider in self.api_providers]
        if len(provider_names) != len(set(provider_names)):
            raise ValueError("API提供商名称存在重复，请检查配置文件。")

        # 检查模型名称是否重复
        model_names = [model.name for model in self.models]
        if len(model_names) != len(set(model_names)):
            raise ValueError("模型名称存在重复，请检查配置文件。")

        self.api_providers_dict = {provider.name: provider for provider in self.api_providers}
        self.models_dict = {model.name: model for model in self.models}

        for model in self.models:
            if not model.model_identifier:
                raise ValueError(f"模型 '{model.name}' 的 model_identifier 不能为空")
            if not model.api_provider or model.api_provider not in self.api_providers_dict:
                raise ValueError(f"模型 '{model.name}' 的 api_provider '{model.api_provider}' 不存在")

    def get_model_info(self, model_name: str) -> ModelInfo:
        """根据模型名称获取模型信息"""
        if not model_name:
            raise ValueError("模型名称不能为空")
        if model_name not in self.models_dict:
            raise KeyError(f"模型 '{model_name}' 不存在")
        return self.models_dict[model_name]

    def get_provider(self, provider_name: str) -> APIProvider:
        """根据提供商名称获取API提供商信息"""
        if not provider_name:
            raise ValueError("API提供商名称不能为空")
        if provider_name not in self.api_providers_dict:
            raise KeyError(f"API提供商 '{provider_name}' 不存在")
        return self.api_providers_dict[provider_name]


def load_config(config_path: str) -> Config:
    """
    加载配置文件
    Args:
        config_path: 配置文件路径
    Returns:
        Config对象
    """
    # 读取配置文件
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = tomlkit.load(f)

    # 创建Config对象
    try:
        return Config.from_dict(config_data)
    except Exception as e:
        logger.critical("配置文件解析失败")
        raise e


def api_ada_load_config(config_path: str) -> APIAdapterConfig:
    """
    加载API适配器配置文件
    Args:
        config_path: 配置文件路径
    Returns:
        APIAdapterConfig对象
    """
    # 读取配置文件
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = tomlkit.load(f)

    # 创建APIAdapterConfig对象
    try:
        return APIAdapterConfig.from_dict(config_data)
    except Exception as e:
        logger.critical("API适配器配置文件解析失败")
        raise e


# 获取配置文件路径
logger.info(f"MaiCore当前版本: {MMC_VERSION}")
# 禁用自动更新配置文件功能
# update_config()
# update_model_config()

logger.info("正在品鉴配置文件...")

# 支持通过环境变量指定配置文件
bot_config_file = os.environ.get('BOT_CONFIG', 'bot_config.toml')
if not bot_config_file.startswith('config/'):
    bot_config_path = os.path.join(CONFIG_DIR, bot_config_file)
else:
    # 如果已经包含 config/ 前缀，直接使用
    bot_config_path = bot_config_file

logger.info(f"加载机器人配置: {bot_config_path}")
global_config = load_config(config_path=bot_config_path)
RESOLVED_BOT_CONFIG_PATH = os.path.abspath(bot_config_path)
if os.environ.get("MAI_FORCE_V2", "").strip().lower() in ("1", "true", "yes", "on"):
    global_config.inner.use_v2_architecture = True
    logger.info(
        "已根据环境变量 MAI_FORCE_V2 强制启用 chat_v2（覆盖 bot_config 中的 use_v2_architecture）"
    )
_v2_on = getattr(global_config.inner, "use_v2_architecture", None)
logger.info(
    f"架构开关 inner.use_v2_architecture={_v2_on} "
    f"（True=chat_v2 UnifiedAgent，False=HeartF/Brain）；配置文件: {RESOLVED_BOT_CONFIG_PATH}"
)
model_config = api_ada_load_config(config_path=os.path.join(CONFIG_DIR, "model_config.toml"))
logger.info("非常的新鲜，非常的美味！")
