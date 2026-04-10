# 启动说明（MaiBot-YiYi）

同一套代码里跑 **两个 QQ 实例** 时，用不同入口即可（勿与 `MaiBot-JunJun` 根目录混用）。

| 脚本 | 实例 | 配置文件 | `.env` |
|------|------|----------|--------|
| **`python launch/junjun.py`** | 君君 | `config/bot_config.toml` | `MAIBOT_*`，与根目录 `.env` |
| **`python launch/yiyi.py`** | 伊伊 | `config/yiyi_bot_config.toml` | `YIYI_*` 等；可选先读 `.env.yiyi` |

根目录 **`bot.py` / `bot_junjun.py` / `bot_yiyi.py`** 仅保留为兼容，内部会转调到上表对应脚本。

- 君君人设：改 `config/bot_config.toml` 的 `[personality]`
- 伊伊人设：改 `config/yiyi_bot_config.toml`（或该多实例结构中的对应段）

根目录 **`archive/`** 为归档区（测试脚本、生成文件），见 `archive/README.md`；零散说明在 **`docs/archive/root-notes/`**。
