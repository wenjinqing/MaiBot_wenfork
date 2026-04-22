"""
chat_v2 专用「门闸规划器」：语义与旧 ActionPlanner / BrainPlanner 对齐，使用同一套 Prompt 模板，
但不向模型注入插件类 Action（表情/TTS/细说等由 UnifiedAgent 主模型与工具处理），减少双轨决策冲突。

与 inner.v2_execute_legacy_planner_side_actions 同时开启时，bridge 会回退旧 planner（需插件类 plan）。
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Deque, Dict, List, Optional, Tuple

import src.chat.brain_chat.brain_planner  # noqa: F401  # 注册 brain_planner_prompt
import src.chat.planner_actions.planner  # noqa: F401  # 注册 planner_prompt*
from src.chat.planner_actions.planner import ActionPlanner
from src.chat.utils.chat_message_builder import (
    build_readable_actions,
    build_readable_messages_with_id,
    get_actions_by_timestamp_with_chat,
    get_raw_msg_before_timestamp_with_chat,
    history_cutoff_for_inbound_message,
)
from src.chat.utils.prompt_builder import global_prompt_manager
from src.chat.utils.utils import get_chat_type_and_target_info
from src.common.data_models.info_data_model import ActionPlannerInfo
from src.common.logger import get_logger
from src.config.config import global_config, model_config
from src.llm_models.utils_model import LLMRequest
from src.chat_v2.legacy_planner_bridge import (
    LegacyPlannerV2Phase,
    legacy_planner_custom_actions,
)

if TYPE_CHECKING:
    from src.chat.message_receive.chat_stream import ChatStream

logger = get_logger("v2_native_planner_gate")

# 不向模型展示插件 Action，避免与 v2 主 LLM 的工具列表重复决策
_NATIVE_GATE_ACTION_OPTIONS = (
    "\n（说明：表情包、TTS、联网搜索等插件能力由后续「主对话模型 + 工具」处理；"
    "本步仅决定 reply / no_reply / no_reply_until_call，勿输出其它 action 名。）\n"
)

_SILENCE_ACTIONS = frozenset({"no_reply", "no_reply_until_call"})


@dataclass
class _StreamGateState:
    last_obs_time_mark: float = 0.0
    # 与 ActionPlanner.plan_log 类似：保留近期门闸结论，供下一轮「历史动作记录」
    plan_records: Deque[Tuple[str, float, List[str]]] = field(default_factory=lambda: deque(maxlen=20))


_GATE_STATE: Dict[str, _StreamGateState] = {}


def _state(stream_id: str) -> _StreamGateState:
    if stream_id not in _GATE_STATE:
        _GATE_STATE[stream_id] = _StreamGateState()
    return _GATE_STATE[stream_id]


def _gate_plan_log_str(stream_id: str, max_action_records: int = 2) -> str:
    st = _state(stream_id)
    lines: List[str] = []
    for reasoning, ts, types in list(st.plan_records)[-max_action_records:]:
        time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        lines.append(f"{time_str}:{reasoning}")
    return "\n".join(lines)


def _gate_has_consecutive_no_reply(stream_id: str, min_count: int = 3) -> bool:
    st = _state(stream_id)
    n = 0
    for _r, _t, types in reversed(st.plan_records):
        if types and all(t == "no_reply" for t in types):
            n += 1
            if n >= min_count:
                return True
        else:
            break
    return False


def _append_gate_record(stream_id: str, reasoning: str, actions: List[ActionPlannerInfo]) -> None:
    st = _state(stream_id)
    types = [a.action_type for a in actions]
    st.plan_records.append((reasoning.strip() or "(无理由)", time.time(), types))


def _parse_planner(chat_id: str) -> ActionPlanner:
    """复用 ActionPlanner 的 JSON 抽取与 _parse_single_action（不调用其 plan）。"""
    from src.chat.planner_actions.action_manager import ActionManager

    return ActionPlanner(chat_id, ActionManager())


async def run_v2_native_planner_gate(
    chat_stream: "ChatStream",
    message,
    *,
    gate: bool,
    _inject_summary: bool = False,
) -> Optional[LegacyPlannerV2Phase]:
    """
    执行 v2 门闸规划（单轮）。返回值与 LegacyPlannerV2Phase 一致，供 UnifiedAgent 短路逻辑复用。
    """
    inner = global_config.inner
    stream_id = chat_stream.stream_id
    is_group = bool(getattr(chat_stream, "group_info", None))

    mentioned = bool(getattr(message, "is_mentioned", False) or getattr(message, "is_at", False))
    if mentioned and not getattr(inner, "v2_run_legacy_planner_on_mention", False):
        return None

    st = _state(stream_id)
    loop_t = time.time()

    _cut = history_cutoff_for_inbound_message(message)
    message_list_before_now = get_raw_msg_before_timestamp_with_chat(
        chat_id=stream_id,
        timestamp=_cut,
        limit=int(global_config.chat.max_context_size * 0.6),
        filter_no_read_command=True,
    )
    message_id_list: List[Tuple[str, Any]] = []
    chat_content_block, message_id_list = build_readable_messages_with_id(
        messages=message_list_before_now,
        timestamp_mode="normal_no_YMD",
        read_mark=st.last_obs_time_mark,
        truncate=True,
        show_actions=True,
    )
    st.last_obs_time_mark = time.time()

    moderation_prompt_block = "请不要输出违法违规内容，不要输出色情，暴力，政治相关内容，如有敏感内容，请规避。"
    time_block = f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    bot_name = global_config.bot.nickname
    bot_nickname = (
        f",也有人叫你{','.join(global_config.bot.alias_names)}" if global_config.bot.alias_names else ""
    )
    name_block = f"你的名字是{bot_name}{bot_nickname}，请注意哪些是你自己的发言。"
    interest = global_config.personality.interest

    ap = _parse_planner(stream_id)
    empty_avail: Dict = {}
    filtered_list: List = []

    try:
        if is_group:
            chat_context_description = "你现在正在一个群聊中"
            planner_nickname = str(global_config.bot.nickname or "")
            planner_alias_names = (
                "、".join(global_config.bot.alias_names) if global_config.bot.alias_names else "无其他常用称呼"
            )
            is_mentioned_flow = bool(mentioned and getattr(inner, "v2_run_legacy_planner_on_mention", False))
            actions_before_now_block = _gate_plan_log_str(stream_id)

            if is_mentioned_flow:
                tmpl = await global_prompt_manager.get_prompt_async("planner_prompt_mentioned")
                prompt = tmpl.format(
                    time_block=time_block,
                    chat_context_description=chat_context_description,
                    chat_content_block=chat_content_block,
                    actions_before_now_block=actions_before_now_block,
                    action_options_text=_NATIVE_GATE_ACTION_OPTIONS,
                    moderation_prompt=moderation_prompt_block,
                    name_block=name_block,
                    interest=interest,
                    plan_style=global_config.personality.plan_style,
                    nickname=planner_nickname,
                    alias_names=planner_alias_names,
                )
            else:
                no_reply_until_call_block = ""
                if _gate_has_consecutive_no_reply(stream_id, min_count=3):
                    no_reply_until_call_block = """no_reply_until_call
