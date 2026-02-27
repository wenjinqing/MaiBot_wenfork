# 📚 知识库导入指南

本指南将帮助你导入 `library` 目录下的知识库文件到项目中。

## 📋 目录

1. [知识库文件格式](#知识库文件格式)
2. [快速导入步骤](#快速导入步骤)
3. [详细导入流程](#详细导入流程)
4. [常见问题](#常见问题)

---

## 📄 知识库文件格式

知识库文件需要使用 **OpenIE 格式**的 JSON 文件，文件命名应为 `*-openie.json`。

### OpenIE 格式说明

```json
{
    "docs": [
        {
            "idx": "文档的唯一标识符（通常是文本的SHA256哈希值）",
            "passage": "文档的原始文本",
            "extracted_entities": ["实体1", "实体2", ...],
            "extracted_triples": [
                ["主语", "谓语", "宾语"],
                ...
            ]
        },
        ...
    ],
    "avg_ent_chars": "实体平均字符数",
    "avg_ent_words": "实体平均词数"
}
```

---

## 🚀 快速导入步骤

### 方法一：使用自动导入脚本（推荐）

1. **运行导入脚本**：
   ```bash
   cd MaiBot
   python scripts/import_library.py
   ```

2. **脚本会自动**：
   - 查找 `library` 目录
   - 将所有 `*-openie.json` 文件复制到 `data/openie/` 目录
   - 提示下一步操作

3. **运行知识库导入**：
   ```bash
   python scripts/import_openie.py
   ```

### 方法二：手动复制文件

1. **复制文件到项目目录**：
   ```bash
   # Windows
   copy ..\library\*-openie.json data\openie\
   
   # Linux/Mac
   cp ../library/*-openie.json data/openie/
   ```

2. **确保目录存在**：
   ```bash
   # 如果 data/openie 目录不存在，先创建
   mkdir -p data/openie
   ```

3. **运行导入脚本**：
   ```bash
   python scripts/import_openie.py
   ```

---

## 📖 详细导入流程

### 第一步：准备知识库文件

确保你的 `library` 目录下有符合格式的 OpenIE JSON 文件：

```
library/
├── 麦麦的自我认知知识库-openie.json
├── fgo第一部剧情文本-openie.json
├── 贴吧热梗大全-openie.json
└── ...
```

### 第二步：复制文件到项目目录

知识库文件需要放在 `MaiBot/data/openie/` 目录下。

**使用自动脚本（推荐）**：
```bash
python scripts/import_library.py
```

**或手动复制**：
- Windows PowerShell:
  ```powershell
  Copy-Item ..\library\*-openie.json .\data\openie\
  ```

- Linux/Mac:
  ```bash
  cp ../library/*-openie.json data/openie/
  ```

### 第三步：配置 LLM API

导入知识库需要调用 LLM API 来生成 Embedding，因此需要先配置模型 API。

1. **编辑配置文件**：
   ```bash
   # 编辑模型配置文件
   config/model_config.toml
   ```

2. **配置 Embedding 模型**：
   在配置文件中找到 `[lpmm_knowledge]` 部分，配置：
   - Embedding 模型 API
   - API Key
   - 推荐使用：硅基流动的 Pro/BAAI/bge-m3

3. **确保 API 有足够的余额**：
   - 导入会消耗大量 Token
   - 每百万 Token 费用约 0.7 元

### 第四步：运行导入脚本

```bash
python scripts/import_openie.py
```

**导入过程说明**：
1. 脚本会提示你确认操作（因为会消耗大量资源）
2. 加载现有的 Embedding 库和知识图谱（如果有）
3. 读取 `data/openie/` 目录下的所有 JSON 文件
4. 进行数据验证和去重
5. 生成 Embedding（这一步最耗时）
6. 构建知识图谱（RAG）
7. 保存到文件

**预计时间**：
- 取决于知识库大小
- 参考：8万条请求约 70 分钟（本地模型）
- 网络允许的情况下可能更快

**资源消耗**：
- CPU: 10700K 几乎跑满，14900HX 占用 80%
- 内存: 峰值约 3GB

### 第五步：启用知识库

导入完成后，需要在配置文件中启用知识库：

1. **编辑配置文件**：
   ```bash
   config/bot_config.toml
   ```

2. **启用 LPMM 知识库**：
   ```toml
   [lpmm_knowledge]
   enable = true  # 改为 true
   ```

3. **重启程序**：
   重启 MaiBot，知识库将自动加载。

---

## ❓ 常见问题

### Q1: 找不到 library 目录

**问题**：运行 `import_library.py` 时提示找不到 library 目录

**解决方案**：
1. 检查 library 目录位置：
   - 应该在 `MaiM-with-u/library/`
   - 或在 `MaiBot/library/`
2. 手动指定路径：
   - 脚本会提示你手动输入路径
3. 手动复制文件：
   - 参考"方法二：手动复制文件"

### Q2: 导入时提示 API 错误

**问题**：导入过程中提示 API 调用失败

**可能原因**：
1. API Key 未配置或错误
2. API 余额不足
3. 网络连接问题
4. API 限流

**解决方案**：
1. 检查 `config/model_config.toml` 中的 API 配置
2. 确认 API 账户有足够余额
3. 检查网络连接
4. 等待一段时间后重试（如果是因为限流）

### Q3: 导入时内存不足

**问题**：导入过程中程序崩溃或提示内存不足

**解决方案**：
1. 分批导入：一次只导入一个知识库文件
2. 增加虚拟内存（Windows）或 swap 空间（Linux）
3. 关闭其他占用内存的程序
4. 在配置更好的电脑上运行

### Q4: 导入后知识库不工作

**问题**：导入完成但机器人无法使用知识库

**检查清单**：
- [ ] 确认 `bot_config.toml` 中 `lpmm_knowledge.enable = true`
- [ ] 确认已重启程序
- [ ] 查看日志是否有错误信息
- [ ] 确认 Embedding 模型配置正确

### Q5: 数据格式错误

**问题**：导入时提示数据格式错误

**解决方案**：
1. 检查 JSON 文件格式是否正确
2. 确保每个文档都有必需的字段：
   - `idx`: 文档 ID（通常是哈希值）
   - `passage`: 原始文本
   - `extracted_entities`: 实体列表
   - `extracted_triples`: 三元组列表
3. 检查是否有非法字符或格式错误

### Q6: 如何查看已导入的知识库

**查看方法**：
1. **查看文件**：
   - Embedding 数据：`data/embedding/`
   - 知识图谱：`data/kg/`

2. **查看日志**：
   - 启动时会显示知识库信息
   - 查看节点数量和边数量

3. **使用 WebUI**：
   - 如果启用了 WebUI，可以通过界面查看

---

## 📝 知识库文件列表

当前 `library` 目录下的知识库文件：

- `麦麦的自我认知知识库-openie.json` - 麦麦的自我认知信息
- `fgo第一部剧情文本-openie.json` - FGO 游戏剧情
- `贴吧热梗大全-openie.json` - 贴吧热梗知识
- `三角洲行动-openie.json` - 游戏相关知识
- `三角洲行动黑话及梗-openie.json` - 游戏黑话
- `中国近现代史加刷机知识-openie.json` - 历史知识
- `梗指南-人工修改-建议自行检查11-21-23-32-openie.json` - 梗知识库
- `mygo讽刺解构木柜子-openie.json` - 相关内容

---

## 🔧 高级操作

### 分批导入知识库

如果知识库文件较大，可以分批导入：

1. **一次只复制一个文件到 `data/openie/`**：
   ```bash
   # 只复制一个文件
   cp ../library/麦麦的自我认知知识库-openie.json data/openie/
   ```

2. **运行导入脚本**：
   ```bash
   python scripts/import_openie.py
   ```

3. **重复上述步骤导入其他文件**

### 查看导入进度

导入过程会在日志中显示详细进度，你也可以：

1. **查看日志文件**：
   ```bash
   logs/app_*.log.jsonl
   ```

2. **实时查看日志**：
   ```bash
   tail -f logs/app_*.log.jsonl
   ```

### 清理和重新导入

如果需要重新导入：

1. **备份现有数据**（可选）：
   ```bash
   cp -r data/embedding data/embedding_backup
   cp -r data/kg data/kg_backup
   ```

2. **清理数据目录**：
   ```bash
   rm -rf data/embedding/*
   rm -rf data/kg/*
   ```

3. **重新导入**

---

## 📚 相关文档

- [完整学习指南](./BEGINNER_GUIDE.md)
- [项目结构说明](./PROJECT_STRUCTURE.md)
- [优化建议](./OPTIMIZATION_SUGGESTIONS.md)

---

## 💡 提示

1. **首次导入建议**：先导入一个较小的知识库测试
2. **资源准备**：确保有足够的 API 余额和系统资源
3. **耐心等待**：导入过程可能需要较长时间，请耐心等待
4. **查看日志**：遇到问题先查看日志文件了解详细错误信息

---

*最后更新：2025-01-28*
*如有问题，请查看日志或提交 Issue*





