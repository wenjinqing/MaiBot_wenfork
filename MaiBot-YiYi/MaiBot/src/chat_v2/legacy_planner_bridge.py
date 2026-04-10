"""
可选桥接：在 v2 主链路中复用旧 ActionPlanner / BrainPlanner。
默认全部关闭；use_v2_architecture = false 时整条旧心流/脑回路不变，便于回退。
"""

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

from src.common.logger import get_logger
from src.config.config import global_config
from src.common.data_models.info_data_model import ActionPlannerInfo
from src.chat.planner_actions.action_manager import ActionManager
from src.chat.planner_actions.action_modifier import ActionModifier
from src.chat.planner_actions.planner import ActionPlanner
from src.chat.brain_chat.brain_planner import BrainPlanner

if TYPE_CHECKING:
    from src.chat.message_receive.chat_stream import ChatStream

logger = get_logger("v2_legacy_planner_bridge")

_DEFAULT_PLANNER_REASON_MAX_CHARS = 280

_LEGACY_CLIENTS: Dict[str, Tuple[ActionManager, Union[ActionPlanner, BrainPlanner]]] = {}

_INTERNAL_ACTIONS = frozenset({"reply", "no_reply", "no_reply_until_call", "wait_time"})
_SILENCE_ACTIONS = frozenset({"no_reply", "no_reply_until_call"})


@dataclass
class LegacyPlannerV2Phase:
    """单次 legacy planner 阶段结果（与 UnifiedAgent 配合使用）"""

    planned_actions: List[ActionPlannerInfo]
    action_manager: ActionManager
    short_circuit_no_reply: bool
    set_no_reply_until_call: bool
    custom_actions: List[ActionPlannerInfo]


def _stream_is_group(chat_stream: "ChatStream") -> bool:
    try:
        return chat_stream.group_info is not None
    except Exception:
        return False


def _get_cached_clients(
    stream_id: str, is_group: bool
) -> Tuple[ActionManager, Union[ActionPlanner, BrainPlanner]]:
    cached = _LEGACY_CLIENTS.get(stream_id)
    if cached is not None:
        _, planner = cached
        ok_group = is_group and isinstance(planner, ActionPlanner)
        ok_private = not is_group and isinstance(planner, BrainPlanner)
        if ok_group or ok_private:
            return cached
    action_manager = ActionManager()
    planner: Union[ActionPlanner, BrainPlanner]
    if is_group:
        planner = ActionPlanner(stream_id, action_manager)
    else:
        planner = BrainPlanner(stream_id, action_manager)
    _LEGACY_CLIENTS[stream_id] = (action_manager, planner)
    return action_manager, planner


def legacy_planner_custom_actions(actions: List[ActionPlannerInfo]) -> List[ActionPlannerInfo]:
    """与旧 planner_adapter 一致：仅插件类 action。"""
    return [a for a in actions if a.action_type not in _INTERNAL_ACTIONS]


def format_legacy_planner_summary_for_prompt(
    actions: List[ActionPlannerInfo],
    max_reason_chars: int = _DEFAULT_PLANNER_REASON_MAX_CHARS,
) -> str:
    """
    将本轮旧 Planner 输出的动作与理由拼成短文本，供 v2 回复模型对齐「规划结论」。
    仅在非短路、且开启 v2_inject_legacy_planner_summary_into_prompt 时使用。
    """
    if not actions:
        return ""
    lines: List[str] = []
    cap = max(0, int(max_reason_chars))
    for a in actions:
        r = (a.reasoning or "").strip()
        if cap > 0 and len(r) > cap:
            r = r[: cap - 1] + "…"
        if r:
            lines.append(f"- {a.action_type}: {r}")
        else:
            lines.append(f"- {a.action_type}")
    return "**旧规划器本轮结论（供参考，最终回复与之协调即可）：**\n" + "\n".join(lines) + "\n"