动作描述：
保持沉默，直到有人直接叫你的名字
当前话题不感兴趣时使用，或有人不喜欢你的发言时使用
当你频繁选择no_reply时使用，表示话题暂时与你无关
{{"action":"no_reply_until_call"}}
"""
                tmpl = await global_prompt_manager.get_prompt_async("planner_prompt")
                prompt = tmpl.format(
                    time_block=time_block,
                    chat_context_description=chat_context_description,
                    chat_content_block=chat_content_block,
                    actions_before_now_block=actions_before_now_block,
                    action_options_text=_NATIVE_GATE_ACTION_OPTIONS,
                    no_reply_until_call_block=no_reply_until_call_block,
                    moderation_prompt=moderation_prompt_block,
                    name_block=name_block,
                    interest=interest,
                    plan_style=global_config.personality.plan_style,
                    nickname=planner_nickname,
                    alias_names=planner_alias_names,
                )
        else:
            _, chat_target_info = get_chat_type_and_target_info(stream_id)
            if chat_target_info:
                chat_context_description = (
                    f"你正在和 {chat_target_info.person_name or chat_target_info.user_nickname or '对方'} 聊天中"
                )
            else:
                chat_context_description = "你正在进行一对一私聊"

            actions_before = get_actions_by_timestamp_with_chat(
                chat_id=stream_id,
                timestamp_start=time.time() - 600,
                timestamp_end=time.time(),
                limit=6,
            )
            actions_before_now_block = build_readable_actions(actions=actions_before)
            if actions_before_now_block:
                actions_before_now_block = f"你刚刚选择并执行过的action是：\n{actions_before_now_block}"
            else:
                actions_before_now_block = ""

            tmpl = await global_prompt_manager.get_prompt_async("brain_planner_prompt")
            prompt = tmpl.format(
                time_block=time_block,
                chat_context_description=chat_context_description,
                chat_content_block=chat_content_block,
                actions_before_now_block=actions_before_now_block,
                action_options_text=_NATIVE_GATE_ACTION_OPTIONS,
                moderation_prompt=moderation_prompt_block,
                name_block=name_block,
                interest=interest,
                plan_style=global_config.personality.private_plan_style,
            )

        llm_req = LLMRequest(
            model_set=model_config.model_task_config.planner,
            request_type="v2_native_planner_gate",
        )
        llm_content, _meta = await llm_req.generate_response_async(prompt=prompt)

        if global_config.debug.show_planner_prompt:
            logger.info(f"[{stream_id}] v2 门闸规划原始提示词: \n{prompt}")
            logger.info(f"[{stream_id}] v2 门闸规划原始响应: \n{llm_content}")
        else:
            logger.debug(f"[{stream_id}] v2 门闸规划已调用 planner 模型")

        actions: List[ActionPlannerInfo] = []
        extracted_reasoning = ""
        if llm_content:
            json_objects, extracted_reasoning = ap._extract_json_from_markdown(llm_content)
            extracted_reasoning = ap._replace_message_ids_with_text(extracted_reasoning, message_id_list) or ""
            if json_objects:
                for json_obj in json_objects:
                    actions.extend(
                        ap._parse_single_action(
                            json_obj,
                            message_id_list,
                            filtered_list,
                            extracted_reasoning,
                        )
                    )
            else:
                actions = ap._create_no_reply("v2 门闸：模型未返回可用 JSON", empty_avail)
        else:
            actions = ap._create_no_reply("v2 门闸：无模型输出", empty_avail)

        for a in actions:
            a.action_data = a.action_data or {}
            a.action_data["loop_start_time"] = loop_t
            a.available_actions = empty_avail

        reasoning_line = extracted_reasoning or "v2_native_gate"
        _append_gate_record(stream_id, reasoning_line, actions)
        head = reasoning_line[:120] + ("…" if len(reasoning_line) > 120 else "")
        logger.info(f"[{stream_id}] v2 门闸规划: {head} | 动作: {[x.action_type for x in actions]}")

    except Exception as e:
        logger.warning(f"v2 门闸规划失败: {e}", exc_info=True)
        from src.chat.planner_actions.action_manager import ActionManager

        am = ActionManager()
        return LegacyPlannerV2Phase(
            planned_actions=[
                ActionPlannerInfo(
                    action_type="no_reply",
                    reasoning=f"v2 门闸异常: {e}",
                    action_data={},
                    action_message=None,
                    available_actions={},
                )
            ],
            action_manager=am,
            short_circuit_no_reply=bool(gate and not mentioned),
            set_no_reply_until_call=False,
            custom_actions=[],
        )

    if getattr(inner, "v2_apply_legacy_planner_smooth_sleep", False):
        elapsed = time.time() - loop_t
        smooth = float(getattr(global_config.chat, "planner_smooth", 0) or 0)
        delay = max(0.0, smooth - elapsed)
        if delay > 0:
            await asyncio.sleep(delay)

    from src.chat.planner_actions.action_manager import ActionManager

    action_manager = ActionManager()
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
        logger.info(f"v2 native planner gate: short_circuit silence ({types})")
    else:
        logger.debug(f"v2 native planner gate: continue v2, actions={types}, custom={len(custom)}")

    return LegacyPlannerV2Phase(
        planned_actions=actions,
        action_manager=action_manager,
        short_circuit_no_reply=short_circuit,
        set_no_reply_until_call=set_until,
        custom_actions=custom,
    )
