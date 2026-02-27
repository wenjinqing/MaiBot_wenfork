<div align="center">

# 🤖 MaiBot

**An Intelligent QQ Bot Framework Based on HeartFlow Architecture**

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-QQ-blue.svg)](https://im.qq.com/)

[English](README_EN.md) | [简体中文](README.md)

</div>

---

## 📖 Introduction

MaiBot is an intelligent QQ bot framework based on the HeartFlow architecture, supporting multiple bot instances, plugin system, memory management, emotion system, and other advanced features. With modular design and flexible configuration system, you can quickly create AI bots with unique personalities.

## ✨ Key Features

- 🧠 **HeartFlow Architecture** - Intelligent dialogue system with context understanding and emotional interaction
- 🎭 **Multi-Personality System** - Support multiple bot instances with independent personalities and memories
- 🔌 **Plugin System** - Flexible plugin architecture supporting commands, actions, events, and more
- 💾 **Memory Management** - Long-term memory storage for user relationships, interests, and shared experiences
- 💕 **Emotion System** - Intimacy, mood values, confession system for more realistic interactions
- 🌐 **Web Management UI** - Intuitive web interface with real-time log viewing and configuration management
- 🔐 **Secure Configuration** - Environment variable management for sensitive information

## 🚀 Quick Start

### Requirements

- Python 3.10+
- QQ Bot Framework (e.g., Napcat-Adapter)
- At least one AI service API Key

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/wenjinqing/MaiBot_wenfork.git
   cd MaiBot_wenfork
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   ```bash
   cp .env.example .env
   # Edit .env and fill in your configuration
   ```

4. **Start the bot**

   ```bash
   python main.py
   ```

5. **Access Web UI**

   Open browser: `http://localhost:8001`

## 📚 Documentation

- [Environment Configuration Guide](docs/环境变量配置指南.md)
- [Plugin Development Guide](docs/插件开发指南.md)
- [Memory System Guide](docs/记忆系统使用指南.md)

## 🔌 Plugin System

MaiBot supports a flexible plugin system for easy functionality extension.

### Built-in Plugins

- **emoji_plugin** - Emoji management and sending
- **repeat_plugin** - Smart repeat functionality
- **reminder_plugin** - Reminders and task management
- **tts_plugin** - Text-to-speech
- **music_plugin** - Music and image retrieval

### Custom Plugin Development

```python
from src.plugin_system.base import BaseCommand

class MyCommand(BaseCommand):
    command_name = "hello"
    command_pattern = r"^/hello$"

    async def execute(self):
        await self.send_text("Hello, World!")
        return True, "Success", True
```

## 🛠️ Tech Stack

- **Language**: Python 3.10+
- **Web Framework**: FastAPI
- **Database**: SQLite + Peewee ORM
- **AI Integration**: OpenAI SDK, Google GenAI
- **Frontend**: HTML5, CSS3, JavaScript

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the [GPL-3.0](LICENSE) License.

## 🙏 Acknowledgments

- Thanks to all contributors
- Thanks to the open-source community
- Special thanks to [MaiBot Original Project](https://github.com/MaiM-with-u/MaiBot)

---

<div align="center">

**If this project helps you, please give it a ⭐️ Star!**

Made with ❤️ by MaiBot Team

</div>
