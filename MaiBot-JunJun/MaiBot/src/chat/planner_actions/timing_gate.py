"""
Timing Gate（节奏门控）

在重量级 planner / 回复生成之前，先用一次「轻量」LLM 判断当前聊天时机，决定本轮：

- continue ：正常进入完整思考（planner + 可能的回复），与不开启门控时行为一致
- wait     ：对方似乎话没说完 / 还在连续发言，先等一小会儿再重新判断，避免抢话打断
- no_reply ：当前是群友之间的互聊、与机器人无关，本轮直接跳过，省下 planner 与回复开销

设计原则（针对稳定的旧架构）：
1. **配置开关**：由 `global_config.chat.enable_timing_gate` 控制，默认关闭，老用户行为不变。
2. **失败放行（fail-open）**：任何异常、空响应、解析失败都返回 continue，
   绝不会因为门控自身的问题让机器人「哑火」。
3. **被点名豁免**：被 @ / 提及时根本不会走到这里（调用方负责），点名必答的行为不受影响。
4. **低成本**：模型 model_list 留空时自动复用 planner 模型；输出只需一个动作词。

概念移植自原项目（maisaka 架构）的 timing_gate，但完全用旧架构的 LLMRequest / 提示词风格重写，
不引入 maisaka 的任何依赖。
"""

import time
import traceback
from typing import List, Optional, TYPE_CHECKING

from src.config.config import global_config, model_config
from src.common.logger import get_logger
from src.llm_models.utils_model import LLMRequest
from src.chat.message_receive.chat_stream import get_chat_manager
from src.chat.utils.chat_message_builder import build_readable_messages

if TYPE_CHECKING:
    from src.common.data_models.database_data_model import DatabaseMessages

logger = get_logger("timing_gate")

# 门控可输出的合法决策
TIMING_CONTINUE = "continue"
TIMING_WAIT = "wait"
TIMING_NO_REPLY = "no_reply"
_VALID_ACTIONS = {TIMING_CONTINUE, TIMING_WAIT, TIMING_NO_REPLY}


class TimingGate:
    """单个聊天流的节奏门控器。"""

    def __init__(self, chat_id: str, is_group: bool = True):
        self.chat_id = chat_id
        self.is_group = is_group
        self.log_prefix = f"[{get_chat_manager().get_stream_name(chat_id) or chat_id}]"
        # 复用 planner 风格的轻量请求；model_list 为空时 get_timing_gate_task 会回退到 planner 模型
        self._llm = LLMRequest(
            model_set=model_config.model_task_config.get_timing_gate_task(),
            request_type="timing_gate",
        )

    def _build_prompt(self, recent_messages_list: List["DatabaseMessages"]) -> str:
        """构建轻量门控提示词。只读最近少量消息，避免与 planner 重复的大上下文开销。"""
        bot_name = global_config.bot.nickname
        alias = ""
        if global_config.bot.alias_names:
            alias = f"（也有人叫你 {', '.join(global_config.bot.alias_names)}）"

        # 只取传入的这批最近消息，控制 token；门控只关心「此刻的节奏」。瘦身：6 条足够判节奏
        chat_content = build_readable_messages(
            recent_messages_list[-6:],
            replace_bot_name=True,
            timestamp_mode="relative",
            read_mark=0.0,
            truncate=True,
            show_actions=False,
        )

        scene = "群聊" if self.is_group else "私聊"

        # 瘦身：不注入完整人设（判断节奏用不到，省 token）；调平衡：默认更倾向 continue
        return f"""你是 {bot_name}{alias}，正在参与一段 QQ {scene}。
你现在**不是**要生成回复，只判断当前聊天「节奏」，决定这一轮要不要开口。
（标注为 {bot_name}(你) 的消息是你自己之前发的。）

**最近的聊天内容：**
{chat_content}

在下面三种动作中选一个：
- continue：适合你开口——有人叫你/问你，或话题你能自然接上、有兴趣搭话。默认倾向选它。
- wait：对方明显还没说完（连发好几条、句子断在半截、还在补充），先等一下别抢话。
- no_reply：这一批纯粹是别人之间、与你完全无关的对话，或你刚说过类似的话，此刻不该插。

判断要点：
1. 只要话题你接得住、能自然搭上一句，就选 continue——不必非得有人点名。
2. 对方像话说到一半或在连续补充时，选 wait 让他说完。
3. 只有当这批消息明显与你无关、硬插会突兀时，才 no_reply。

**输出格式（严格遵守）：**
只输出一个词：continue 或 wait 或 no_reply。不要输出任何解释、标点或多余内容。"""

    @staticmethod
    def _parse(llm_content: Optional[str]) -> str:
        """从 LLM 输出中解析出动作词；无法识别时按 continue（放行）处理。"""
        if not llm_content:
            return TIMING_CONTINUE
        text = llm_content.strip().lower()
        # 直接命中
        for action in (TIMING_NO_REPLY, TIMING_WAIT, TIMING_CONTINUE):
            # no_reply 要先于 reply 之类的子串匹配；这里用包含判断，兼容模型多输出几个字
            if action in text:
                return action
        # 一些中文/同义表述兜底
        if any(k in text for k in ("等", "稍等", "没说完", "再等")):
            return TIMING_WAIT
        if any(k in text for k in ("不回复", "沉默", "不插话", "无关")):
            return TIMING_NO_REPLY
        return TIMING_CONTINUE

    async def decide(self, recent_messages_list: List["DatabaseMessages"]) -> str:
        """
        返回 continue / wait / no_reply 之一。

        失败放行：任何异常或空响应都返回 continue，保证不会因门控问题而让机器人哑火。
        """
        if not recent_messages_list:
            return TIMING_CONTINUE
        try:
            start = time.time()
            prompt = self._build_prompt(recent_messages_list)
            llm_content, _ = await self._llm.generate_response_async(
                prompt=prompt,
                raise_when_empty=False,
            )
            action = self._parse(llm_content)
            elapsed = time.time() - start
            logger.info(
                f"{self.log_prefix} Timing Gate 判定: {action}"
                f"（耗时{elapsed:.2f}s，原始输出: {str(llm_content).strip()[:40]!r}）"
            )
            return action if action in _VALID_ACTIONS else TIMING_CONTINUE
        except Exception as e:
            logger.warning(f"{self.log_prefix} Timing Gate 判定失败，按 continue 放行: {e}")
            logger.debug(traceback.format_exc())
            return TIMING_CONTINUE
