"""旧 Replyer：在 execute_from_chat_message 前可选一次轻量 LLM，判断是否值得走工具链路。"""

from __future__ import annotations

from src.common.logger import get_logger
from src.config.config import global_config, model_config
from src.plugin_system.apis import llm_api

logger = get_logger("replyer_tool_precheck")


def _parse_need_tool_response(text: str) -> bool:
    """解析预判断模型输出：要工具 True，否则 False；解析失败时 True（与旧行为一致，避免漏工具）。"""
    t = (text or "").strip()
    if not t:
        return True
    head = t[:6].lower()
    if head.startswith("否") or head.startswith("不") or head.startswith("no"):
        return False
    if head.startswith("是") or head.startswith("要") or head.startswith("需") or head.startswith("yes"):
        return True
    if "不需要" in t[:12] or "不用工具" in t[:20] or "无需" in t[:8]:
        return False
    if "需要" in t[:20] and "不需要" not in t[:20]:
        return True
    return True


async def should_run_replyer_tools(*, target: str, chat_history: str) -> bool:
    """若未开启配置则恒为 True；否则用小模型做一次「是否需要工具」判断。"""
    tool_cfg = global_config.tool
    if not getattr(tool_cfg, "replyer_tool_precheck_with_llm", False):
        return True

    n = int(getattr(tool_cfg, "replyer_tool_precheck_history_chars", 500) or 500)
    n = max(200, min(n, 8000))
    tail = (chat_history or "")[-n:] if chat_history else ""
    tgt = (target or "").strip() or "（空）"

    prompt = (
        "你是低成本路由分类器。根据「用户最新消息」判断：是否明显依赖联网搜索、实时资讯、"
        "或外部工具才能好好回答（例如：新闻/政策真假、天气股价、具体可查的知识点、"
        "明确的「帮我搜一下」等）。\n"
        "普通闲聊、斗图接梗、恋爱打趣、纯情绪回应、角色扮演、无需查证的事实聊天 → 不需要工具。\n\n"
        f"【最近上下文节选】\n{tail}\n\n"
        f"【用户最新消息】\n{tgt}\n\n"
        "只输出一个字：是 或 否。不要输出其它任何文字。"
    )

    task = model_config.model_task_config.utils_small
    ok, text, _reasoning, model_name = await llm_api.generate_with_model(
        prompt,
        model_config=task,
        request_type="replyer.tool_precheck",
        temperature=0.05,
        max_tokens=12,
    )
    if not ok:
        logger.warning(f"replyer 工具预判断 LLM 失败，回退为执行工具: {text[:120]!r}")
        return True

    need = _parse_need_tool_response(text)
    logger.info(
        f"replyer 工具预判断 model={model_name} need_tool={need} raw={text.strip()[:40]!r}"
    )
    return need
