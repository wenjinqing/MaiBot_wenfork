# MaiBot 项目目录结构

## 📁 根目录文件

| 文件 | 说明 |
|------|------|
| `bot_junjun.py` | 君君机器人启动脚本 |
| `bot_yiyi.py` | 伊伊机器人启动脚本 |
| `README.md` | 项目说明文档（中文） |
| `README_EN.md` | 项目说明文档（英文） |
| `requirements.txt` | Python 依赖列表 |
| `pyproject.toml` | 项目配置文件 |
| `docker-compose.yml` | Docker Compose 配置 |
| `Dockerfile` | Docker 镜像配置 |
| `mcp_config.json` | MCP 配置文件 |

## 📂 主要目录

### 核心目录

| 目录 | 说明 |
|------|------|
| `src/` | 源代码目录 |
| `config/` | 配置文件目录（包含机器人配置） |
| `plugins/` | 插件目录 |
| `data/` | 数据目录（数据库、用户数据） |
| `logs/` | 日志文件目录 |

### 文档和示例

| 目录 | 说明 |
|------|------|
| `docs/` | 项目文档 |
| `docs-src/` | 文档源码 |
| `examples/` | 示例代码 |
| `changelogs/` | 更新日志 |

### 工具和脚本

| 目录 | 说明 |
|------|------|
| `scripts/` | 脚本目录 |
| `scripts/emergency/` | 应急脚本（如敏感文件清理） |
| `tools/` | 工具文件 |
| `tools/statistics/` | 统计报告 |

### 依赖和资源

| 目录 | 说明 |
|------|------|
| `depends-data/` | 依赖数据文件 |
| `library/` | 库文件 |
| `mod/` | 模块文件 |
| `template/` | 配置模板 |

### Web 和适配器

| 目录 | 说明 |
|------|------|
| `webui/` | Web 管理界面 |
| `MaiBot-Napcat-Adapter/` | NapCat 适配器（君君） |
| `MaiBot-Napcat-Adapter-Yiyi/` | NapCat 适配器（伊伊） |

### 归档

| 目录 | 说明 |
|------|------|
| `archive/` | 归档文件（旧版本脚本、配置等） |

## 🔒 被忽略的目录（不会推送到 Git）

| 目录 | 说明 |
|------|------|
| `.venv/` | Python 虚拟环境 |
| `data/` | 用户数据和数据库 |
| `logs/` | 日志文件 |
| `__pycache__/` | Python 缓存 |

## 📋 源代码结构（src/）

```
src/
├── chat/                    # 聊天相关
│   ├── emoji_system/       # 表情系统
│   ├── heart_flow/         # 思维流系统
│   ├── knowledge/          # 知识库
│   ├── message_receive/    # 消息接收
│   ├── planner_actions/    # 规划器动作
│   ├── replyer/            # 回复生成器
│   └── utils/              # 工具函数
├── common/                  # 公共模块
│   ├── database/           # 数据库
│   ├── performance_monitor.py  # 性能监控
│   ├── prompt_guard.py     # Prompt 防护
│   └── relationship_updater.py # 关系更新
├── config/                  # 配置管理
├── express/                 # 表达学习
├── hippo_memorizer/        # 记忆系统
├── jargon/                 # 黑话识别
├── llm_models/             # LLM 模型接口
├── manager/                # 管理器
├── memory_system/          # 记忆检索
├── mood/                   # 情绪系统
├── person_info/            # 用户信息
├── plugin_system/          # 插件系统
├── plugins/                # 内置插件
│   └── built_in/
│       └── lite_search_plugin/  # 轻量级搜索插件
├── proactive_system/       # 主动对话系统
└── webui/                  # Web 界面后端
```

## 🚀 快速开始

### 启动君君
```bash
python bot_junjun.py
```

### 启动伊伊
```bash
python bot_yiyi.py
```

### 安装依赖
```bash
pip install -r requirements.txt
```

## 📝 配置文件位置

- 君君配置：`config/bot_config.toml`
- 伊伊配置：`config/yiyi_bot_config.toml`
- 环境变量：`.env`（需要从 `.env.example` 复制）

## 🔧 常用脚本

- 应急删除敏感文件：`scripts/emergency/emergency_remove_sensitive_files.sh`
- 统计报告：`tools/statistics/maibot_statistics.html`

## 📦 归档文件

- 旧版启动脚本：`archive/bot.py`
- 旧版配置：`archive/napcat_yiyi.json`
- 启动命令：`archive/启动命令.txt`
