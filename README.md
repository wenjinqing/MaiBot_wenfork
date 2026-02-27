# 🤖 MaiBot 多机器人完全分离部署

基于 [MaiBot](https://github.com/MaiM-with-u/MaiBot) 的多机器人完全分离部署方案。

## 📖 项目简介

本项目实现了 MaiBot 的多机器人完全分离部署，每个机器人拥有：
- ✅ 独立的代码目录
- ✅ 独立的配置文件
- ✅ 独立的数据库
- ✅ 独立的缓存和日志
- ✅ 零冲突、零干扰

## �� 解决的问题

### 原始问题
- ❌ 两个机器人共享数据库，导致同时回复同一条消息
- ❌ 端口冲突，无法同时运行
- ❌ 配置互相干扰
- ❌ 日志混在一起，难以调试

### 解决方案
- ✅ 完全独立的目录结构
- ✅ 独立的数据库和缓存
- ✅ 独立的端口配置
- ✅ 独立的日志文件

## 📁 目录结构

```
MaiM/
├── MaiBot-JunJun/          # 君君机器人（完全独立）
│   ├── MaiBot/
│   │   ├── bot.py          # 启动文件
│   │   ├─��� .env.junjun     # 君君专用配置
│   │   ├── config/         # 配置文件
│   │   ├── data/           # 数据库和缓存
│   │   └── logs/           # 日志文件
│   └── MaiBot-Napcat-Adapter/
│
├── MaiBot-YiYi/            # 伊伊机器人（完全独立）
│   ├── MaiBot/
│   │   ├── bot.py          # 启动文件
│   │   ├── .env.yiyi       # 伊伊专用配置
│   │   ├── config/         # 配置文件
│   │   ├── data/           # 数据库和缓存
│   │   └── logs/           # 日志文件
│   └── MaiBot-Napcat-Adapter/
│
├── NapCat.Shell/           # 共享的 NapCat
│   └── config/
│
├── 启动君君.bat
├── 启动伊伊.bat
├── 完整启动流程.bat
├── 检查分离部署.bat
├── 数据分离.bat
└── docs/                   # 文档目录
    ├── 最终启动指南.md
    ├── 完全数据分离指南.md
    ├── NapCat错误排查指南.md
    └── 完成总结.md
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- NapCat
- 至少一个 AI 服务商的 API Key

### 安装步骤

1. **克隆项目**
   ```bash
   git clone <your-repo-url>
   cd MaiM
   ```

2. **配置君君**
   ```bash
   cd MaiBot-JunJun/MaiBot

   # 复制环境变量模板
   cp template/template.env .env.junjun

   # 编辑配置文件
   # 填入你的 API Keys 和 QQ 账号
   ```

3. **配置伊伊**
   ```bash
   cd MaiBot-YiYi/MaiBot

   # 复制环境变量模板
   cp template/template.env .env.yiyi

   # 编辑配置文件
   # 填入你的 API Keys 和 QQ 账号
   ```

4. **安装依赖**
   ```bash
   # 君君
   cd MaiBot-JunJun/MaiBot
   pip install -r requirements.txt

   # 伊伊
   cd MaiBot-YiYi/MaiBot
   pip install -r requirements.txt
   ```

5. **启动服务**
   ```bash
   # 方式一：使用启动脚本（推荐）
   双击：完整启动流程.bat

   # 方式二：手动启动
   双击：启动君君.bat
   双击：启动伊伊.bat
   ```

## 📊 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| 君君 WebUI | 8001 | Web 管理界面 |
| 君君消息服务器 | 8091 | maim_message 服务器 |
| 君君 NapCat 适配器 | 8095 | 适配器监听端口 |
| 伊伊消息服务器 | 8092 | maim_message 服务器 |
| 伊伊 NapCat 适配器 | 8097 | 适配器监听端口 |

## 📚 文档

- [最终启动指南](docs/最终启动指南.md) - 详细的启动步骤
- [完全数据分离指南](docs/完全数据分离指南.md) - 数据分离说明
- [NapCat错误排查指南](docs/NapCat错误排查指南.md) - 常见问题解决
- [完成总结](docs/完成总结.md) - 完整的配置总结

## ✨ 核心特性

### 1. 完全独立
- 每个机器人拥有独立的代码副本
- 独立的配置文件和环境变量
- 独立的数据库和缓存
- 独立的日志文件

### 2. 零冲突
- 不会同时回复同一条消息
- 不会读取对方的聊天记录
- 不会共享用户关系数据
- 端口完全分离

### 3. 易管理
- 可以分别启动/停止
- 可以分别更新
- 可以使用不同配置
- 一个出问题不影响另一个

## 🔧 配置说明

### 君君配置 (.env.junjun)
```bash
WEBUI_ENABLED=true      # 启用 WebUI
WEBUI_PORT=8001         # WebUI 端口
HOST=127.0.0.1
PORT=8091               # 消息服务器端口

# API Keys（必填）
DEEPSEEK_API_KEY=your_api_key_here
```

### 伊伊配置 (.env.yiyi)
```bash
WEBUI_ENABLED=false     # 禁用 WebUI（避免冲突）
HOST=127.0.0.1
PORT=8092               # 消息服务器端口

# API Keys（必填）
DEEPSEEK_API_KEY=your_api_key_here
```

## 🛠️ 故障排查

### 问题1: 端口被占用
```
ERROR: [Errno 10048] error while attempting to bind on address
```

**解决：**
1. 检查端口占用：`netstat -ano | findstr "8091 8092"`
2. 停止占用端口的进程
3. 或修改配置使用其他端口

### 问题2: 无法获取用户信息
```
Error: 无法获取用户信息
```

**解决：**
1. 重启 NapCat
2. 等待 1-2 分钟确保完全登录
3. 查看 [NapCat错误排查指南](docs/NapCat错误排查指南.md)

### 问题3: 数据库锁定
```
database is locked
```

**解决：**
1. 确保没有多个实例同时运行
2. 删除 `.db-shm` 和 `.db-wal` 文件
3. 重启机器人

## 📝 注意事项

### 敏感信息保护
- ⚠️ 不要将 `.env` 文件提交到 Git
- ⚠️ 不要将配置文件中的 API Keys 公开
- ⚠️ 不要将数据库文件提交到 Git

### 数据备份
建议定期备份：
- `data/MaiBot.db` - 数据库
- `config/` - 配置文件
- `.env.*` - 环境变量

### NapCat 使用
- 确保 NapCat 完全登录后再启动机器人
- 等待好友列表和群列表加载完成
- 建议使用快速登录功能

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 开源协议

本项目基于 [GPL-3.0](LICENSE) 协议开源。

## 🙏 致谢

- [MaiBot](https://github.com/MaiM-with-u/MaiBot) - 原始项目
- [NapCat](https://github.com/NapNeko/NapCatQQ) - QQ 协议实现

## 📮 联系方式

- Issues: [GitHub Issues](https://github.com/your-username/your-repo/issues)
- 原项目文档: [docs.mai-mai.org](https://docs.mai-mai.org)

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star 支持一下！**

Made with ❤️ by MaiBot Community

</div>
