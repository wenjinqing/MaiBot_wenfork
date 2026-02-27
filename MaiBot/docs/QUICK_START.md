# ⚡ 快速上手指南

> 这是针对初学者的快速上手指南。如果你想深入学习，请查看 [完整学习指南](./BEGINNER_GUIDE.md)

## 🎯 5 分钟快速开始

### 第一步：环境准备

```bash
# 1. 检查 Python 版本（需要 3.10+）
python --version

# 2. 克隆项目（如果还没有）
git clone https://github.com/MaiM-with-u/MaiBot.git
cd MaiBot

# 3. 创建虚拟环境
python -m venv venv

# 4. 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 5. 安装依赖
pip install -r requirements.txt
```

### 第二步：基本配置

```bash
# 1. 复制配置文件模板
cp template/bot_config_template.toml config/bot_config.toml
cp template/model_config_template.toml config/model_config.toml
cp template/template.env .env

# 2. 编辑配置文件（至少需要配置 LLM API Key）
# 编辑 config/model_config.toml，填入你的 OpenAI 或 Gemini API Key
```

### 第三步：运行

```bash
# 运行程序
python bot.py

# 首次运行会要求你同意协议，输入 "同意" 或 "confirmed"
```

## ✅ 检查清单

在开始学习之前，确认你已经完成：

- [ ] Python 3.10+ 已安装
- [ ] 项目已克隆到本地
- [ ] 虚拟环境已创建并激活
- [ ] 依赖已安装完成
- [ ] 配置文件已创建并配置
- [ ] 程序可以成功运行（至少到启动阶段）

## 📚 学习路径

### 第 1 天：了解项目
- [ ] 阅读 README.md
- [ ] 查看项目目录结构
- [ ] 运行程序，观察日志输出
- [ ] 阅读 `src/main.py` 了解启动流程

### 第 2-3 天：理解消息处理
- [ ] 阅读 `src/chat/message_receive/bot.py`
- [ ] 理解消息是如何接收和处理的
- [ ] 尝试添加日志输出，追踪消息流程

### 第 4-5 天：理解 LLM 调用
- [ ] 阅读 `src/llm_models/utils_model.py`
- [ ] 理解如何调用 AI 模型
- [ ] 尝试修改 prompt，观察回复变化

### 第 6-7 天：编写第一个插件
- [ ] 阅读插件开发文档
- [ ] 查看示例插件 `plugins/hello_world_plugin`
- [ ] 编写一个简单的命令插件

## 🆘 遇到问题？

1. **查看完整指南**：[BEGINNER_GUIDE.md](./BEGINNER_GUIDE.md)
2. **查看官方文档**：https://docs.mai-mai.org
3. **搜索 Issues**：https://github.com/MaiM-with-u/MaiBot/issues
4. **加入社区**：技术交流群 https://qm.qq.com/q/RzmCiRtHEW

## 🎓 推荐阅读顺序

1. [完整学习指南](./BEGINNER_GUIDE.md) - 深入理解项目
2. [优化建议](./OPTIMIZATION_SUGGESTIONS.md) - 了解如何优化代码
3. [官方文档](https://docs.mai-mai.org) - 完整的 API 参考

---

*祝你学习顺利！* 🚀





