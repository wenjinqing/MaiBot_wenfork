# Lolicon色图插件 (Lolicon Setu Plugin)

> 基于 [Lolicon API v2](https://api.lolicon.app) 的 MaiBot 色图获取插件

[![GitHub release](https://img.shields.io/github/v/release/saberlights/lolicon-setu-plugin)](https://github.com/saberlights/lolicon-setu-plugin/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📖 简介

Lolicon色图插件是一个功能强大的MaiBot插件，通过对接Lolicon API v2提供高质量的Pixiv图片获取服务。支持标签组合搜索、关键词搜索、长宽比筛选等高级功能。

## ✨ 功能特性

- 🎨 **Pixiv图源** - 所有图片来自Pixiv
- 🔍 **强大的搜索功能**:
  - 标签AND/OR组合搜索
  - 关键词模糊搜索（标题、作者、标签）
  - 作者UID筛选
  - 长宽比筛选（横图/竖图/方图/自定义）
- 🤖 **AI作品控制** - 可选择排除AI作品
- 🔞 **R18内容控制** - 可配置允许R18内容
- 📦 **合并转发格式** - 支持以聊天记录格式发送，整洁美观
- 🛡️ **冷却管理** - 防止刷屏的冷却时间控制
- ⚙️ **灵活配置** - 丰富的配置选项

## 📦 安装

### 方式一：Git Clone（推荐）

```bash
cd /path/to/MaiBot/plugins
git clone https://github.com/saberlights/lolicon-setu-plugin.git lolicon_setu_plugin
```

### 方式二：手动下载

1. 下载 [最新 Release](https://github.com/saberlights/lolicon-setu-plugin/releases)
2. 解压到 `MaiBot/plugins/` 目录
3. 重命名文件夹为 `lolicon_setu_plugin`

### 安装依赖

插件需要 `aiohttp` 库，请确保已安装：

```bash
pip install aiohttp>=3.8.0
```

## ⚙️ 配置

编辑 `config.toml` 文件进行配置：

### 基本配置

```toml
[plugin]
enabled = true  # 是否启用插件

[components]
enable_command = true  # 启用命令
```

### 功能配置

```toml
[features]
default_num = 1           # 默认获取数量
allow_r18 = false         # 是否允许R18（请谨慎开启）
cooldown_seconds = 10     # 冷却时间（秒）
size_list = ["regular"]   # 图片规格
api_timeout = 30          # API超时时间
use_forward_message = true  # 是否使用合并转发(聊天记录)格式发送
proxy = "i.pixiv.re"      # 图片代理服务器（可更换为其他反代）
```

**代理服务器说明**：
- 默认使用 `i.pixiv.re` 作为 Pixiv 图片的反代服务器
- 可更换为其他反代服务器，如 `i.pixiv.cat`、`i.pximg.net` 等
- 如果留空可能导致图片无法访问（Pixiv 在国内被墙）

## 🎮 使用方法

### 基础命令

```bash
/setu              # 获取1张随机图片
/setu 3            # 获取3张图片
/setu help         # 显示帮助信息
```

### 标签搜索 (用 # 号)

标签搜索支持AND和OR组合：

```bash
/setu #萝莉              # 搜索萝莉标签
/setu #白丝,黑丝         # OR搜索：白丝或黑丝
/setu #萝莉 #白丝        # AND搜索：萝莉且白丝
/setu 5 #风景 #唯美      # 获取5张风景且唯美的图
```

### 关键词搜索 (直接输入文本)

关键词会在标题、作者、标签中模糊匹配：

```bash
/setu 原神         # 搜索原神相关
/setu 初音未来      # 搜索初音未来
/setu 风景 5       # 搜索5张风景相关图片
```

### 长宽比筛选

```bash
/setu 横图           # 横图 (长宽比>1)
/setu 竖图           # 竖图 (长宽比<1)
/setu 方图           # 方图 (长宽比=1)
/setu gt1.7lt1.8     # 自定义：1.7 < 长宽比 < 1.8 (约16:9)
```

长宽比表达式格式：`(gt|gte|lt|lte|eq)数字`
- `gt`: 大于
- `gte`: 大于等于
- `lt`: 小于
- `lte`: 小于等于
- `eq`: 等于

### 排除AI作品

```bash
/setu noai         # 排除AI作品
/setu 5 noai       # 获取5张非AI作品
```

### 作者筛选

```bash
/setu uid:12345    # 获取指定UID作者的作品
```

### R18内容

```bash
/setu r18          # 获取R18图片（需配置允许）
/setu 3 r18        # 获取3张R18图片
```

### 组合使用

```bash
/setu 3 #萝莉,少女 横图              # 3张萝莉或少女的横图
/setu #白丝 #JK noai                # 白丝且JK，排除AI
/setu 原神 5 竖图                   # 5张原神相关竖图
/setu #风景 #唯美 gt1.5 noai        # 风景且唯美，长宽比>1.5，非AI
```

### 兼容旧格式

插件也支持旧的冒号格式：

```bash
/setu keyword:原神      # 等同于 /setu 原神
/setu tag:萝莉          # 等同于 /setu #萝莉
/setu kw:初音未来       # keyword的缩写
```

## 📊 图片规格说明

| 规格 | 说明 | 适用场景 |
|------|------|----------|
| `original` | 原图 | 最高质量，文件较大 |
| `regular` | 常规图 | **推荐**，质量好且文件适中 |
| `small` | 小图 | 流量受限场景 |
| `thumb` | 缩略图 | 快速预览 |
| `mini` | 迷你图 | 极小尺寸 |

## ⚠️ 注意事项

### R18内容

- 默认**关闭** R18 功能
- 启用前请确保：
  - ✅ 符合当地法律法规
  - ✅ 群组成员均为成年人
  - ✅ 已告知群成员此功能
  - ✅ 理解使用风险

### 使用限制

- API有调用限制，请理性使用
- 单次最多获取20张图片
- 请勿用于爬虫等滥用行为

### 版权说明

- 所有图片来自Pixiv，版权归原作者所有
- API仅储存作品基本信息，不提供图片代理或储存
- 请勿用于商业用途

## 🔧 故障排除

### 无法获取图片

1. 检查网络连接是否正常
2. 查看API是否可访问：https://api.lolicon.app/setu/v2
3. 检查日志文件中的错误信息
4. 确认配置文件格式正确

### 图片发送失败

1. 可能是图片URL失效，重试即可
2. 检查网络代理设置
3. 尝试更换图片规格（使用smaller size）

### 搜索无结果

1. 尝试更换关键词或标签
2. 减少筛选条件
3. 某些小众标签可能库中没有

## 📄 许可证

本插件采用 MIT 许可证开源。

## 🙏 鸣谢

- [Lolicon API](https://api.lolicon.app) - 提供图片数据服务
- [MaiBot](https://github.com/MaiM-with-u/MaiBot) - 优秀的QQ机器人框架
- 所有贡献图片的画师们

## 📮 反馈与支持

如遇到问题或有建议，欢迎通过以下方式反馈：

- 提交 [Issue](https://github.com/saberlights/lolicon-setu-plugin/issues)
- 发起 [Pull Request](https://github.com/saberlights/lolicon-setu-plugin/pulls)

## 📋 更新日志

### v2.1.0 (2025-11-09)

- ✨ 新增简短命令格式
  - 使用 `#标签` 代替 `tag:标签` (更简洁)
  - 直接输入文本作为关键词 (无需 `keyword:` 前缀)
- ✨ 新增 `/setu help` 命令显示帮助信息
- ✨ 支持多种帮助命令：`help`, `帮助`, `?`, `？`
- ✨ 新增 proxy 配置，可自定义图片反代服务器
- 🔄 保持向后兼容旧的冒号格式
- 📝 更新文档和使用示例
- 🐛 修复合并转发消息发送者显示问题

### v2.0.0 (2025-11-09)

- 🎉 重写插件，改用Lolicon API v2
- ✨ 新增标签AND/OR组合搜索
- ✨ 新增关键词模糊搜索
- ✨ 新增长宽比筛选功能
- ✨ 新增AI作品排除选项
- ✨ 支持合并转发格式
- 📝 全新的文档和使用说明

---

**享受使用，请合理使用本插件！** 🎉
