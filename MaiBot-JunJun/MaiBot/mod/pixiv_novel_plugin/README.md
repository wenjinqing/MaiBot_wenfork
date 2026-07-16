# Pixiv小说插件 (Pixiv Novel Plugin)

> 基于 [Pixiv 官方 Web API](https://www.pixiv.net) 的 MaiBot 小说下载插件

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📖 简介

Pixiv小说插件是一个 MaiBot 插件，通过对接 Pixiv 官方 Web AJAX 接口，**下载整部小说系列或单篇正文，合成一个 txt 文件发送**。通过 NapCat OneBot HTTP API 以文件形式发送，失败时回退为合并转发分段文本。

## ✨ 功能特性

- 📚 **小说系列下载** - 下载整个系列的全部章节，合成一个 txt 文件
- 📖 **单篇正文下载** - 下载单篇小说正文为 txt 文件
- 📄 **txt 文件发送** - 通过 NapCat OneBot API 以文件形式发送
- 🔄 **回退机制** - 文件发送失败时回退为合并转发分段文本
- 🔐 **Cookie 鉴权** - 配置 PHPSESSID 后可抓取登录后可见内容（如 R-18）
- 🌐 **HTTP 代理** - 支持配置代理访问 Pixiv
- 🛡️ **冷却管理** - 防止刷屏的冷却时间控制
- 🔐 **权限管控** - QQ 白名单，只有名单内 QQ 才能触发（涉及 R18 内容管控）
- 🔎 **小说搜索** - `/novel search <关键词>` 搜索小说，返回编号列表（仅私聊）
- 📥 **交互式下载** - `/novel dl <编号>` 按搜索结果内部编号下载，每次搜索重新编号
- 🚫 **群聊拦截** - 小说功能仅限私聊，群聊触发统一回复『该功能暂不支持群聊使用』
- 🛑 **关键词黑名单** - 搜索关键词含『幼女/未成年/儿童/萝莉』等敏感词自动拒绝
- ⚙️ **灵活配置** - 丰富的配置选项

## 📦 安装

### 方式一：Git Clone（推荐）

```bash
cd /path/to/MaiBot/plugins
git clone https://github.com/saberlights/pixiv-novel-plugin.git pixiv_novel_plugin
```

### 方式二：手动下载

1. 下载 [最新 Release](https://github.com/saberlights/pixiv-novel-plugin/releases)
2. 解压到 `MaiBot/plugins/` 目录
3. 重命名文件夹为 `pixiv_novel_plugin`

### 安装依赖

插件需要 `aiohttp` 库（MaiBot 通常已自带）：

```bash
pip install aiohttp>=3.8.0
```

## ⚙️ 配置

编辑 `config.toml` 文件进行配置：

```toml
[auth]
# Pixiv 登录 Cookie (PHPSESSID=...)
pixiv_cookie = "

[network]
# HTTP 代理地址 (如 http://127.0.0.1:7890)，留空不使用代理
proxy = "

[napcat]
# NapCat OneBot HTTP API 配置（用于发送 txt 文件）
host = 127.0.0.1
port = 5700
token = "

[features]
cooldown_seconds = 30
api_timeout = 30
max_chapters_per_series = 999   # 999 表示下载全部章节
use_forward_message = true      # 文件发送失败时回退为合并转发
save_dir = data/pixiv_novel   # txt 文件保存目录
```

### 获取 Cookie（重要）

匿名访问只能抓取到公开作品，**R-18 及部分作品必须配置 Cookie**：

1. 浏览器登录 https://www.pixiv.net
2. 按 `F12` 打开开发者工具
3. 切到 `Application`（Chrome）或 `存储`（Firefox）→ `Cookies` → `https://www.pixiv.net`
4. 找到 `PHPSESSID`，复制其值
5. 填入配置：`pixiv_cookie = PHPSESSID=12345678_xxxxxxxxx`

### NapCat 配置

插件通过 NapCat 的 OneBot HTTP API 发送 txt 文件，需确保：

1. NapCat 已开启 HTTP Server（端口默认 5700）
2. `config.toml` 中 `[napcat]` 的 `host`/`port`/`token` 与 NapCat 设置一致
3. Docker 部署时 `host` 填服务名 `napcat`，本机部署填 `127.0.0.1`

## 🚀 使用

### 命令格式

```
/novel <系列URL或ID>               下载整个系列为 txt 发送
/novel read <单篇URL或ID>           仅下载单篇为 txt 发送
/novel list <系列URL或ID>           只列出章节目录
/novel search <关键词>             搜索小说，返回编号列表（仅私聊）
/novel dl <编号>                    按搜索结果编号下载对应小说
/novel help                         显示帮助
```

### 示例

```
/novel https://www.pixiv.net/novel/series/14998441
/novel 14998441
/novel read https://www.pixiv.net/novel/show.php?id=12345678
/novel read 12345678
/novel list 14998441
```
/novel search 異世界転生
/novel dl 3
```

### 下载流程（系列）

1. 抓取系列元信息（标题、作者、总章节数）
2. 分页抓取所有章节列表
3. 逐章抓取正文，每章附带标题/作者/标签/链接
4. 全部合成一个 txt 文件（带头部信息）
5. 通过 NapCat OneBot API 发送 txt 文件
6. 若文件发送失败，回退为合并转发分段文本

## 🔧 工作原理

插件通过 Pixiv 官方 Web AJAX 接口抓取数据：

| 用途 | 接口 |
|------|------|
| 系列元信息 | `https://www.pixiv.net/ajax/novel/series/{series_id}` |
| 系列章节列表 | `https://www.pixiv.net/ajax/novel/series_content/{series_id}` |
| 单篇元信息 | `https://www.pixiv.net/ajax/novel/{novel_id}` |
| 单篇正文 | `https://www.pixiv.net/ajax/novel/{novel_id}/content` |

请求时携带 `User-Agent`、`Cookie` 等头模拟浏览器访问。文件通过 NapCat 的 `send_group_msg`/`send_private_msg` 发送 `file` 类型消息（`file:///` 协议）。

## ⚠️ 注意事项

- **必须配置 Cookie** 才能抓取 R-18 等登录后可见内容
- 必须正确配置 `[napcat]` 才能发送 txt 文件，否则会回退为分段文本
- 章节较多时下载耗时较长，请耐心等待
- 频繁请求可能触发 Pixiv 限流，请合理设置冷却时间
- Pixiv 在部分网络环境下需要代理才能访问
- 仅用于个人学习交流，请遵守 Pixiv 用户协议，不要传播抓取到的内容

## 📄 License

MIT
