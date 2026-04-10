# 启动说明（MaiBot-JunJun）

本仓库只跑 **君君** 单实例，与 `MaiBot-YiYi` 是多实例副本不同，这里**不要**再放 `bot_yiyi` 一类入口。

| 方式 | 说明 |
|------|------|
| **`python launch/junjun.py`** | 推荐：工作目录自动定为项目根 |
| `python bot_junjun.py` / `python bot.py` | 兼容：内部转调到 `launch/junjun.py` |

- 配置：`config/bot_config.toml`
- 环境：根目录 `.env`；若存在 `.env.junjun` 会先加载，再加载 `.env`（后者覆盖同名变量）

人设改 `[personality]` 请编辑 `config/bot_config.toml`，不要指望 `.env` 里的 `MAIBOT_PERSONALITY` 覆盖正文。

根目录下的 **`archive/`** 存放已迁移的测试脚本与生成物，见 `archive/README.md`；历史笔记类文件在 **`docs/archive/root-notes/`**。
