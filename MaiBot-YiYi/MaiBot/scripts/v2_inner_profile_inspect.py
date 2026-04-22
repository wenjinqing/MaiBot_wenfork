#!/usr/bin/env python3
"""
列出 bot_config.toml 里 [inner] 与 chat_v2 相关的键，并对照「默认满载」估算额外 LLM / I/O 风险。

用法（在 MaiBot 根目录，已安装依赖）:
  python scripts/v2_inner_profile_inspect.py
  python scripts/v2_inner_profile_inspect.py config/bot_config.toml

不连接 QQ、不启动 bot；仅解析 TOML。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _parse_inner_loose(raw: str) -> dict[str, object]:
    """无第三方库时，从文本中粗解析 [inner] 表（仅支持 key = 标量）。"""
    m = re.search(r"^\[inner\]\s*\n(.*?)(?=^\[|\Z)", raw, re.MULTILINE | re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    out: dict[str, object] = {}
    for line in block.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if v.lower() in ("true", "false"):
            out[k] = v.lower() == "true"
        else:
            try:
                if "." in v:
                    out[k] = float(v)
                else:
                    out[k] = int(v)
            except ValueError:
                out[k] = v.strip('"').strip("'")
    return out


# 与 src.config.config.InnerConfig 保持同步（重构时若增删字段请一并更新）
V2_INNER_KEYS: list[tuple[str, str, str]] = [
    ("use_v2_architecture", "bool", "总开关：关则走心流 HeartF/Brain"),
    ("v2_enable_legacy_planner_no_reply_gate", "bool", "true：可能多 1 次旧 Planner/门闸 LLM（取决于 native）"),
    ("v2_use_native_planner_gate", "bool", "true：门闸用 v2_native（仍可能 1 次 LLM），通常比完整旧 plan 轻"),
    ("v2_run_legacy_planner_on_mention", "bool", "true：@/提及时仍跑 planner，多调用"),
    ("v2_execute_legacy_planner_wait_time", "bool", "true：执行 wait_time，延迟 + 行为变化"),
    ("v2_apply_legacy_planner_smooth_sleep", "bool", "true：planner 后补睡 planner_smooth，延迟"),
    ("v2_append_legacy_plan_style_to_system_prompt", "bool", "注入 plan_style 文本，token↑ 无额外 LLM"),
    ("v2_execute_legacy_planner_side_actions", "bool", "true：旧 planner 插件类动作，常触发完整旧 plan"),
    ("v2_inject_legacy_planner_summary_into_prompt", "bool", "true：多 planner 且注入摘要，token↑"),
    ("v2_use_replyer_aligned_persona", "bool", "true：对齐旧 Replyer 人设素材，子任务/检索可能很重"),
    ("v2_run_legacy_observe_side_tasks", "bool", "后台任务，不占主链路但占资源"),
    ("v2_run_legacy_reflect_side_tasks", "bool", "后台反思任务"),
    ("v2_use_legacy_prompt_message_scope", "bool", "决策/终局包进 prompt scope，行为对齐旧模板"),
    ("v2_log_full_unified_prompt", "bool", "true：INFO 分块打全量 prompt，磁盘 I/O 明显"),
    ("v2_anti_repeat_inject_recent_own_speech", "bool", "注入近期本人发言，token↑"),
    ("v2_anti_repeat_llm_rewrite", "bool", "true：相似度高时多 1 次改写 LLM"),
    ("v2_tool_execution_timeout_seconds", "float", "单工具 asyncio 超时下限 30s（UnifiedAgent 内 clamp）"),
    ("v2_inbound_message_dedup_ttl_seconds", "float", "0 关闭 message_id 去重"),
    ("v2_serial_process_per_stream", "bool", "true：同会话串行 process，延迟队列、少乱序"),
    ("v2_skip_text_when_only_unified_tts_success", "bool", "仅 TTS 成功时是否跳过终局文字"),
    ("v2_anti_repeat_recent_own_max_items", "int", "反读注入条数上限"),
    ("v2_anti_repeat_recent_own_max_chars_per_line", "int", "反读注入单行上限"),
    ("v2_anti_repeat_similarity_threshold", "float", "触发改写的相似度阈值"),
]


DEFAULTS_TRUE = {
    "use_v2_architecture",
    "v2_enable_legacy_planner_no_reply_gate",
    "v2_append_legacy_plan_style_to_system_prompt",
    "v2_use_replyer_aligned_persona",
    "v2_log_full_unified_prompt",
    "v2_anti_repeat_inject_recent_own_speech",
    "v2_anti_repeat_llm_rewrite",
    "v2_serial_process_per_stream",
    "v2_skip_text_when_only_unified_tts_success",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspect [inner] chat_v2 keys in bot_config.toml")
    ap.add_argument(
        "bot_config",
        nargs="?",
        default="config/bot_config.toml",
        help="Path to bot_config.toml",
    )
    args = ap.parse_args()
    path = Path(args.bot_config)
    if not path.is_file():
        print(f"找不到文件: {path.resolve()}", file=sys.stderr)
        return 2

    raw = path.read_text(encoding="utf-8")
    data: dict
    try:
        import tomllib as _tp  # py3.11+

        data = _tp.loads(raw)
    except ModuleNotFoundError:
        try:
            import toml as _tp  # 项目依赖 toml，兼容 py3.10

            data = _tp.loads(raw)
        except ImportError:
            data = {"inner": _parse_inner_loose(raw)}
    inner = data.get("inner")
    if not isinstance(inner, dict):
        print("未找到 [inner] 表或格式错误", file=sys.stderr)
        return 1

    print(f"文件: {path.resolve()}\n")
    print(f"{'key':<50} {'value':<14} note")
    print("-" * 120)

    for key, _typ, note in V2_INNER_KEYS:
        val = inner.get(key, "<未写，用代码默认>")
        disp = repr(val) if val != "<未写，用代码默认>" else val
        if len(disp) > 12:
            disp = disp[:11] + "…"
        print(f"{key:<50} {disp:<14} {note}")

    print("\n--- 粗粒度风险提示（基于当前文件显式值；未写的 bool 按代码默认）---\n")

    def g(name: str) -> object:
        if name not in inner:
            return "default"
        return inner[name]

    u = g("use_v2_architecture")
    if u is False or u == "false":
        print("当前 use_v2_architecture=false：未走 chat_v2，本表仅作对照。")
        return 0

    gate = g("v2_enable_legacy_planner_no_reply_gate")
    native = g("v2_use_native_planner_gate")
    inj = g("v2_inject_legacy_planner_summary_into_prompt")
    side = g("v2_execute_legacy_planner_side_actions")

    if gate == "default":
        gate = True
    if native == "default":
        native = False
    if inj == "default":
        inj = False
    if side == "default":
        side = False

    planner_llm = bool(gate or inj or side)
    print(
        f"前置规划类 LLM（门闸/旧 plan）: {'可能 1 次/轮或更多' if planner_llm else '关 gate 且未开 inject/side 时通常无'}"
    )

    persona = g("v2_use_replyer_aligned_persona")
    if persona == "default":
        persona = True
    print(f"旧 Replyer 人设对齐: {'开（多路素材/可能子模型）' if persona else '关'}")

    rw = g("v2_anti_repeat_llm_rewrite")
    if rw == "default":
        rw = True
    print(f"复读改写 LLM: {'开（最坏多 +1 次）' if rw else '关'}")

    logp = g("v2_log_full_unified_prompt")
    if logp == "default":
        logp = True
    print(f"全量 prompt INFO 日志: {'开（大 I/O）' if logp else '关'}")

    serial = g("v2_serial_process_per_stream")
    if serial == "default":
        serial = True
    print(f"同会话串行: {'开（排队延迟）' if serial else '关（吞吐↑、易连发）'}")

    missing = [k for k, _, _ in V2_INNER_KEYS if k not in inner]
    if missing:
        print(f"\n未在文件中显式写出（将用 src/config/config.py 默认值）的键: {len(missing)} 个")
        for k in missing[:12]:
            d = "true" if k in DEFAULTS_TRUE else "(见代码)"
            print(f"  - {k} 默认约 {d}")
        if len(missing) > 12:
            print("  ...")

    print(
        "\nchat_v2 [inner] 片段（复制 [inner] 到 config/bot_config.toml）:\n"
        "  template/bot_config_inner_v2_profile_natural.toml   # 真人感优先（推荐）\n"
        "  template/bot_config_inner_v2_profile_default.toml\n"
        "  template/bot_config_inner_v2_profile_minimal.toml\n"
        "  template/bot_config_inner_v2_profile_gate_only.toml"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
