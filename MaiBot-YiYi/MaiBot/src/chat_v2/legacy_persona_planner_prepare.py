"""
v2 专用统一入口：旧架构「完整人设素材」+「动作规划」（群聊 ActionPlanner / 私聊 BrainPlanner）。

与 heart_flow 旧链路同源：replyer 侧人设块、planner 侧 modify_actions + plan。
配置仍由 global_config.inner 各 v2_* 开关控制（人设 v2_use_replyer_aligned_persona；
规划 v2_enable_legacy_planner_no_reply_gate / v2_use_native_planner_gate（替代旧 plan，不枚举插件 Action）/
v2_execute_legacy_planner_side_actions / v2_inject_legacy_planner_summary_into_prompt /
v2_run_legacy_planner_on_mention / v2_execute_legacy_planner_wait_time / v2_apply_legacy_planner_smooth_sleep）。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

from src.common.logger import get_logger
from src.config.config import global_config
from src.chat.utils.chat_message_builder import (
    build_readable_messages,
    get_raw_msg_before_timestamp_with_chat,
    history_cutoff_for_inbound_message,
    replace_user_references,
)
from src.chat_v2.legacy_planner_bridge import (
    LegacyPlannerV2Phase,
    format_legacy_planner_summary_for_prompt,
    run_legacy_planner_v2_phase,
)

if TYPE_CHECKING:
    from src.chat.message_receive.chat_stream import ChatStream


@dataclass
class LegacyV2AlignmentBundle:
    """单轮 v2 在构建 AgentContext 之前可拿到的旧对齐结果。"""

    persona_meta: Dict[str, Any]
    planner_phase: Optional[LegacyPlannerV2Phase]
    legacy_planner_summary_text: Optional[str]


async def fill_replyer_aligned_persona_metadata(
    chat_stream: "ChatStream",
    message,
    metadata: Dict[str, Any],
    *,
    log: Any = None,
) -> None:
    """
    与旧 DefaultReplyer / PrivateReplyer 对齐的人设素材，写入传入的 metadata 字典。
    键与 UnifiedChatAgent._build_system_prompt 约定一致。
    """
    log = log or get_logger("v2_legacy_align")
    try:
        from src.chat.replyer.replyer_manager import replyer_manager
        from src.jargon.jargon_explainer import explain_jargon_in_context

        replyer = replyer_manager.get_replyer(chat_stream, request_type="unified_agent.persona")
        if replyer is None:
            return

        chat_id = chat_stream.stream_id
        platform = chat_stream.platform
        target_raw = message.processed_plain_text or message.display_message or ""
        target = replace_user_references(target_raw, platform, replace_bot_name=True)

        message_list_short = get_raw_msg_before_timestamp_with_chat(
            chat_id=chat_id,
            timestamp=history_cutoff_for_inbound_message(message),
            limit=int(global_config.chat.max_context_size * 0.33),
            filter_no_read_command=True,
        )
        chat_talking_prompt_short = build_readable_messages(
            message_list_short,
            replace_bot_name=True,
            timestamp_mode="relative",
            read_mark=0.0,
            show_actions=True,
        )

        try:
            ui = getattr(message, "message_info", None)
            uui = getattr(ui, "user_info", None) if ui is not None else None
            sender_name = (
                (getattr(uui, "user_nickname", None) or getattr(uui, "user_id", None) or "用户")
                if uui is not None
                else "用户"
            )
        except Exception:
            sender_name = "用户"

        identity_coro = replyer.build_personality_prompt()
        kw_coro = replyer.build_keywords_reaction_prompt(target if target else None)
        expr_coro = replyer.build_expression_habits(chat_talking_prompt_short, target, "")
        jargon_coro = explain_jargon_in_context(chat_id, message_list_short, chat_talking_prompt_short)
        knowledge_coro = replyer.get_prompt_info(chat_talking_prompt_short, str(sender_name), target)

        identity, kw_line, expr_pack, jargon_block, prompt_info = await asyncio.gather(
            identity_coro,
            kw_coro,
            expr_coro,
            jargon_coro,
            knowledge_coro,
            return_exceptions=True,
        )

        if isinstance(identity, Exception):
            log.debug(f"v2 persona identity: {identity}")
        else:
            metadata["v2_replyer_identity"] = identity

        if isinstance(kw_line, Exception):
            log.debug(f"v2 persona keywords: {kw_line}")
            metadata["v2_keywords_reaction"] = ""
        else:
            metadata["v2_keywords_reaction"] = kw_line or ""

        if isinstance(expr_pack, Exception):
            log.debug(f"v2 persona expression: {expr_pack}")
            metadata["v2_expression_habits"] = ""
        else:
            eb, _sel = expr_pack
            metadata["v2_expression_habits"] = eb or ""

        if isinstance(jargon_block, Exception):
            log.debug(f"v2 persona jargon: {jargon_block}")
            metadata["v2_jargon_explanation"] = ""
        else:
            metadata["v2_jargon_explanation"] = (jargon_block or "").strip()

        if isinstance(prompt_info, Exception):
            log.debug(f"v2 persona knowledge (get_prompt_info): {prompt_info}")
            metadata["v2_knowledge_prompt"] = ""
        else:
            metadata["v2_knowledge_prompt"] = (prompt_info or "").strip()

        try:
            extra = replyer.get_chat_prompt_for_chat(chat_id)
            metadata["v2_chat_prompt_extra"] = (extra or "").strip()
        except Exception as e:
            log.debug(f"v2 persona chat_prompt: {e}")
            metadata["v2_chat_prompt_extra"] = ""
    except Exception as e:
        log.warning(f"v2 人设对齐素材构建失败，回退基础人格字段: {e}")


async def prepare_legacy_persona_and_action_planning(
    chat_stream: "ChatStream",
    message,
    *,
    log: Any = None,
) -> LegacyV2AlignmentBundle:
    """
    新架构单入口：先拉齐旧 replyer 人设素材，再按需跑旧 planner 阶段（与 legacy_planner_bridge 一致）。

    须在频率控制通过之后调用；@/提及时 bridge 内会跳过 planner，与旧链路一致。
    """
    log = log or get_logger("v2_legacy_align")
    inner = global_config.inner
    persona_meta: Dict[str, Any] = {}
    if getattr(inner, "v2_use_replyer_aligned_persona", True):
        await fill_replyer_aligned_persona_metadata(chat_stream, message, persona_meta, log=log)

    planner_phase = await run_legacy_planner_v2_phase(chat_stream, message)

    summary_text: Optional[str] = None
    if planner_phase is not None and planner_phase.planned_actions:
        if getattr(inner, "v2_inject_legacy_planner_summary_into_prompt", False) and (
            not planner_phase.short_circuit_no_reply
        ):
            summary_text = format_legacy_planner_summary_for_prompt(planner_phase.planned_actions)

    return LegacyV2AlignmentBundle(
        persona_meta=persona_meta,
        planner_phase=planner_phase,
        legacy_planner_summary_text=summary_text,
    )
