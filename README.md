#  MaiBot 多机部署完全分离部署

基于 [MaiBot](https://github.com/MaiM-with-u/MaiBot) 的多机器人完全分离部署方案。本项目实现了多个 MaiBot 实例的代码、配置、数据库、缓存、日志的完全独立，支持零冲突并行运行。

> 本仓库是 MaiBot 的 **fork + 多实例部署工程化改造**。核心框架来自 [MaiM-with-u/MaiBot](https://github.com/MaiM-with-u/MaiBot)，插件来自社区与自研，详见下方插件清单。

## 📦 项目简介

本仓库以「君君（JunJun）」实例为主干，提供一套完整分离的 MaiBot 部署方案：

- ✅ 独立的代码目录与配置文件
- ✅ 独立的数据库与缓存
- ✅ 独立的端口与日志
- ✅ 零冲突、零干扰，可分别启停/升级
- ✅ 集成了 20+ 个功能插件（社区 + 自研）

## 🗂️ 目录结构

```
MaiM/
├── MaiBot-JunJun/                 # 君君机器人（主干，纳入版本库）
│   ├── MaiBot/                    # MaiBot 本体
│   │   ├── bot.py                 # 启动入口
│   │   ├── template/              # 配置模板（.env / toml）
│   │   ├── config/                # 实际配置（已 gitignore）
│   │   ├── data/                  # 数据库与缓存（已 gitignore）
│   │   ├── logs/                  # 日志（已 gitignore）
│   │   └── mod/                   # 插件目录
│   └── MaiBot-Napcat-Adapter/     # NapCat 适配器
├── MaiBot-YiYi/                   # 伊伊机器人（本地保留，不入库）
├── NapCat.Shell/                  # NapCat 运行时（本地保留，不入库）
├── .gitignore
└── README.md
```

> `MaiBot-YiYi/` 与 `NapCat.Shell/` 已通过 `.gitignore` 排除，本地保留但不上传。如需第二实例，可复制 `MaiBot-JunJun/` 结构并改端口。

## 🚀 快速开始

### 环境要求

- Python 3.10+
- [NapCat](https://github.com/NapNeko/NapCatQQ)（QQ 协议实现）
- 至少一个 AI 服务商的 API Key（推荐 SiliconFlow / DeepSeek / Google）

### 安装步骤

1. **克隆仓库**
   ```bash
   git clone https://github.com/wenjinqing/MaiBot_wenfork.git
   cd MaiBot_wenfork
   ```

2. **配置君君**
   ```bash
   cd MaiBot-JunJun/MaiBot
   cp template/template.env .env.junjun
   # 编辑 .env.junjun，填入 API Keys 与 QQ 账号
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置 NapCat**
   - 启动 NapCat，登录 QQ
   - 在 NapCat WebUI 中填入适配器地址：`ws://localhost:8095`（对应 JunJun 的 `napcat_server` 端口）

5. **启动**
   ```bash
   python bot.py
   ```

详见 [MaiBot 官方文档](https://docs.mai-mai.org)。

## 📊 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| JunJun WebUI | 8001 | Web 管理界面 |
| JunJun 消息服务 | 8091 | maim_message 服务（`/ws`） |
| JunJun NapCat 适配器 | 8095 | 适配器监听端口 |

如需第二实例，将上述端口 +1（8092/8097）并同步修改适配器的 `maibot_server.port`。

## 🧩 插件清单

插件统一位于 `MaiBot-JunJun/MaiBot/mod/`。下表标注每个插件的来源：**社区** 表示来自第三方仓库（可能含本地二改），**自研/集成** 表示本仓库开发或无上游仓库。

| 插件目录 | 功能 | 版本 | 作者 | 来源 |
|----------|------|------|------|------|
| `acpoke_plugin` | 戳一戳互动 | v0.4.3 | 何夕 | [Heximiao/acpoke_plugin](https://github.com/Heximiao/acpoke_plugin) |
| `ai_draw_plugin` | AI 文生图（ModelScope） | v1.0.0 | JunJun | 自研 |
| `bilibili_video_sender_plugin` | B 站视频解析发送 | v1.3.6 | XinxInxiN0 | [XinxInxiN0/bilibili_video_sender_plugin](https://github.com/XinxInxiN0/bilibili_video_sender_plugin) |
| `ChatFrequency` | 发言频率控制 | v2.0.0 | SengokuCola | [SengokuCola/BetterFrequency](https://github.com/SengokuCola/BetterFrequency) |
| `chat_context_selector_plugin` | 聊天上下文选择 | v1.0.0 | Assistant | 自研/集成 |
| `chat_screenshot_plugin` | 聊天记录截图 | v1.0.0 | Assistant | 自研/集成 |
| `cross_scene_chat_plugin` | 跨场景聊天查询 | v1.0.0 | MaiBot | 自研/集成 |
| `detailed_explanation_plugin` | 长文本详细解释 | v1.1.0 | CharTyr | [CharTyr/MaiBot-DetailedExplanation-Plugin](https://github.com/CharTyr/MaiBot-DetailedExplanation-Plugin) |
| `douyin_video_plugin` | 抖音视频解析 | v1.0.2 | MaiBot-JunJun | 自研（API 来自 [xingzhige.com](https://api.xingzhige.com/API/douyin/)） |
| `emoji_manage_plugin` | 表情包管理 | v1.0.0 | SengokuCola | [SengokuCola/BetterEmoji](https://github.com/SengokuCola/BetterEmoji) |
| `google_search_plugin` | 联网搜索（多引擎） | v1.2.0 | 晴空 | [XXXxx7258/google_search_plugin](https://github.com/XXXxx7258/google_search_plugin) |
| `hello_world_plugin` | 示例插件 | v1.0.0 | MaiBot 团队 | [MaiM-with-u/maibot](https://github.com/MaiM-with-u/maibot) |
| `image_viewer_plugin` | 图片查看 | v1.0.0 | JunJun | 自研 |
| `intimacy_query_plugin` | 好感度查询 | v1.0.0 | MaiBot Team | 自研/集成 |
| `jrys_prpr_maimbot` | 今日运势卡片 | v1.7.0 | MaiM | 集成（[npm 包](https://www.npmjs.com/package/koishi-plugin-jrys-prpr)） |
| `lolicon_setu_plugin` | Lolicon 色图 | v2.1.1 | 久远 | [saberlights/lolicon-setu-plugin](https://github.com/saberlights/lolicon-setu-plugin) |
| `Maibot_topic_finder_plugin` | 找话题 | v1.1.0 | CharTyr | [CharTyr/Maibot_topic_finder_plugin](https://github.com/CharTyr/Maibot_topic_finder_plugin) |
| `maizone_plugin` | 麦麦空间（QQ 空间） | v2.5.0 | internetsb | [internetsb/Maizone](https://github.com/internetsb/Maizone) |
| `music_player_plugin` | 音乐播放 | v1.0.0 | JunJun | 自研 |
| `netdisk_parser_plugin` | 网盘直链解析 | v1.0.0 | MaiBot-JunJun | 自研（基于 [qaiu/netdisk-fast-download](https://github.com/qaiu/netdisk-fast-download)） |
| `news_plugin` | 60 秒新闻 | v1.0.0 | JunJun | 自研 |
| `tts_voice_plugin` | 统一 TTS 语音合成 | v3.0.0 | 靓仔 | [xuqian13/tts_voice_plugin](https://github.com/xuqian13/tts_voice_plugin) |
| `wife_plugin` | 抽群老婆 | v1.0.0 | Hug_Yo | [Hug-Yo/wife_plugin](https://github.com/Hug-Yo/wife_plugin) |

> 各插件目录内通常含 `README.md` 与 `_manifest.json`，可查看更详细的用法与原作者信息。部分插件经本地二次修改以适配多实例部署。

## ⚙️ 配置说明

### `.env.junjun` 关键项

```bash
WEBUI_ENABLED=true
WEBUI_PORT=8001
HOST=127.0.0.1
PORT=8091                 # MaiBot 消息服务端口（适配器连 ws://localhost:8091/ws）

# API Keys（必填，按需）
SILICONFLOW_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
```

> NapCat WebUI 里填的「适配器地址」是 `ws://localhost:8095`（对应 `[napcat_server]` 端口），不是上面的 `PORT`。两者需分别配置。

## 🔍 可观测性（Langfuse）

本项目集成了 [Langfuse](https://langfuse.com)（自托管）用于 Agent 调用链追踪、token 成本监控与耗时分析。

**埋点覆盖**（见 `src/common/langfuse_client.py`）：
- LLM 调用：`src/llm_models/utils_model.py` 的 `_execute_request`，记录模型、耗时、token。
- 消息回复顶层：`group_generator.py` / `private_generator.py` 的 `generate_reply_with_context`，作为 trace 根节点。
- 工具调用：`src/plugin_system/core/tool_use.py` 的 `execute_tool_call`，记录工具名、参数、耗时。

**启用步骤**：
1. 启动 Langfuse 服务（仓库根目录）：
   ```bash
   docker compose -f langfuse/docker-compose.yml up -d
   ```
2. 访问 `http://localhost:3000`，创建账号与项目，获取 `public_key` / `secret_key`。
3. 在 `MaiBot-JunJun/MaiBot/.env.junjun` 填入：
   ```
   LANGFUSE_ENABLED=true
   LANGFUSE_HOST=http://localhost:3000
   LANGFUSE_PUBLIC_KEY=pk-lf-xxx
   LANGFUSE_SECRET_KEY=sk-lf-xxx
   ```
4. 启动机器人，发一条消息，回到 Langfuse UI 即可看到完整调用链。

> 未启用时（`LANGFUSE_ENABLED=false`）所有埋点静默空操作，不影响机器人运行。
## 🛡️ 敏感信息保护

- `.env`、`config/*.toml`、各插件 `config.toml`、`mcp_config.json`、`*.db`、`local_store.json` 等均已通过 `.gitignore` 排除。
- 任何 API Key、QQ 账号、Token 仅写在本地配置文件中，不会进入版本库。
- 部署前请确认 `git status` 不含敏感文件。

## 🧯 故障排查

| 问题 | 解决 |
|------|------|
| 端口被占用 `error 10048` | `netstat -ano \| findstr "8091 8095"`，停掉占用进程或改端口 |
| 无法获取用户信息 | 重启 NapCat，等待完全登录后再启动机器人 |
| `database is locked` | 确认无多实例同时运行；删除 `.db-shm`/`.db-wal` 后重启 |
| NapCat 连不上适配器 | 检查 `[napcat_server]` 端口与 NapCat WebUI 填的地址是否一致 |

## 📜 开源协议

本项目基于 [GPL-3.0](LICENSE) 协议开源。各插件遵循其原始协议（见各插件 `_manifest.json` 的 `license` 字段）。

## 🙏 致谢

- [MaiBot](https://github.com/MaiM-with-u/MaiBot) — 原始项目
- [NapCat](https://github.com/NapNeko/NapCatQQ) — QQ 协议实现
- 各插件作者（见上方插件清单）

## 📬 联系方式

- Issues: [GitHub Issues](https://github.com/wenjinqing/MaiBot_wenfork/issues)
- 官方文档: [docs.mai-mai.org](https://docs.mai-mai.org)

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star 支持一下！**

Made with ❤️ by wenjinqing

</div>
