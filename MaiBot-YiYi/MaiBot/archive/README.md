# archive/

本目录用于存放**不参与日常运行**的根目录零散文件，避免与 `launch/`、`src/`、`config/` 混淆。

| 子目录 | 内容 |
|--------|------|
| `manual-scripts/` | 从项目根移入的临时/手工测试脚本（如 `test_intimacy_*.py`） |
| `generated/` | 运行产生的样例输出（如 TTS mp3、统计 html），可按需删除 |

需要跑其中脚本时：

```text
python archive/manual-scripts/某脚本.py
```

（请在项目根目录下执行，或先 `cd` 到本仓库 `MaiBot` 根目录。）
