import os
from dataclasses import dataclass, field

from .config_base import ConfigBase


@dataclass
class APIProvider(ConfigBase):
    """API提供商配置类"""

    name: str
    """API提供商名称"""

    base_url: str
    """API基础URL"""

    api_key: str = field(default_factory=str, repr=False)
    """API密钥列表"""

    client_type: str = field(default="openai")
    """客户端类型（如openai/google等，默认为openai）"""

    max_retry: int = 2
    """最大重试次数（单个模型API调用失败，最多重试的次数）"""

    timeout: int = 10
    """API调用的超时时长（超过这个时长，本次请求将被视为“请求超时”，单位：秒）"""

    retry_interval: int = 10
    """重试间隔（如果API调用失败，重试的间隔时间，单位：秒）"""

    def get_api_key(self) -> str:
        return self.api_key

    def __post_init__(self):
        """
        初始化后处理方法

        功能说明：
        1. 确保 api_key 在 repr 中不被显示（通过 field(repr=False) 实现）
        2. 支持从环境变量读取 API key，提高安全性
        3. 验证配置项的有效性

        环境变量支持格式：
        - ${ENV_VAR_NAME}  推荐格式，兼容 shell 语法
        - env:ENV_VAR_NAME 备选格式，更明确的语义

        示例：
        配置文件中: api_key = "${SILICONFLOW_API_KEY}"
        .env 文件中: SILICONFLOW_API_KEY=sk-xxx
        """
        # ===== 环境变量解析 =====
        # 支持从环境变量读取 API key，避免在配置文件中硬编码敏感信息
        if self.api_key:
            # 处理 ${ENV_VAR_NAME} 格式（推荐）
            # 例如: "${SILICONFLOW_API_KEY}" -> 提取 "SILICONFLOW_API_KEY" -> 读取环境变量
            if self.api_key.startswith("${") and self.api_key.endswith("}"):
                env_var_name = self.api_key[2:-1]  # 去掉前缀 "${" 和后缀 "}"
                self.api_key = os.getenv(env_var_name, "")  # 从环境变量读取，未设置则为空字符串

            # 处理 env:ENV_VAR_NAME 格式（备选）
            # 例如: "env:SILICONFLOW_API_KEY" -> 提取 "SILICONFLOW_API_KEY" -> 读取环境变量
            elif self.api_key.startswith("env:"):
                env_var_name = self.api_key[4:]  # 去掉前缀 "env:"
                self.api_key = os.getenv(env_var_name, "")  # 从环境变量读取，未设置则为空字符串

        # ===== 配置验证 =====
        # 验证 API 密钥不能为空
        if not self.api_key:
            raise ValueError(
                f"API密钥不能为空，请在配置或环境变量中设置 '{self.name}' 的有效API密钥。\n"
                f"提示：请检查 .env 文件或系统环境变量中是否正确设置了相应的 API Key。"
            )

        # 验证 base_url（Gemini 除外，因为其使用特殊的 API 格式）
        if not self.base_url and self.client_type != "gemini":
            raise ValueError("API基础URL不能为空，请在配置中设置有效的基础URL。")

        # 验证提供商名称
        if not self.name:
            raise ValueError("API提供商名称不能为空，请在配置中设置有效的名称。")


@dataclass
class ModelInfo(ConfigBase):
    """单个模型信息配置类"""

    model_identifier: str
    """模型标识符（用于URL调用）"""

    name: str
    """模型名称（用于模块调用）"""

    api_provider: str
    """API提供商（如OpenAI、Azure等）"""

    price_in: float = field(default=0.0)
    """每M token输入价格"""

    price_out: float = field(default=0.0)
    """每M token输出价格"""

    force_stream_mode: bool = field(default=False)
    """是否强制使用流式输出模式"""

    extra_params: dict = field(default_factory=dict)
    """额外参数（用于API调用时的额外配置）"""

    def __post_init__(self):
        if not self.model_identifier:
            raise ValueError("模型标识符不能为空，请在配置中设置有效的模型标识符。")
        if not self.name:
            raise ValueError("模型名称不能为空，请在配置中设置有效的模型名称。")
        if not self.api_provider:
            raise ValueError("API提供商不能为空，请在配置中设置有效的API提供商。")


@dataclass
class TaskConfig(ConfigBase):
    """任务配置类"""

    model_list: list[str] = field(default_factory=list)
    """任务使用的模型列表"""

    max_tokens: int = 8192
    """任务最大输出token数（配置缺省时默认；以 model_config.toml 为准）"""

    temperature: float = 0.3
    """模型温度"""

    slow_threshold: float = 15.0
    """慢请求阈值（秒），超过此值会输出警告日志"""


def _default_jrys_fortune_task() -> TaskConfig:
    """今日运势等轻量占卜文案；未在 model_config.toml 中写 [model_task_config.jrys_fortune] 时使用。"""
    return TaskConfig(
        model_list=["siliconflow-deepseek-v3.2"],
        temperature=0.85,
        max_tokens=512,
        slow_threshold=25.0,
    )


@dataclass
class ModelTaskConfig(ConfigBase):
    """模型配置类"""

    utils: TaskConfig
    """组件模型配置"""

    utils_small: TaskConfig
    """组件小模型配置"""

    replyer: TaskConfig
    """normal_chat首要回复模型模型配置"""

    vlm: TaskConfig
    """视觉语言模型配置"""

    voice: TaskConfig
    """语音识别模型配置"""

    tool_use: TaskConfig
    """专注工具使用模型配置"""

    planner: TaskConfig
    """规划模型配置"""

    embedding: TaskConfig
    """嵌入模型配置"""

    lpmm_entity_extract: TaskConfig
    """LPMM实体提取模型配置"""

    lpmm_rdf_build: TaskConfig
    """LPMM RDF构建模型配置"""

    lpmm_qa: TaskConfig
    """LPMM问答模型配置"""

    jrys_fortune: TaskConfig = field(default_factory=_default_jrys_fortune_task)
    """今日运势占卜文案（建议 DeepSeek）；独立任务配置，与 replyer/utils 分流计费与模型选择"""

    def get_task(self, task_name: str) -> TaskConfig:
        """获取指定任务的配置"""
        if hasattr(self, task_name):
            return getattr(self, task_name)
        raise ValueError(f"任务 '{task_name}' 未找到对应的配置")
