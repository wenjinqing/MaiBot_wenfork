# ✅ 知识库文件已复制完成

## 已完成

✅ 已成功将 `library` 目录下的 8 个知识库文件复制到 `data/openie/` 目录

## 📝 下一步操作

### 1. 配置 LLM API（必需）

导入知识库需要调用 LLM API 来生成 Embedding，请先配置：

1. **编辑配置文件**：
   ```
   config/model_config.toml
   ```

2. **配置 Embedding 模型**：
   - 找到 `[lpmm_knowledge]` 部分
   - 配置 Embedding 模型 API 和 API Key
   - **推荐使用**：硅基流动的 Pro/BAAI/bge-m3
   - 每百万 Token 费用约 0.7 元

3. **确保 API 有足够余额**：
   - 导入会消耗大量 Token
   - 请确保账户有足够余额

### 2. 运行导入脚本

配置好 API 后，运行导入脚本：

```bash
cd MaiBot
python scripts/import_openie.py
```

**重要提示**：
- ⚠️ 导入过程会消耗大量系统资源（CPU、内存）
- ⚠️ 导入可能需要较长时间（取决于知识库大小）
- ⚠️ 参考：8万条请求约 70 分钟

**导入过程**：
1. 脚本会提示你确认操作
2. 加载现有的 Embedding 库和知识图谱
3. 读取 `data/openie/` 目录下的所有 JSON 文件
4. 进行数据验证和去重
5. 生成 Embedding（最耗时）
6. 构建知识图谱（RAG）
7. 保存到文件

### 3. 启用知识库

导入完成后，在配置文件中启用知识库：

1. **编辑配置文件**：
   ```
   config/bot_config.toml
   ```

2. **启用 LPMM 知识库**：
   ```toml
   [lpmm_knowledge]
   enable = true  # 改为 true
   ```

3. **重启程序**：
   重启 MaiBot，知识库将自动加载。

## 📚 相关文档

- [知识库导入详细指南](./KNOWLEDGE_IMPORT_GUIDE.md) - 完整的导入教程
- [完整学习指南](./BEGINNER_GUIDE.md) - 初学者教程
- [项目结构说明](./PROJECT_STRUCTURE.md) - 了解项目结构

## ⚠️ 注意事项

1. **分批导入**（可选）：如果知识库文件较大，可以一次只导入一个文件
2. **查看日志**：导入过程中可以查看日志了解进度
3. **资源准备**：确保有足够的系统资源和 API 余额

## 🆘 遇到问题？

如果导入过程中遇到问题：

1. **查看日志**：检查 `logs/` 目录下的日志文件
2. **查看文档**：阅读 [知识库导入详细指南](./KNOWLEDGE_IMPORT_GUIDE.md)
3. **常见问题**：参考详细指南中的"常见问题"部分

---

*文件已复制完成，可以进行下一步导入操作了！*





