<div align="center">

# 🤖 MaiBot

**基于思维流的智能 QQ 机器人框架**

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-QQ-blue.svg)](https://im.qq.com/)

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [配置指南](#-配置指南) • [文档](#-文档) • [贡献指南](#-贡献指南)

</div>

---

## 📖 项目简介

MaiBot 是一个基于思维流（HeartFlow）架构的智能 QQ 机器人框架，支持多机器人实例、插件系统、记忆管理、情感系统等高级功能。通过模块化设计和灵活的配置系统，你可以快速创建具有独特人格的 AI 机器人。

> **仓库地址**: https://github.com/wenjinqing/MaiBot_wenfork.git

### ✨ 核心特性

- 🧠 **思维流架构** - 基于 HeartFlow 的智能对话系统，支持上下文理解和情感交互
- 🎭 **多人格系统** - 支持配置多个机器人实例，每个实例拥有独立的人格和记忆
- 🔌 **插件系统** - 灵活的插件架构，支持命令、动作、事件等多种组件类型
- 💾 **记忆管理** - 长期记忆存储，支持用户关系、兴趣爱好、共同经历等多维度记忆
- 💕 **情感系统** - 亲密度、心情值、表白系统，打造更真实的互动体验
- 🌐 **Web 管理界面** - 直观的 Web UI，支持实时日志查看、配置管理等
- 🔐 **安全配置** - 环境变量管理敏感信息，支持多种 AI 服务商 API

---

## 🎯 功能特性

### 核心功能

| 功能 | 说明 |
|------|------|
| 💬 **智能对话** | 基于大语言模型的自然对话，支持上下文理解 |
| 🎨 **表情包系统** | 智能表情包匹配和发送 |
| 🖼️ **图片识别** | 支持图片内容识别和描述 |
| 🔊 **语音识别** | 语音消息转文字 |
| 📝 **知识库** | 支持导入和检索知识库内容 |
| ⏰ **提醒功能** | 定时提醒和任务管理 |
| 🔁 **复读检测** | 智能复读功能 |

### 高级功能

- **多机器人部署** - 单进程运行多个机器人实例，完全的数据隔离
- **主动对话** - 根据时间和活跃度主动发起聊天
- **关系系统** - 亲密度、心情值、表白、恋爱状态管理
- **记忆系统** - 用户兴趣、动态、共同经历的长期记忆
- **插件生态** - 支持自定义插件开发，扩展机器人功能

### 支持的 AI 服务

- ✅ SiliconFlow
- ✅ DeepSeek
- ✅ 阿里百炼（Bailian）
- ✅ Google Gemini
- ✅ 其他兼容 OpenAI API 的服务

---

## 🚀 快速开始

### 环境要求

- Python 3.10 或更高版本
- QQ 机器人框架（如 Napcat-Adapter）
- 至少一个 AI 服务商的 API Key

### 安装步骤

1. **克隆项目**

   ```bash
   git clone https://github.com/wenjinqing/MaiBot_wenfork.git
   cd MaiBot_wenfork
   ```

2. **安装依赖**

   ```bash
   pip install -r requirements.txt
   ```

3. **配置环境变量**

   ```bash
   # 复制环境变量模板
   cp .env.example .env

   # 编辑 .env 文件，填入你的配置
   nano .env
   ```

   必填配置：
   ```bash
   # 机器人 QQ 账号
   MAIMAI_QQ_ACCOUNT=你的QQ账号

   # AI 服务 API Key（至少配置一个）
   SILICONFLOW_API_KEY=你的API_Key
   ```

4. **配置机器人人格**

   编辑 `config/bot_config.toml`，自定义机器人的人格、昵称、说话风格等：

   ```toml
   [bot]
   nickname = "麦麦"

   [personality]
   personality = "我是一个乐观开朗的猫娘..."
   reply_style = "语气轻松自然，回复简洁口语化..."
   ```

5. **启动机器人**

   ```bash
   python main.py
   ```

6. **访问 Web 管理界面**

   打开浏览器访问：`http://localhost:8001`

---

## ⚙️ 配置指南

### 目录结构

```
MaiBot/
├── config/              # 配置文件目录
│   ├── bot_config.toml      # 主机器人配置
│   ├── model_config.toml    # AI 模型配置
│   └── yiyi_bot_config.toml # 第二个机器人配置（可选）
├── src/                 # 源代码目录
│   ├── chat/               # 对话系统
│   ├── plugin_system/      # 插件系统
│   ├── memory_system/      # 记忆系统
│   └── webui/              # Web 界面
├── plugins/             # 插件目录
├── data/                # 数据目录
├── docs/                # 文档目录
├── .env                 # 环境变量配置（需自行创建）
└── main.py              # 主程序入口
```

### 核心配置文件

#### 1. 环境变量配置 (`.env`)

存储敏感信息，不会被提交到 Git：

```bash
# 机器人账号
MAIMAI_QQ_ACCOUNT=你的QQ账号

# API Keys
SILICONFLOW_API_KEY=你的API_Key
DEEPSEEK_API_KEY=你的API_Key
```

详细配置说明：[环境变量配置指南](docs/环境变量配置指南.md)

#### 2. 机器人配置 (`config/bot_config.toml`)

配置机器人的人格、行为、兴趣等：

```toml
[bot]
platform = "qq"
qq_account = "${MAIMAI_QQ_ACCOUNT}"  # 从环境变量读取
nickname = "麦麦"

[personality]
personality = "你的机器人人格描述..."
reply_style = "说话风格描述..."
interest = "兴趣爱好描述..."
```

#### 3. 模型配置 (`config/model_config.toml`)

配置 AI 模型和 API：

```toml
[[models]]
name = "deepseek-chat"
api_key = "${DEEPSEEK_API_KEY}"
base_url = "https://api.deepseek.com"
model = "deepseek-chat"
```

### 多机器人配置

支持在同一进程中运行多个机器人实例：

1. 复制 `config/bot_config.toml` 为 `config/bot2_config.toml`
2. 修改新配置文件中的 QQ 账号、昵称、人格等
3. 在 `.env` 中添加新的环境变量
4. **重要：配置独立的端口**，避免端口冲突：
   ```toml
   [maim_message]
   use_custom = true
   host = "127.0.0.1"
   port = 8092  # 每个机器人使用不同的端口（8091, 8092, 8093...）
   mode = "ws"
   ```
5. 重启机器人

**端口分配建议：**
- 主程序：8000（.env 中的 PORT）
- WebUI：8001（.env 中的 WEBUI_PORT）
- 机器人1（君君）：8091
- 机器人2（伊伊）：8092
- 更多机器人：8093, 8094...

---

## 📚 文档

### 用户文档

- [环境变量配置指南](docs/环境变量配置指南.md) - 如何配置敏感信息
- [插件开发指南](docs/插件开发指南.md) - 如何开发自定义插件
- [记忆系统使用指南](docs/记忆系统使用指南.md) - 记忆系统的使用方法

### 开发文档

- [系统架构](docs/系统架构.md) - 项目整体架构说明
- [API 文档](docs/API文档.md) - RESTful API 接口文档
- [数据库设计](docs/数据库设计.md) - 数据库表结构说明

---

## 🔌 插件系统

MaiBot 支持灵活的插件系统，你可以轻松扩展机器人功能。

### 内置插件

- **emoji_plugin** - 表情包管理和发送
- **repeat_plugin** - 智能复读功能
- **reminder_plugin** - 提醒和任务管理
- **tts_plugin** - 文字转语音
- **music_plugin** - 音乐和图片获取

### 开发自定义插件

创建插件非常简单：

```python
from src.plugin_system.base import BaseCommand

class MyCommand(BaseCommand):
    command_name = "hello"
    command_pattern = r"^/hello$"

    async def execute(self):
        await self.send_text("Hello, World!")
        return True, "Success", True
```

详细教程：[插件开发指南](docs/插件开发指南.md)

---

## 🛠️ 技术栈

- **语言**: Python 3.10+
- **Web 框架**: FastAPI
- **数据库**: SQLite + Peewee ORM
- **AI 集成**: OpenAI SDK, Google GenAI
- **前端**: HTML5, CSS3, JavaScript
- **其他**: aiohttp, structlog, python-dotenv

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

### 如何贡献

1. Fork 本项目
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

### 代码规范

- 遵循 PEP 8 代码风格
- 使用类型注解
- 添加必要的注释和文档字符串
- 确保所有测试通过

---

## 📝 更新日志

### v1.0.0 (2025-02-25)

- ✨ 初始版本发布
- ✅ 支持多机器人部署
- ✅ 完整的插件系统
- ✅ 记忆和情感系统
- ✅ Web 管理界面
- ✅ 环境变量配置

---

## ⚠️ 免责声明

本项目仅供学习和研究使用，请勿用于任何违法用途。使用本项目所产生的一切后果由使用者自行承担。

---

## 📄 开源协议

本项目采用 [GPL-3.0](LICENSE) 协议开源。

---

## 🙏 致谢

- 感谢所有贡献者的付出
- 感谢开源社区提供的优秀工具和库
- 特别感谢 [MaiBot 原项目](https://github.com/MaiM-with-u/MaiBot) 的开源贡献

---

## 📮 联系方式

- **Issues**: [GitHub Issues](https://github.com/wenjinqing/MaiBot_wenfork/issues)
- **Discussions**: [GitHub Discussions](https://github.com/wenjinqing/MaiBot_wenfork/discussions)
- **仓库地址**: https://github.com/wenjinqing/MaiBot_wenfork.git

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star 支持一下！**

Made with ❤️ by MaiBot Team

</div>