async def run_legacy_planner_v2_phase(chat_stream: "ChatStream", message) -> Optional[LegacyPlannerV2Phase]:
    """
    在 v2 且开启门闸或插件执行时，跑一轮旧 modify_actions + plan。

    默认 @/提及时不调用（省 planner LLM）。若 inner.v2_run_legacy_planner_on_mention=true，则仍调用；
    群聊 ActionPlanner 会传 is_mentioned=True（简化提示词）。提及时永不触发沉默门闸短路。

    short_circuit_no_reply：开启 v2_enable_legacy_planner_no_reply_gate 且规划结果全部为沉默类动作、且非 @/提及时，
    调用方应跳过 v2 主 LLM 并返回 no_reply。

    custom_actions：非 reply/no_reply/no_reply_until_call/wait_time，供 v2_execute_legacy_planner_side_actions 执行。

    仅开启 v2_inject_legacy_planner_summary_into_prompt 时也会进入本阶段（多一次 planner LLM）。

    v2_apply_legacy_planner_smooth_sleep：plan 返回后按 chat.planner_smooth 补足 asyncio.sleep。
    """
    inner = global_config.inner
    if not getattr(inner, "use_v2_architecture", False):
        return None
    gate = getattr(inner, "v2_enable_legacy_planner_no_reply_gate", False)
    exec_plugins = getattr(inner, "v2_execute_legacy_planner_side_actions", False)
    inject_summary = getattr(inner, "v2_inject_legacy_planner_summary_into_prompt", False)
    if not gate and not exec_plugins and not inject_summary:
        return None

    use_native = getattr(inner, "v2_use_native_planner_gate", False)
    if use_native and not exec_plugins:
        from src.chat_v2.v2_native_planner_gate import run_v2_native_planner_gate

        return await run_v2_native_planner_gate(
            chat_stream, message, gate=gate, _inject_summary=inject_summary
        )
    if use_native and exec_plugins:
        logger.warning(
            "inner.v2_use_native_planner_gate 与 v2_execute_legacy_planner_side_actions 同时开启，"
            "本回合使用旧 ActionPlanner/BrainPlanner（需插件类动作规划）"
        )

    mentioned = bool(getattr(message, "is_mentioned", False) or getattr(message, "is_at", False))
    if mentioned and not getattr(inner, "v2_run_legacy_planner_on_mention", False):
        return None

    stream_id = chat_stream.stream_id
    is_group = _stream_is_group(chat_stream)
    action_manager, planner = _get_cached_clients(stream_id, is_group)
    modifier = ActionModifier(action_manager, stream_id)
    try:
        await modifier.modify_actions()
    except Exception as e:
        logger.warning(f"v2 legacy planner phase: modify_actions failed: {e}")
        return None

    available = action_manager.get_using_actions()
    loop_t = time.time()
    try:
        if is_group:
            assert isinstance(planner, ActionPlanner)
            actions = await planner.plan(
                available_actions=available,
                loop_start_time=loop_t,
                is_mentioned=bool(mentioned and getattr(inner, "v2_run_legacy_planner_on_mention", False)),
            )
        else:
            assert isinstance(planner, BrainPlanner)
            actions = await planner.plan(available_actions=available, loop_start_time=loop_t)
    except Exception as e:
        logger.warning(f"v2 legacy planner phase: plan failed: {e}")
        return None

    if getattr(inner, "v2_apply_legacy_planner_smooth_sleep", False):
        elapsed = time.time() - loop_t
        smooth = float(getattr(global_config.chat, "planner_smooth", 0) or 0)
        delay = max(0.0, smooth - elapsed)
        if delay > 0:
            await asyncio.sleep(delay)

    if not actions:
        return LegacyPlannerV2Phase(
            planned_actions=[],
            action_manager=action_manager,
            short_circuit_no_reply=False,
            set_no_reply_until_call=False,
            custom_actions=[],
        )

    types = [a.action_type for a in actions]
    all_silence = all(t in _SILENCE_ACTIONS for t in types)
    short_circuit = bool(gate and all_silence and not mentioned)
    set_until = any(a.action_type == "no_reply_until_call" for a in actions)
    custom = legacy_planner_custom_actions(actions)

    if short_circuit:
        logger.info(f"v2 legacy planner phase: short_circuit silence ({types})")
    else:
        logger.debug(f"v2 legacy planner phase: continue v2, actions={types}, custom={len(custom)}")

    return LegacyPlannerV2Phase(
        planned_actions=actions,
        action_manager=action_manager,
        short_circuit_no_reply=short_circuit,
        set_no_reply_until_call=set_until,
        custom_actions=custom,
    )


async def should_short_circuit_v2_with_planner_no_reply(chat_stream: "ChatStream", message) -> bool:
    """兼容旧调用点：等价于 run_legacy_planner_v2_phase(...).short_circuit_no_reply（仅 gate 开启时可能为 True）。"""
    phase = await run_legacy_planner_v2_phase(chat_stream, message)
    return phase is not None and phase.short_circuit_no_reply
