<div align="center">

<img src="MaiBot/depends-data/maimai.png" alt="MaiBot" title="作者:略nd" width="300">

# 🌟 MaiBot Fork - 增强版

[![Python Version](https://img.shields.io/badge/Python-3.10+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-green)](LICENSE)
[![Fork](https://img.shields.io/badge/Fork-Enhanced-orange)](https://github.com/MaiM-with-u/MaiBot)
[![Status](https://img.shields.io/badge/Status-Active-success)](https://github.com/wenjinqing/MaiBot_wenfork)

**基于 [MaiBot](https://github.com/MaiM-with-u/MaiBot) 的增强版本**

[🚀 快速开始](#-快速开始) • [✨ 改进特性](#-改进特性) • [📖 使用文档](#-使用文档) • [💡 使用示例](#-使用示例) • [❓ FAQ](#-常见问题faq) • [🤝 贡献](#-贡献)

</div>

---

## 🎬 演示视频

<div align="center">
<a href="https://www.bilibili.com/video/BV1amAneGE3P" target="_blank">
  <img src="MaiBot/depends-data/video.png" width="60%" alt="麦麦演示视频">
  <br>
  <b>👆 点击观看麦麦演示视频 👆</b>
</a>
</div>

---

## 📋 项目简介

这是 [MaiBot](https://github.com/MaiM-with-u/MaiBot) 的 Fork 版本，在原项目基础上进行了**安全性**和**可维护性**的全面改进。

**MaiBot** 是一个基于大语言模型的可交互智能体，旨在创造一个活跃在 QQ 群聊的"生命体"。

### 🎯 核心特性

- 💭 **拟人化对话** - 使用自然语言风格构建 prompt，实现近似人类的对话习惯
- 🧠 **表达学习** - 学习群友的说话风格和表达方式
- 🤔 **黑话学习** - 自主学习新词语，尝试理解并认知含义
- 🎭 **情感表达** - 完整的情绪系统和表情包系统
- 🔌 **插件系统** - 提供 API 和事件系统，可编写丰富插件
- 📊 **行为规划** - 在合适的时间说话，使用合适的动作

---

## ✨ 改进特性

相比原项目，本 Fork 版本进行了以下改进：

### 🔒 安全性增强

#### API Keys 环境变量化
- **双格式支持**
  - `${ENV_VAR_NAME}` - Shell 风格，推荐使用
  - `env:ENV_VAR_NAME` - 显式语义，备选方案
- **自动解析机制**
  - 在 `api_ada_configs.py` 的 `__post_init__` 方法中实现
  - 启动时自动从环境变量读取 API Keys
  - 配置验证：API Key 为空时抛出友好错误提示
- **完善的安全配置**
  - `.gitignore` 忽略 `.env` 文件（第 41 行）
  - `.env` 文件包含所有敏感配置
  - 提供 `template/template.env` 模板文件
- **多层防护**
  - 配置文件中使用环境变量引用，不直接存储密钥
  - `api_key` 字段设置 `repr=False`，日志中不显示
  - 详细的安全使用建议和最佳实践

#### 配置验证增强
- **API 提供商验证**
  - 验证 API Key 非空（第 69-73 行）
  - 验证 base_url 有效性（第 76-77 行）
  - 验证提供商名称（第 80-81 行）
- **友好错误提示**
  - 提供具体的错误原因和解决方案
  - 指导用户检查 `.env` 文件配置

### 📝 代码质量提升

#### 详细中文注释
- **核心配置文件** (`src/config/api_ada_configs.py`)
  - 类和方法的完整文档字符串
  - 环境变量解析逻辑的逐行注释（第 52-65 行）
  - 配置验证逻辑的详细说明（第 67-81 行）
  - 代码示例和使用场景说明
- **环境变量配置** (`.env`)
  - 87 行详细注释，包含：
    - 每个配置项的用途说明
    - API 提供商的官网和获取地址
    - 定价信息和使用建议
    - 安全使用提示
- **配置文件** (`config/model_config.toml`)
  - 环境变量引用格式说明
  - 配置项的详细注释
  - 使用示例和最佳实践

#### 代码结构优化
- **环境变量解析逻辑**
  - 使用 `__post_init__` 钩子实现自动解析
  - 支持两种格式的统一处理
  - 清晰的代码分段和注释
- **错误处理改进**
  - 使用 `ValueError` 抛出配置错误
  - 提供详细的错误信息和解决建议

### 🗂️ 项目结构优化

#### 文件清理
- **移除错误文件**
  - 删除 `=0.23.0`, `=3.12.0`, `=4.1.0`, `=7.4.0` 等错误依赖文件
  - 这些文件可能是依赖安装错误产生的
- **文档整理**
  - 将报告文件移至 `docs/reports/` 目录
  - 统一文档存放位置
- **代码规范**
  - 清理 `start.bat` 末尾多余空行
  - 统一文件格式和编码

#### 目录结构
```
MaiBot/
├── src/config/          # 配置模块（已优化）
│   └── api_ada_configs.py  # 支持环境变量的 API 配置
├── config/              # 配置文件（已优化）
│   └── model_config.toml   # 使用环境变量引用
├── template/            # 配置模板（新增）
│   └── template.env        # 详细的环境变量模板
├── .env                 # 环境变量（不提交）
└── .gitignore          # 忽略配置（已完善）
```

### 📚 文档完善

#### 环境变量配置模板
**文件**: `template/template.env` (90+ 行)

包含内容：
- **配置说明**
  - 使用步骤（复制、重命名、填写）
  - 文件安全提示
- **主程序配置**
  - HOST 和 PORT 设置
  - WebUI 服务器配置
- **API Keys 配置**
  - DeepSeek API（推荐，性价比高）
  - 阿里百炼 API
  - Google AI (Gemini) API
  - SiliconFlow API
- **每个 API 提供商包含**
  - 服务商简介
  - 官网地址
  - API Key 获取地址
  - 定价信息
  - 使用说明
- **安全建议**
  - API Keys 轮换建议
  - 泄露应对措施
  - 生产环境最佳实践

#### 配置文件模板
- `template/model_config_template.toml` - 模型配置模板
- `template/compare/model_config_template.toml` - 对比配置模板
- 所有模板文件都已更新为使用环境变量引用

---

## 🚀 快速开始

### 📦 环境要求

- Python 3.10+
- Windows / Linux / macOS
- Git

### 🔧 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/wenjinqing/MaiBot_wenfork.git
cd MaiBot_wenfork/MaiBot
```

2. **创建虚拟环境**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

3. **安装依赖**

```bash
pip install -r requirements.txt
```

4. **配置环境变量**

```bash
# 复制模板文件
cp template/template.env .env

# 编辑 .env 文件，填入你的 API Keys
# 支持的 API 提供商：
# - DeepSeek (推荐，性价比高)
# - 阿里百炼 (BaiLian)
# - Google AI (Gemini)
# - SiliconFlow (开源模型)
```

5. **配置模型**

编辑 `config/model_config.toml`，选择你要使用的模型和 API 提供商。

6. **启动 MaiBot**

```bash
# Windows
start.bat

# Linux/macOS
python bot.py
```

---

## 📖 使用文档

### 🔑 API Keys 配置

本 Fork 版本支持通过环境变量配置 API Keys，提高安全性：

**方式一：使用 .env 文件（推荐）**

```bash
# .env 文件
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx
GOOGLE_API_KEY=AIzaSyxxxxxxxxxx
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxx
```

**方式二：在配置文件中引用环境变量**

```toml
# config/model_config.toml
[[api_providers]]
name = "DeepSeek"
api_key = "${DEEPSEEK_API_KEY}"  # 推荐格式
# 或
api_key = "env:DEEPSEEK_API_KEY"  # 备选格式
```

### 🎨 支持的 API 提供商

| 提供商 | 模型 | 定价 | 获取地址 |
|--------|------|------|----------|
| **DeepSeek** | deepseek-chat | 输入 2元/M, 输出 8元/M | [platform.deepseek.com](https://platform.deepseek.com/) |
| **阿里百炼** | qwen-turbo/plus/max | 按量计费 | [dashscope.aliyuncs.com](https://dashscope.aliyuncs.com/) |
| **Google AI** | gemini-pro/flash | 免费额度 | [makersuite.google.com](https://makersuite.google.com/app/apikey) |
| **SiliconFlow** | 多种开源模型 | 按量计费 | [cloud.siliconflow.cn](https://cloud.siliconflow.cn/) |

### 📂 项目结构

```
MaiBot_wenfork/
├── MaiBot/                      # 主程序目录
│   ├── bot.py                   # 启动入口
│   ├── src/                     # 源代码
│   │   ├── config/              # 配置模块
│   │   │   └── api_ada_configs.py  # API 配置（支持环境变量）
│   │   ├── core/                # 核心功能
│   │   └── plugins/             # 插件系统
│   │       └── built_in/        # 内置插件
│   │           ├── plugin_management/  # 插件管理
│   │           ├── knowledge/          # 知识库集成
│   │           ├── emoji_plugin/       # 表情动作
│   │           ├── tts_plugin/         # 文字转语音
│   │           └── capabilities/       # 功能查询
│   ├── config/                  # 配置文件
│   │   └── model_config.toml    # 模型配置
│   ├── template/                # 配置模板
│   │   └── template.env         # 环境变量模板
│   ├── .env                     # 环境变量（不提交到 Git）
│   └── start.bat                # Windows 启动脚本
├── MaiBot-Napcat-Adapter/       # NapCat 协议适配器
├── library/                     # 知识库文件
└── mod/                         # 外部插件模块
    ├── google_search_plugin/    # 网络搜索
    ├── Maibot_topic_finder_plugin/  # 话题生成
    ├── MaiBot-DetailedExplanation-Plugin/  # 详细解释
    ├── lolicon-setu-plugin/     # 图片获取
    ├── acpoke_plugin/           # 戳一戳功能
    ├── tts_voice_plugin/        # TTS语音合成
    ├── Maizone/                 # QQ空间互动
    ├── music_plugin/            # 娱乐功能
    └── wife_plugin/             # 群老婆抽取
```

---

## 🔌 已安装插件

MaiBot 拥有丰富的插件生态，提供多样化的功能扩展。

### 内置插件 (5个)

#### 1. 🔧 插件管理 (Plugin Management)
**功能**: 插件和组件的动态管理系统

- 列出所有已注册和已加载的插件
- 动态加载/卸载/重新加载插件
- 管理插件目录
- 列出和管理组件（Action、Command、EventHandler）
- 全局和本地启用/禁用组件

**命令**: `/pm plugin list`, `/pm component list`

**状态**: 默认禁用（需要配置权限）

---

#### 2. 📚 知识库集成 (Knowledge)
**功能**: LPMM 知识库查询和集成

- 从知识库中搜索相关信息
- 提供知识库查询工具供 LLM 使用
- 支持自定义查询限制
- 增强 AI 回复的准确性和相关性

**工具**: `lpmm_search_knowledge`

**状态**: 根据全局配置决定

---

#### 3. 😊 表情动作 (Emoji Plugin)
**功能**: 核心表情和图片发送

- 发送表情符号
- 发送图片
- 基础聊天交互动作
- 增强表达能力

**组件**: EmojiAction

**状态**: 默认启用

---

#### 4. 🔊 文字转语音 (TTS Plugin)
**功能**: 文本转语音输出

- 将文本转换为语音
- 支持语音输出
- 文本预处理能力
- 提供更自然的交互方式

**动作**: TTSAction

**状态**: 默认启用

---

#### 5. 📋 功能查询 (Capabilities)
**功能**: 查询已启用的所有功能

- 查询已启用的插件、动作、命令、工具
- 支持按类型筛选查询
- 提供功能清单给用户
- 帮助用户了解可用功能

**工具**: `get_capabilities`

**状态**: 默认启用

---

### 外部插件 (9个)

#### 1. 🔍 网络搜索 (Google Search)
**功能**: 强大的网络搜索和内容抓取

**特性**:
- 支持多个搜索引擎
  - Google、Bing、搜狗
  - DuckDuckGo、Tavily、You
- 智能查询重写
- 网页内容抓取和总结
- 图片搜索功能
- 搜索结果缓存和历史记录

**工具**: WebSearchTool、AbbreviationTool

**动作**: ImageSearchAction

**状态**: 默认启用

---

#### 2. 💬 话题生成 (Topic Finder)
**功能**: 智能话题生成，保持群聊活跃

**特性**:
- RSS 订阅源管理
- 联网大模型信息获取
- 智能话题生成
- 定时发送话题
- 群聊静默检测和自动发起话题
- 支持群聊级别配置覆盖

**命令**: `/topic_test`, `/topic_config`, `/topic_debug`

**状态**: 默认启用

**适用场景**: 群聊冷场时自动活跃气氛

---

#### 3. 📖 详细解释 (Detailed Explanation)
**功能**: 生成长文本详细解释和科普

**特性**:
- 生成长文本详细解释
- 智能分段发送
- 支持联网搜索增强
- 多种分段算法
  - 智能分段
  - 按句子分段
  - 按长度分段
- 内容长度控制和二次扩写

**动作**: DetailedExplanationAction

**状态**: 默认启用

**适用场景**: 需要深入解释复杂概念时

---

#### 4. 🖼️ 图片获取 (Lolicon Setu)
**功能**: 基于 Lolicon API 的图片获取

**特性**:
- 支持标签搜索（AND/OR 组合）
- 关键词搜索
- 长宽比筛选
- AI 作品排除
- 用户冷却控制
- 合并转发格式发送

**命令**: `/setu`

**状态**: 默认启用

---

#### 5. 👉 戳一戳 (Poke Plugin)
**功能**: QQ 戳一戳互动功能

**特性**:
- 主动戳用户
- 被动戳回
- 支持群聊和私聊
- 用户 ID 智能查找
- 重复戳检测

**动作**: PokeAction

**状态**: 默认启用

**适用场景**: 增加互动趣味性

---

#### 6. 🎤 TTS 语音合成 (TTS Voice)
**功能**: 统一的 TTS 语音合成系统

**特性**:
- 支持三种后端
  - AI Voice
  - GSV2P
  - GPT-SoVITS
- 多种音色选择
- 文本清理和语言检测
- 支持中文、日文、英文

**动作**: UnifiedTTSAction

**状态**: 默认启用

---

#### 7. 🌐 QQ 空间互动 (Maizone)
**功能**: QQ 空间自动化互动

**特性**:
- 发送说说
- 阅读说说
- 点赞和评论
- 自动刷空间
- 定时发送说说
- Cookie 管理

**命令**: 发送说说、阅读说说等

**状态**: 默认启用

---

#### 8. 🎮 娱乐功能 (Entertainment)
**功能**: 多样化的娱乐功能集合

**特性**:
- 看看腿（随机图片）
- 看看美女（身体部位图片）
- 新闻功能
  - 60秒新闻
  - 历史上的今天
- 音乐功能
  - 播放音乐
  - 选择歌曲
- AI 绘图

**状态**: 默认启用

---

#### 9. 💑 群老婆抽取 (Wife Plugin)
**功能**: 趣味性的群老婆抽取功能

**特性**:
- 随机抽取群成员作为"群老婆"
- 每日限制（每人每天只能抽一次）
- 群成员列表获取
- 成员信息查询

**命令**: `抽老婆`

**状态**: 默认启用

**适用场景**: 增加群聊趣味性

---

### 插件系统特点

- ⚡ **动态加载**: 支持运行时加载/卸载插件
- 🧩 **组件系统**: 每个插件可包含多个组件（Action、Command、Tool、EventHandler）
- ⚙️ **配置管理**: 每个插件都有独立的 `config.toml` 配置文件
- 🔐 **权限控制**: 支持插件级别的权限管理
- 📦 **依赖管理**: 支持 Python 包依赖声明
- 🎯 **事件系统**: 支持事件驱动的插件交互

---

### 📂 项目结构（完整版）

```
MaiBot_wenfork/
├── MaiBot/                      # 主程序目录
│   ├── bot.py                   # 启动入口
│   ├── src/                     # 源代码
│   │   ├── config/              # 配置模块
│   │   │   └── api_ada_configs.py  # API 配置（支持环境变量）
│   │   ├── core/                # 核心功能
│   │   └── plugins/             # 插件系统
│   │       └── built_in/        # 内置插件
│   │           ├── plugin_management/  # 插件管理
│   │           ├── knowledge/          # 知识库集成
│   │           ├── emoji_plugin/       # 表情动作
│   │           ├── tts_plugin/         # 文字转语音
│   │           └── capabilities/       # 功能查询
│   ├── config/                  # 配置文件
│   │   └── model_config.toml    # 模型配置
│   ├── template/                # 配置模板
│   │   └── template.env         # 环境变量模板
│   ├── .env                     # 环境变量（不提交到 Git）
│   └── start.bat                # Windows 启动脚本
├── MaiBot-Napcat-Adapter/       # NapCat 协议适配器
├── library/                     # 知识库文件
└── mod/                         # 外部插件模块
    ├── google_search_plugin/    # 网络搜索
    ├── Maibot_topic_finder_plugin/  # 话题生成
    ├── MaiBot-DetailedExplanation-Plugin/  # 详细解释
    ├── lolicon-setu-plugin/     # 图片获取
    ├── acpoke_plugin/           # 戳一戳功能
    ├── tts_voice_plugin/        # TTS语音合成
    ├── Maizone/                 # QQ空间互动
    ├── music_plugin/            # 娱乐功能
    └── wife_plugin/             # 群老婆抽取
```

---

## 💡 使用示例

### 示例 1：配置 DeepSeek API（推荐）

DeepSeek 提供高性价比的 AI 服务，适合个人和小团队使用。

**步骤：**

1. 访问 [DeepSeek 平台](https://platform.deepseek.com/) 注册账号
2. 获取 API Key
3. 编辑 `.env` 文件：

```bash
DEEPSEEK_API_KEY=sk-your-actual-deepseek-key-here
```

4. 编辑 `config/model_config.toml`：

```toml
[[api_providers]]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
api_key = "${DEEPSEEK_API_KEY}"
client_type = "openai"

[[models]]
name = "deepseek-chat"
api_provider = "DeepSeek"
model_name = "deepseek-chat"
```

5. 启动 MaiBot，即可使用 DeepSeek 模型

### 示例 2：使用多个 API 提供商

你可以同时配置多个 API 提供商，实现负载均衡或备用方案。

```bash
# .env 文件
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx
GOOGLE_API_KEY=AIzaSyxxxxxxxxxx
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxx
```

```toml
# config/model_config.toml
[[api_providers]]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
api_key = "${DEEPSEEK_API_KEY}"
client_type = "openai"

[[api_providers]]
name = "Google"
base_url = "https://generativelanguage.googleapis.com/v1beta"
api_key = "${GOOGLE_API_KEY}"
client_type = "gemini"

[[api_providers]]
name = "SiliconFlow"
base_url = "https://api.siliconflow.cn/v1"
api_key = "${SILICONFLOW_API_KEY}"
client_type = "openai"
```

### 示例 3：配置 WebUI

MaiBot 提供 Web 管理界面，方便监控和管理。

```bash
# .env 文件
WEBUI_ENABLED=true
WEBUI_MODE=production
WEBUI_HOST=0.0.0.0  # 允许外部访问
WEBUI_PORT=8001
```

启动后访问：`http://localhost:8001`

### 示例 4：自定义插件开发

MaiBot 支持插件系统，你可以开发自己的功能插件。

```python
# mod/my_plugin/plugin.py
from src.plugins import Plugin

class MyPlugin(Plugin):
    """自定义插件示例"""

    def __init__(self):
        super().__init__()
        self.name = "我的插件"
        self.description = "这是一个示例插件"

    async def on_message(self, message):
        """处理消息事件"""
        if "你好" in message.text:
            return "你好！我是麦麦！"
        return None
```

---

## ❓ 常见问题（FAQ）

### 安装相关

<details>
<summary><b>Q: 安装依赖时出现错误怎么办？</b></summary>

**A:** 常见解决方案：

1. **升级 pip**：
   ```bash
   python -m pip install --upgrade pip
   ```

2. **使用国内镜像源**：
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

3. **检查 Python 版本**：
   ```bash
   python --version  # 确保是 3.10 或更高版本
   ```

4. **使用虚拟环境**：
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/macOS
   ```
</details>

<details>
<summary><b>Q: 虚拟环境激活失败？</b></summary>

**A:**

**Windows PowerShell 执行策略问题**：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**或者使用 CMD 而不是 PowerShell**：
```cmd
venv\Scripts\activate.bat
```
</details>

### 配置相关

<details>
<summary><b>Q: API Key 配置后仍然提示错误？</b></summary>

**A:** 检查以下几点：

1. **确认 .env 文件位置**：
   - `.env` 文件应该在 `MaiBot/` 目录下
   - 不是在 `template/` 目录下

2. **检查环境变量格式**：
   ```bash
   # 正确格式
   DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx

   # 错误格式（不要加引号）
   DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxx"  # ❌
   ```

3. **验证 API Key 有效性**：
   - 前往对应平台检查 API Key 是否正确
   - 确认 API Key 是否有足够的额度

4. **检查配置文件引用**：
   ```toml
   # config/model_config.toml
   api_key = "${DEEPSEEK_API_KEY}"  # 确保变量名一致
   ```
</details>

<details>
<summary><b>Q: 如何切换不同的 AI 模型？</b></summary>

**A:** 编辑 `config/model_config.toml` 文件：

```toml
# 方式一：修改默认模型
[default_model]
model = "deepseek-chat"  # 改为你想用的模型名

# 方式二：添加新模型配置
[[models]]
name = "my-model"
api_provider = "DeepSeek"
model_name = "deepseek-chat"
```
</details>

<details>
<summary><b>Q: WebUI 无法访问？</b></summary>

**A:**

1. **检查配置**：
   ```bash
   # .env 文件
   WEBUI_ENABLED=true  # 确保启用
   WEBUI_HOST=0.0.0.0  # 允许外部访问
   WEBUI_PORT=8001     # 确认端口未被占用
   ```

2. **检查防火墙**：
   - Windows：允许 Python 通过防火墙
   - Linux：`sudo ufw allow 8001`

3. **检查端口占用**：
   ```bash
   # Windows
   netstat -ano | findstr :8001

   # Linux/macOS
   lsof -i :8001
   ```
</details>

### 使用相关

<details>
<summary><b>Q: MaiBot 不回复消息？</b></summary>

**A:** 检查以下几点：

1. **确认 NapCat 连接正常**：
   - 查看 MaiBot 启动日志
   - 确认 NapCat 适配器正常运行

2. **检查群聊配置**：
   - 确认 MaiBot 已加入目标群聊
   - 检查群聊权限设置

3. **查看日志输出**：
   - 启动时添加 `--debug` 参数查看详细日志
   - 检查是否有错误信息

4. **验证 API 调用**：
   - 确认 API Key 有效且有余额
   - 检查网络连接是否正常
</details>

<details>
<summary><b>Q: Token 消耗过快怎么办？</b></summary>

**A:** 优化建议：

1. **调整模型参数**：
   ```toml
   # config/model_config.toml
   [model_settings]
   max_tokens = 500  # 限制输出长度
   temperature = 0.7  # 降低随机性
   ```

2. **使用更便宜的模型**：
   - DeepSeek：性价比高
   - SiliconFlow：开源模型选择多

3. **限制对话历史长度**：
   - 减少上下文记忆轮数
   - 定期清理对话历史

4. **设置触发条件**：
   - 只在被 @ 时回复
   - 设置关键词触发
</details>

<details>
<summary><b>Q: QQ 账号被限制怎么办？</b></summary>

**A:**

1. **降低活跃度**：
   - 减少发言频率
   - 增加回复延迟
   - 避免频繁发送相同内容

2. **使用小号**：
   - 不要使用主账号运行机器人
   - 准备多个备用账号

3. **遵守规则**：
   - 不发送违规内容
   - 不进行广告推广
   - 遵守群规和平台规则

4. **风险提示**：
   - QQ 机器人存在被限制风险
   - 请自行评估风险后使用
</details>

### 开发相关

<details>
<summary><b>Q: 如何开发自定义插件？</b></summary>

**A:**

1. **查看官方文档**：
   - [MaiBot 开发文档](https://docs.mai-mai.org/develop/)

2. **参考示例插件**：
   - 查看 `src/plugins/` 目录下的现有插件
   - 学习插件开发模式

3. **插件开发基本结构**：
   ```python
   from src.plugins import Plugin

   class MyPlugin(Plugin):
       def __init__(self):
           super().__init__()
           self.name = "插件名称"

       async def on_message(self, message):
           # 处理消息逻辑
           pass
   ```

4. **加入开发群**：
   - [插件开发群](https://qm.qq.com/q/1036092828)
</details>

<details>
<summary><b>Q: 如何贡献代码？</b></summary>

**A:**

1. **Fork 本仓库**
2. **创建特性分支**：`git checkout -b feature/my-feature`
3. **提交更改**：`git commit -m 'Add some feature'`
4. **推送到分支**：`git push origin feature/my-feature`
5. **创建 Pull Request**

**代码规范**：
- 遵循 PEP 8 编码规范
- 添加必要的注释和文档
- 编写单元测试
- 确保代码通过 CI 检查
</details>

---

## 📊 更新日志

### v0.11.6 Fork 增强版 (2026-02-09)

**🔒 安全性改进**
- ✅ API Keys 环境变量化
- ✅ 完善 .gitignore 配置
- ✅ 添加环境变量配置模板

**📝 代码质量**
- ✅ 核心文件添加详细中文注释
- ✅ 配置文件注释完善
- ✅ API 配置逻辑优化

**🗂️ 项目结构**
- ✅ 清理无用文件
- ✅ 整理文档目录
- ✅ 优化项目结构

**📚 文档更新**
- ✅ 创建详细的 README
- ✅ 添加使用示例
- ✅ 完善 FAQ 文档

查看完整更新日志：[MaiBot 原项目更新日志](MaiBot/changelogs/changelog.md)

---

## 🌟 Star 历史

[![Star History Chart](https://api.star-history.com/svg?repos=wenjinqing/MaiBot_wenfork&type=Date)](https://star-history.com/#wenjinqing/MaiBot_wenfork&Date)

---

## 📂 项目结构

```
MaiBot_wenfork/
├── MaiBot/                      # 主程序目录
│   ├── bot.py                   # 启动入口
│   ├── src/                     # 源代码
│   │   ├── config/              # 配置模块
│   │   │   └── api_ada_configs.py  # API 配置（支持环境变量）
│   │   ├── core/                # 核心功能
│   │   └── plugins/             # 插件系统
│   ├── config/                  # 配置文件
│   │   └── model_config.toml    # 模型配置
│   ├── template/                # 配置模板
│   │   └── template.env         # 环境变量模板
│   ├── .env                     # 环境变量（不提交到 Git）
│   └── start.bat                # Windows 启动脚本
├── MaiBot-Napcat-Adapter/       # NapCat 协议适配器
├── library/                     # 知识库文件
└── mod/                         # 外部插件模块
```

---

## 🔒 安全建议

1. **保护 API Keys**
   - 不要将 `.env` 文件提交到版本控制系统
   - 定期轮换 API Keys
   - 如果 API Key 泄露，立即前往服务商平台撤销并重新生成

2. **生产环境部署**
   - 建议使用系统环境变量或密钥管理服务
   - 限制 `.env` 文件的访问权限
   - 定期审查 API 使用情况

3. **QQ 机器人风险**
   - QQ 机器人存在被限制风险，请自行了解
   - 谨慎使用，遵守相关法律法规
   - AI 生成内容不代表本项目团队的观点和立场

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📜 许可证

本项目采用 [GPL-3.0](LICENSE) 许可证。

---

## 🙏 致谢

### 原项目

- [MaiBot](https://github.com/MaiM-with-u/MaiBot) - 原始项目
- [略nd](https://space.bilibili.com/1344099355) - 为麦麦绘制人设

### 技术支持

- [NapCat](https://github.com/NapNeko/NapCatQQ) - 现代化的基于 NTQQ 的 Bot 协议端实现

### 社区

感谢所有为 MaiBot 项目做出贡献的开发者和用户！

---

## 📞 联系方式

- **原项目仓库**: [MaiM-with-u/MaiBot](https://github.com/MaiM-with-u/MaiBot)
- **Fork 仓库**: [wenjinqing/MaiBot_wenfork](https://github.com/wenjinqing/MaiBot_wenfork)
- **原项目文档**: [docs.mai-mai.org](https://docs.mai-mai.org)

### 💬 交流群

**技术交流群**：
- [麦麦脑电图](https://qm.qq.com/q/RzmCiRtHEW)
- [麦麦大脑磁共振](https://qm.qq.com/q/VQ3XZrWgMs)
- [麦麦要当VTB](https://qm.qq.com/q/wGePTl1UyY)

**聊天吹水群**：
- [麦麦之闲聊群](https://qm.qq.com/q/JxvHZnxyec)

**插件开发/测试版讨论群**：
- [插件开发群](https://qm.qq.com/q/1036092828)

---

## ⚠️ 免责声明

> 使用本项目前必须阅读和同意原项目的[用户协议](MaiBot/EULA.md)和[隐私协议](MaiBot/PRIVACY.md)。
>
> 本应用生成内容来自人工智能模型，由 AI 生成，请仔细甄别，请勿用于违反法律的用途。

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐ Star 支持一下！**

Made with ❤️ by [wenjinqing](https://github.com/wenjinqing)

Based on [MaiBot](https://github.com/MaiM-with-u/MaiBot) by [MaiM-with-u](https://github.com/MaiM-with-u)

</div>
