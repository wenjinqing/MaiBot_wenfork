# 项目文档整理说明

## 整理日期
2025-12-01

## 整理目标
将所有 `.md` 文档文件从代码目录中分离出来，统一放到 `docs/` 子目录中，以保持代码目录的整洁。

## 整理规则

### 1. 保留在主目录的文件
- **README.md** - 项目主 README 文件（保留在主目录，但更新了文档链接）
- **changelogs/** - 更新日志目录（标准位置，保持不变）
- **docs-src/** - 文档源码目录（保持不变）

### 2. 移动到 docs/ 的文件
- 所有其他 `.md` 文件都移动到对应目录的 `docs/` 子目录中

## 已整理的目录

### MaiBot 根目录
- **docs/** - 包含以下文档：
  - BEGINNER_GUIDE.md - 新手入门指南
  - CODE_OF_CONDUCT.md - 行为准则
  - DEBUGGER_FIX.md - 调试器修复说明
  - EULA.md - 最终用户许可协议
  - KNOWLEDGE_IMPORT_GUIDE.md - 知识库导入指南
  - KNOWLEDGE_IMPORT_STEPS.md - 知识库导入步骤
  - OPTIMIZATION_SUGGESTIONS.md - 优化建议
  - PRIVACY.md - 隐私政策
  - PROJECT_STRUCTURE.md - 项目结构说明
  - QUICK_START.md - 快速开始指南
  - README.md - 文档索引

### MaiBot-Napcat-Adapter
- **docs/** - 包含以下文档：
  - POKE_FIX.md - 戳一戳功能问题修复说明
  - command_args.md - 命令参数文档
  - notify_args.md - 通知参数文档
  - README.md - 文档索引

### MaiBot/src 子目录
- **src/common/data_models/docs/** - 数据模型文档
- **src/memory_system/retrieval_tools/docs/** - 记忆检索工具文档
- **src/plugin_system/core/docs/** - 插件系统核心文档

### 插件目录
所有插件都已整理，文档统一放在 `docs/` 目录：

#### MaiBot/plugins/
- **acpoke_plugin/docs/** - 戳一戳插件文档
- **detailed_explanation/docs/** - 详细解释插件文档
- **lolicon_setu_plugin/docs/** - 色图插件文档
- **music_plugin/docs/** - 音乐插件文档（13个文档文件）

#### mod/
- **acpoke_plugin/docs/** - 戳一戳插件文档
- **lolicon-setu-plugin/docs/** - 色图插件文档
- **MaiBot-DetailedExplanation-Plugin/** - 详细解释插件
- **music_plugin/** - 音乐插件

## 目录结构示例

整理后的典型目录结构：

```
project_name/
├── README.md          # 主 README（保留）
├── plugin.py          # 代码文件
├── config.toml        # 配置文件
├── docs/              # 文档目录
│   ├── README.md      # 文档索引
│   └── *.md           # 其他文档
└── modules/           # 代码模块
```

## 链接更新

已更新以下文件中的文档链接：
- `MaiBot/README.md` - 更新了 EULA.md 和 PRIVACY.md 的链接路径

## 注意事项

1. **changelogs/** 目录保持不变 - 这是标准的更新日志位置
2. **docs-src/** 目录保持不变 - 这是文档源码目录
3. 所有主 README.md 文件都保留在原位置，但添加了指向 docs 目录的说明
4. 每个 docs 目录都创建了 README.md 作为文档索引

## 后续维护

- 新增文档应直接放在对应目录的 `docs/` 子目录中
- 保持主目录只包含代码、配置和主 README
- 定期更新 docs/README.md 索引文件

## 优势

1. **代码目录更整洁** - 主目录只包含必要的代码和配置文件
2. **文档集中管理** - 所有文档都在统一的 docs 目录中
3. **易于查找** - 通过 docs/README.md 可以快速找到相关文档
4. **结构统一** - 所有插件和模块使用相同的文档组织方式

