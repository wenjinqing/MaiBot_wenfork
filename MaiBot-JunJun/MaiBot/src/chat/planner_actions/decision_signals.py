"""
决策客观信号（Decision Signals）

当前旧架构的 planner 几乎完全靠 LLM 读 prompt 里的"铁律"来判断要不要回复、回复给谁，
没有任何客观裏付け。本模块从最近的消息里算出几个**客观事实**，注入到 planner 提示词中，
把"主观臆断"变成"看着事实判断"：

- distinct_speakers       ：最近 N 条消息里有几个不同的人在说话（多人互聊的客观指标）
- addressed_to_bot        ：最近是否有人在直接对机器人说话（@/提及/出现昵称）
- messages_since_bot_spoke：距离机器人上次发言过了几条消息
- bot_last_reply_engaged  ：机器人上一条回复之后，有没有人接话（回复效果 lite，区分"冷场"与"被无视"）

设计原则（与 Timing Gate / DB 清理一致）：配置开关 + 失败隔离（任何异常都返回空，绝不影响主流程）。
"""

import traceback
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

from src.config.config import global_config
from src.common.logger import get_logger

if TYPE_CHECKING:
    from src.common.data_models.database_data_model import DatabaseMessages

logger = get_logger("decision_signals")


@dataclass
class ConversationSignals:
    """从最近消息算出的客观会话信号。"""

    distinct_speakers: int = 0
    addressed_to_bot: bool = False
    messages_since_bot_spoke: Optional[int] = None  # None 表示窗口内机器人没发过言
    bot_last_reply_engaged: Optional[bool] = None  # None 表示机器人最近没发言/无法判断
    followups_after_bot: int = 0  # 机器人上次发言后他人接话条数

    def to_prompt_block(self, bot_name: str) -> str:
        """渲染成一段简短的客观信号文本，供 planner 参考。空信号返回空串。"""
        lines: List[str] = []
        if self.distinct_speakers >= 3:
            lines.append(
                f"- 最近有 {self.distinct_speakers} 个不同的人在说话，多半是群友之间在互聊，先判断这是不是对你说的"
            )
        if self.addressed_to_bot:
            lines.append("- 最近有人像是在直接对你说话或叫你（出现了你的名字/@），这通常是该回应的信号")
        else:
            lines.append("- 最近没有人直接叫你或 @ 你")
        if self.messages_since_bot_spoke is not None:
            if self.bot_last_reply_engaged is False:
                lines.append(
                    f"- 你上次发言后过了 {self.messages_since_bot_spoke} 条消息，但没人接你的话——"
                    f"注意不要自说自话、连续刷屏"
                )
            elif self.bot_last_reply_engaged is True:
                lines.append(
                    f"- 你上次发言后有 {self.followups_after_bot} 人接了话，互动还在继续"
                )
        if not lines:
            return ""
        return "**当前客观信号（供参考，不是硬性指令）**\n" + "\n".join(lines) + "\n"


def _is_from_bot(msg: "DatabaseMessages") -> bool:
    try:
        return str(msg.user_info.user_id) == str(global_config.bot.qq_account)
    except Exception:
        return False


def _addresses_bot(msg: "DatabaseMessages", names: List[str]) -> bool:
    """判断一条消息是否在对机器人说话：@/提及标志，或文本里出现机器人昵称。"""
    try:
        if getattr(msg, "is_mentioned", False) or getattr(msg, "is_at", False):
            return True
        text = (msg.processed_plain_text or "")
        return any(name and name in text for name in names)
    except Exception:
        return False


def compute_signals(recent_messages: List["DatabaseMessages"]) -> ConversationSignals:
    """从最近消息（时间升序）算出客观会话信号。失败时返回空信号。"""
    signals = ConversationSignals()
    if not recent_messages:
        return signals
    try:
        # 机器人名字集合（昵称 + 别名）
        names: List[str] = []
        if global_config.bot.nickname:
            names.append(global_config.bot.nickname)
        if global_config.bot.alias_names:
            names.extend([a for a in global_config.bot.alias_names if a])

        window = recent_messages[-12:]

        # 1) 不同发言人数（排除机器人自己）
        speakers = set()
        for m in window:
            if _is_from_bot(m):
                continue
            try:
                speakers.add(str(m.user_info.user_id))
            except Exception:
                continue
        signals.distinct_speakers = len(speakers)

        # 2) 最近 3 条里是否有人在对机器人说话
        signals.addressed_to_bot = any(_addresses_bot(m, names) for m in window[-3:])

        # 3) 距机器人上次发言的消息数 + 4) 上次发言后是否有人接话
        last_bot_idx = None
        for i in range(len(recent_messages) - 1, -1, -1):
            if _is_from_bot(recent_messages[i]):
                last_bot_idx = i
                break
        if last_bot_idx is not None:
            after = recent_messages[last_bot_idx + 1 :]
            non_bot_after = [m for m in after if not _is_from_bot(m)]
            signals.messages_since_bot_spoke = len(after)
            signals.followups_after_bot = len(non_bot_after)
            # 机器人发言后已经过了一些消息却无人接话 → 视为未被接话（冷场/被无视）
            if len(after) >= 2:
                signals.bot_last_reply_engaged = len(non_bot_after) > 0

        return signals
    except Exception as e:
        logger.debug(f"计算决策信号失败，返回空信号: {e}")
        logger.debug(traceback.format_exc())
        return ConversationSignals()
