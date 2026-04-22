"""
MaiBot 版「今日运势」娱乐插件（指令风格对齐 koishi-plugin-jrys-prpr，但并非 npm 包，无需 Node/Koishi）。

签文（等级+星级）按用户+自然日写入数据库，同日不变；解签每次重新生成。
默认卡片**不**展示桃花/财运等分项；需要时用 `jrysprpr 详` / `jrysprpr -d` 或发「今日运势详」「今日运势详细」「分项运势」触发分项并重新解签。
另支持「今日桃花」「工作运势」等**分项独立关键字**：每次只算一项，单独发分项运势图（与主运势卡无关）。
主卡解签采用「签诗 VERSE + 白话 LINE」双层结构，风格参考常见运势签。
模型任务见 model_task_config.jrys_fortune。
"""

from __future__ import annotations

import base64
import io
import random
import re
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type

from src.plugin_system import BasePlugin, BaseCommand, ComponentInfo, register_plugin, ConfigField
from src.common.logger import get_logger
from src.config.config import model_config
from src.plugin_system.apis import database_api, llm_api
from src.common.database.database_model import JrysDailyLot
from src.config.config import global_config
from PIL import Image

from .card_render import (
    _safe_display_text,
    _star_bar,
    pick_local_fortune_entry,
    png_to_base64,
    render_fortune_png,
)

logger = get_logger("jrys_prpr_maimbot")

PLUGIN_DIR = Path(__file__).resolve().parent

_REQ_LOT = "jrys_fortune.daily_lot"
_REQ_INTERP = "jrys_fortune.interpretation"
_REQ_SUB_LUCK = "jrys_fortune.sub_luck"
_REQ_SINGLE_DIM = "jrys_fortune.single_dimension"

_LUCK_DIMS: Tuple[str, ...] = ("桃花", "财运", "仕途", "健康", "人缘")

_SINGLE_PHRASE_DIM_RAW: Tuple[Tuple[str, str], ...] = (
    ("今日感情运势", "桃花"),
    ("今日恋爱运势", "桃花"),
    ("感情运势", "桃花"),
    ("恋爱运势", "桃花"),
    ("今日桃花运", "桃花"),
    ("桃花运势", "桃花"),
    ("今日桃花", "桃花"),
    ("今日感情", "桃花"),
    ("今日恋爱", "桃花"),
    ("职场运势", "仕途"),
    ("工作运势", "仕途"),
    ("事业运势", "仕途"),
    ("今日工作", "仕途"),
    ("今日仕途", "仕途"),
    ("仕途运势", "仕途"),
    ("学业运势", "仕途"),
    ("考试运势", "仕途"),
    ("今日学业", "仕途"),
    ("财运运势", "财运"),
    ("今日财运", "财运"),
    ("身体运势", "健康"),
    ("今日身体", "健康"),
    ("健康运势", "健康"),
    ("今日健康", "健康"),
    ("人际关系", "人缘"),
    ("社交运势", "人缘"),
    ("人缘运势", "人缘"),
    ("今日人缘", "人缘"),
)
_SINGLE_PHRASE_DIM_SORTED: Tuple[Tuple[str, str], ...] = tuple(
    sorted(_SINGLE_PHRASE_DIM_RAW, key=lambda x: len(x[0]), reverse=True)
)


def _match_single_luck_phrase(text: str) -> str | None:
    t = text or ""
    for phrase, dim in _SINGLE_PHRASE_DIM_SORTED:
        if phrase in t:
            return dim
    return None


def _single_luck_command_pattern() -> str:
    phrases = sorted({p for p, _ in _SINGLE_PHRASE_DIM_RAW}, key=len, reverse=True)
    alt = "|".join(re.escape(p) for p in phrases)
    return rf"^(?!.*今日运势)[\s\S]{{0,500}}(?:{alt})[\s\S]{{0,500}}$"


def _keyword_requests_detail_luck(text: str) -> bool:
    """关键词里要求「带分项的详版卡」：与默认「今日运势」区分。"""
    t = text or ""
    if "分项运势" in t:
        return True
    if "今日运势详细" in t:
        return True
    if re.search(r"今日运势\s*详(?:\s|$|[,，;；。！？])", t):
        return True
    return False


def _parse_jrysprpr_extra(extra: str) -> Tuple[bool, bool]:
    """jrysprpr 后的空格参数 → (split 先发文字, detail 要分项详卡并重新解签)。"""
    tokens = (extra or "").split()
    split = any(tok in ("-s", "--split") for tok in tokens)
    detail = any(tok in ("-d", "--detail", "详", "详细") for tok in tokens)
    return split, detail


# 君君人设：涩气小猫娘、短句口语、偶尔喵；{name}=机器人自称，{nick}=用户昵称（已截断）
_JRYS_CONFIRM_TEMPLATES: Tuple[str, ...] = (
    "{name}收到喵～摇签中，稍等一咪咪。",
    "想看今日运势？行呀，{name}这就去晃签筒。",
    "嗯哼……抽签交给{name}就好，你先深呼吸一下？",
    "{name}摇签中～别催嘛，催了也未必大吉哦？开玩笑的，喵。",
    "今日运势单子{name}接了，乖乖等出图喵。",
    "{nick}要的签文？{name}在帮你摇了，先别偷看结果。",
    "签筒沙沙响……{name}认真得很，不许捣乱。",
    "运势这种东西，{name}帮你摸一把就好，别紧张。",
    "来都来了，{name}给你摇个狠的……咳，合法娱乐那种。",
    "{name}掐指一算——不对，是按流程摇签，马上好。",
    "小猫办事你放心，{name}去摇签，你喝口水等我。",
    "今日份玄学由{name}承包，摇完就发你，别急。",
    "{nick}今天手气怎样，就看这一签了，{name}开工喵。",
    "签文正在路上，{name}没跑路，只是模型要转一下。",
    "运势卡片生成中……{name}也在好奇你会抽到什么。",
    "摇签也是体力活好吧，{name}摇得可认真了，等等我。",
    "收到收到，{name}这就把签筒晃出火星子——比喻啦。",
    "{nick}，{name}听见啦，今日运势马上安排。",
    "喵呜，占卜请求确认～{name}去摇签，别走开。",
    "今日总签{name}去摇啦，你先把期待值调低一点点？娱乐向的。",
    "签筒已就位，{name}开始晃——晃出好签算你赚到。",
    "{nick}等等，{name}把签文从模型那边薅过来就发。",
    "玄学小作坊开工：{name}负责摇，你负责接收好运碎片。",
    "别慌别慌，{name}在走流程，出图前不许偷偷换愿望。",
    "今日运势加载条……{name}这边是真实物理摇签版。",
    "想偷看？不行。{name}摇完之前结果一律加密喵。",
    "{name}把耳朵竖起来了：占卜请求已读，执行中。",
    "签文生成中，{name}也在猜你会抽到吉还是末吉。",
    "深呼吸，吐气，然后等{name}把签甩你脸上——温柔地。",
    "今日份签筒 KPI，{name}帮你冲一冲。",
    "{nick}，{name}记下啦，这就去跟签筒谈判。",
    "摇签三秒，解签……看模型心情，{name}会催的。",
    "小猫盖章：此单{name}接了，出图前先去摸个鱼……骗你的，马上摇。",
    "运势卡片排版中，{name}顺便帮你把晦气抖一抖。",
    "收到！{name}把签筒抱稳了，这次不手滑。",
    "今日运势请求入队，{name}插队帮你办，感动吧？",
    "签筒说它也想知道，{name}这就替你们双向奔赴一下。",
    "{nick}的心愿{name}听见了，摇签这种粗活交给我。",
    "先确认一下：你要的是今日总签对吧？{name}开工。",
    "喵的，又来一单……{name}摇得动，放心。",
    "运势出图前请保持微笑，{name}正在施法（按协议调用）。",
    "今日玄学快递：{name}已揽件，派送中。",
    "{name}把爪子在签筒上抹抹干净，马上给你摇。",
    "别急，{name}在摇——摇签比回消息更需要仪式感。",
    "签文在路上，{name}没摸鱼，真的，签筒可以作证。",
    "今日运势：{name}已切换「认真摇签」模式。",
    "{nick}，{name}收到，先去跟签筒开个短会。",
)

# 分项触发（今日桃花等）；{dim}=该项名称（桃花、财运…）
_JRYS_SINGLE_CONFIRM_TEMPLATES: Tuple[str, ...] = (
    "{nick}想单独看「{dim}」？行，{name}转专项签筒，稍等喵。",
    "只算「{dim}」呀……{name}懂了，这就帮你摇这一枝。",
    "「{dim}」专线接通中，{name}去摇，别走开。",
    "{name}收到：今日{dim}单项，马上摇给你看。",
    "总签不动，先看「{dim}」？可以，{name}拆一条分项给你。",
    "{nick}的「{dim}」请求{name}接了，摇完就发图。",
    "专项运势也是体力活，{name}摇「{dim}」会认真的。",
    "喵呜，「{dim}」单子确认～{name}去晃小签筒。",
    "只看「{dim}」也很合理，{name}帮你单独摸一把。",
    "「{dim}」运势生成中……{name}没跑路，模型在转。",
    "{name}把「{dim}」签筒抱出来了，等我三秒。",
    "今日{dim}？{name}听见啦，专项摇签开工。",
    "{nick}等等，{name}去给「{dim}」单独求个签。",
    "分项也是签，{name}照样晃出火星子——比喻啦，「{dim}」马上好。",
    "「{dim}」这条{name}帮你插队摇，感动要有的。",
    "签筒沙沙响……这次是「{dim}」专场，{name}在摇。",
    "想偷看「{dim}」结果？不行，{name}摇完再发。",
    "{name}切换「{dim}」模式：专注摇签，勿扰……开玩笑的，很快。",
    "今日{dim}运势加载中，{name}帮你按住签筒不让它乱跑。",
    "「{dim}」小灶开摇，{name}火已点好，别急。",
    "{nick}要的「{dim}」，{name}记下了，摇签去也。",
    "专项签文也是娱乐向，{name}摇「{dim}」会可爱一点的。",
    "「{dim}」这一枝交给{name}，你喝口水等我出图。",
    "{name}收到「{dim}」占卜请求，签筒已就位。",
    "只看一项也很清楚嘛，{name}这就摇「{dim}」。",
    "「{dim}」运势{name}承包了，摇完发你，喵。",
    "{nick}，{name}去摇「{dim}」啦，先别刷屏催哦。",
    "今日「{dim}」专线繁忙……骗你的，{name}马上给你摇。",
    "分项摇签也是摇，{name}对「{dim}」一样认真。",
    "收到～「{dim}」单项，{name}这就去跟签筒谈判。",
)


def _resolve_bot_self_name(cmd: BaseCommand) -> str:
    name = str(cmd.get_config("confirm.self_name", "") or "").strip()
    if name:
        return name[:16]
    bot = getattr(global_config, "bot", None)
    n = str(getattr(bot, "nickname", None) or "").strip()
    return n[:16] if n else "依依"


def _personality_snippet_for_jrys() -> str:
    """从 bot_config 注入解签：人格 + 表达习惯（过长截断）；状态按 state_probability 随机替换，与聊天侧一致。"""
    pc = getattr(global_config, "personality", None)
    if pc is None:
        return ""
    prompt_personality = (getattr(pc, "personality", None) or "").strip()
    states = getattr(pc, "states", None) or []
    prob = float(getattr(pc, "state_probability", 0.0) or 0.0)
    if states and prob > 0 and random.random() < prob:
        prompt_personality = (random.choice(states) or "").strip()
    rs = (getattr(pc, "reply_style", None) or "").strip()
    parts: List[str] = []
    if prompt_personality:
        parts.append(prompt_personality)
    if rs:
        parts.append(f"表达习惯：{rs}")
    text = "\n".join(parts).strip()
    if len(text) > 1200:
        text = text[:1200].rstrip() + "…"
    return text


def _pick_confirm_message(
    cmd: BaseCommand,
    user_nickname: str,
    *,
    dimension: str | None = None,
) -> str:
    nick = (user_nickname or "你").strip()[:20] or "你"
    name = _resolve_bot_self_name(cmd)
    if dimension:
        dim = (dimension or "").strip()[:8] or "这项"
        tpl = random.choice(_JRYS_SINGLE_CONFIRM_TEMPLATES)
        return tpl.format(name=name, nick=nick, dim=dim)
    tpl = random.choice(_JRYS_CONFIRM_TEMPLATES)
    return tpl.format(name=name, nick=nick)


def _parse_lot_only(text: str) -> Dict[str, Any] | None:
    title, stars = None, None
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        up = s.upper()
        if up.startswith("TITLE:"):
            title = s.split(":", 1)[1].strip()
        elif up.startswith("STARS:"):
            try:
                stars = int(s.split(":", 1)[1].strip().split()[0])
            except (ValueError, IndexError):
                stars = None
    if not title or stars is None:
        return None
    stars = max(1, min(5, int(stars)))
    return {"title": title[:12], "stars": stars}


def _luck_from_seed(seed: str) -> Dict[str, int]:
    rng = random.Random(seed)
    return {k: rng.randint(1, 5) for k in _LUCK_DIMS}


def _parse_sub_luck_response(text: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        for k in _LUCK_DIMS:
            mo = re.match(rf"^{re.escape(k)}\s*[:：]\s*(\d)\s*$", s)
            if mo:
                out[k] = max(1, min(5, int(mo.group(1))))
                break
    return out


def _merge_luck(parsed: Dict[str, int], seed: str) -> Dict[str, int]:
    base = _luck_from_seed(seed)
    base.update(parsed)
    return {k: base[k] for k in _LUCK_DIMS}


async def roll_sub_luck_for_reading(
    *,
    title: str,
    stars: int,
    bind_key: str,
    day_iso: str,
) -> Dict[str, int]:
    """分项运随每次解签/出图重新摇（不入库）；与总签当日固定无关。"""
    raw = await _llm_draw_sub_luck(
        title=title,
        stars=stars,
        bind_key=bind_key,
        day_iso=day_iso,
    )
    seed = f"{bind_key}:{day_iso}:{time.time_ns()}"
    return _merge_luck(_parse_sub_luck_response(raw or ""), seed)


async def _llm_draw_sub_luck(
    *,
    title: str,
    stars: int,
    bind_key: str,
    day_iso: str,
) -> str | None:
    task = model_config.model_task_config.jrys_fortune
    prompt = f"""你是运势签辅助，只输出分项星级（每项 1～5），与总签略协调即可，勿写正文。
本次为**新一轮摇签**：分项可与用户上一次查看时不同。

总签：{title}  总运：{stars}/5
绑定：{bind_key}  日期：{day_iso}

请输出且仅输出下面 5 行，行名必须完全一致，冒号用英文 : 或中文 ：均可，冒号后只跟一个 1～5 的整数，不要标题、不要解释、不要 markdown：
桃花:
财运:
仕途:
健康:
人缘:
（每行冒号后填入你判定的整数）"""

    ok, response, _r, _m = await llm_api.generate_with_model(
        prompt,
        task,
        request_type=_REQ_SUB_LUCK,
        max_tokens=128,
        temperature=0.45,
    )
    if not ok:
        logger.warning(f"jrys_fortune 分项运 LLM 失败: {(response or '')[:200]}")
        return None
    return response


def _parse_line_only(text: str) -> str | None:
    """解析解签：兼容 LINE: / LINE：、整段无标签的正文（模型常不按格式输出）。"""
    t = (text or "").strip()
    if not t:
        return None

    for raw in t.splitlines():
        s = raw.strip()
        if not s:
            continue
        mo = re.match(r"(?i)^LINE\s*[:：]\s*(.*)$", s)
        if mo:
            v = mo.group(1).strip()
            if v:
                return v[:4000]

    # 去掉 markdown 代码块外壳
    fence = t
    if fence.startswith("```"):
        fence = re.sub(r"^```\w*\s*", "", fence)
        fence = re.sub(r"\s*```\s*$", "", fence).strip()
        for raw in fence.splitlines():
            s = raw.strip()
            mo = re.match(r"(?i)^LINE\s*[:：]\s*(.*)$", s)
            if mo and mo.group(1).strip():
                return mo.group(1).strip()[:4000]

    # 无 LINE 行：去掉 TITLE/STARS/VERSE/LINE 行后合并为正文（多行解签保留）
    body_lines: List[str] = []
    for raw in fence.splitlines():
        s = raw.strip()
        if not s:
            continue
        if re.match(r"(?i)^TITLE\s*[:：]", s):
            continue
        if re.match(r"(?i)^STARS\s*[:：]", s):
            continue
        if re.match(r"(?i)^VERSE\s*[:：]", s):
            continue
        if re.match(r"(?i)^LINE\s*[:：]", s):
            continue
        body_lines.append(s)
    body = "\n".join(body_lines).strip()
    if len(body) >= 16:
        return body[:4000]
    return None


def _parse_interpretation_verse_and_line(text: str) -> Tuple[str | None, str | None]:
    """解析总运解签：VERSE（签诗式短句）+ LINE（白话）；兼容仅 LINE 或整段无标签。"""
    verse: str | None = None
    line: str | None = None
    t = (text or "").strip()
    if not t:
        return None, None
    for raw in t.splitlines():
        s = raw.strip()
        if not s:
            continue
        mo = re.match(r"(?i)^VERSE\s*[:：]\s*(.*)$", s)
        if mo and mo.group(1).strip():
            verse = mo.group(1).strip()[:200]
        mo2 = re.match(r"(?i)^LINE\s*[:：]\s*(.*)$", s)
        if mo2 and mo2.group(1).strip():
            line = mo2.group(1).strip()[:4000]
    if line:
        return verse, line
    return verse, _parse_line_only(t)


def _parse_star_verse_line_block(text: str) -> Tuple[int | None, str | None, str | None]:
    """解析分项单次 LLM：STAR、可选 VERSE（文言断语）、LINE。"""
    star: int | None = None
    verse: str | None = None
    line: str | None = None
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        if re.match(r"(?i)^STAR\s*[:：]", s):
            mo = re.search(r"[:：]\s*(\d)", s)
            if mo:
                try:
                    star = max(1, min(5, int(mo.group(1))))
                except ValueError:
                    star = None
        if re.match(r"(?i)^VERSE\s*[:：]", s):
            mo = re.match(r"(?i)^VERSE\s*[:：]\s*(.*)$", s)
            if mo and mo.group(1).strip():
                verse = mo.group(1).strip()[:120]
        if re.match(r"(?i)^LINE\s*[:：]", s):
            mo = re.match(r"(?i)^LINE\s*[:：]\s*(.*)$", s)
            if mo:
                v = mo.group(1).strip()
                if v:
                    line = v[:2000]
    return star, verse, line


def _limit_image_base64_for_send(b64: str, max_raw_bytes: int = 2_400_000) -> str:
    """过长 PNG 易触发 NapCat/链路限制；超限时先略缩小、仍偏大再转 JPEG（尽量保清晰度）。"""
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception:
        return b64
    if len(raw) <= max_raw_bytes:
        return b64
    try:
        im = Image.open(io.BytesIO(raw))
        w0, h0 = im.size
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS  # type: ignore[attr-defined]
        scale = 0.88
        for _ in range(5):
            if len(raw) <= max_raw_bytes:
                break
            w0 = max(360, int(w0 * scale))
            h0 = max(440, int(h0 * scale))
            im = im.resize((w0, h0), resample)
            buf = io.BytesIO()
            rgb = im.convert("RGB")
            rgb.save(buf, format="JPEG", quality=92, optimize=True, subsampling=0)
            raw = buf.getvalue()
            b64 = base64.b64encode(raw).decode("ascii")
            scale = 0.82
    except Exception as e:
        logger.warning(f"jrys 图片压缩失败，使用原图: {e}")
    return b64


def _soft_clamp_interp(s: str, max_chars: int = 110) -> str:
    """解签过长时截断，避免卡片过高（模型偶发超长）。"""
    t = (s or "").strip()
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars].rstrip("，。、；; ")
    return cut + "…"


def _ensure_nickname_in_line(line: str, nickname: str) -> str:
    nick = (nickname or "").strip()
    if not nick:
        return line
    if nick in line:
        return line
    return f"{nick}，{line}"


def _ensure_bot_name_in_line(line: str, bot_name: str) -> str:
    bn = (bot_name or "").strip()
    if not bn:
        return line
    if bn in line:
        return line
    return f"{bn}帮你看完签啦——{line}"


async def _llm_draw_daily_lot(*, bind_key: str, day_iso: str) -> Dict[str, Any] | None:
    task = model_config.model_task_config.jrys_fortune
    prompt = f"""你是运势签筒助手，只输出「签」的等级与星级，不要解签正文。

绑定用户标识：{bind_key}
今日日期：{day_iso}

请严格输出下面两行（键名大写英文，冒号后一个空格），不要有其它任何内容：
TITLE: （2～4 个汉字，如 大吉、中吉、小吉、末吉）
STARS: （1 到 5 的整数）"""

    ok, response, _r, _m = await llm_api.generate_with_model(
        prompt,
        task,
        request_type=_REQ_LOT,
        max_tokens=128,
    )
    if not ok:
        logger.warning(f"jrys_fortune 抽签 LLM 失败: {(response or '')[:200]}")
        return None
    return _parse_lot_only(response)


async def _llm_daily_interpretation(
    *,
    nickname: str,
    bot_name: str,
    persona_snippet: str,
    bind_key: str,
    day_iso: str,
    title: str,
    stars: int,
    card_has_sub_luck: bool,
) -> Tuple[str | None, str | None]:
    task = model_config.model_task_config.jrys_fortune
    ps = (persona_snippet or "").strip()
    if ps:
        persona_block = (
            f"\n你是聊天机器人「{bot_name}」，请按下面人设**语气与性格**来写解签"
            "（内化人设，勿复述设定原文；人设仅供风格参考）：\n"
            + ps
            + "\n"
        )
    else:
        persona_block = f"\n你是聊天机器人「{bot_name}」，用符合你日常聊天口吻的方式解签。\n"
    if card_has_sub_luck:
        scope = (
            "你是解签助手。今日总签与桃花/财运等分项已在卡片上单独展示，你**不要**再列举分项星级。"
        )
        ban_sub = "4) 禁止 markdown、禁止列表、禁止写「桃花」「财运」等分项词（卡片已有）。\n"
    else:
        scope = (
            "你是解签助手。今日卡片**只**展示总签等级、总运星级与总运解签，**没有**桃花/财运等分项栏。"
            "只写总运层面的安慰或俏皮话，不要主动提及或列举「桃花」「财运」「仕途」「健康」「人缘」等分项。"
        )
        ban_sub = "4) 禁止 markdown、禁止列表。\n"
    prompt = (
        scope
        + persona_block
        + f"""
今日总签：{title}  总运：{stars}/5
用户昵称：{nickname}
绑定：{bind_key}  日期：{day_iso}

要求（务必遵守）——模仿常见「今日运势」签：先**签诗式短句**，再**白话解说**：
1) **VERSE**：全句 **16～24 个汉字**，文言、对仗或顿号分节（参考风格：「忍得苦难，必有后福，是成是败，惟靠坚毅」「名虽可得，利则难获，艺界发展，可望成功」）。**不要**写昵称或机器人名，不要 markdown。
2) **LINE**：**白话总运解签**，**50～100 个汉字**，把 VERSE 的意思用现代话说清楚，温暖、安慰或略带俏皮；必须自然带上用户昵称「{nickname}」一次；必须自然带上「{bot_name}」一次。
3) 签诗与白话须语义呼应，勿各说各话。
{ban_sub}5) 不要复述「TITLE/STARS」字样。

输出格式（严格三行，键名大写英文，冒号后一个空格）：
VERSE: （签诗式短句，一行内写完）
LINE: （白话解签）"""
    )

    ok, response, _r, _m = await llm_api.generate_with_model(
        prompt,
        task,
        request_type=_REQ_INTERP,
        max_tokens=384,
        temperature=0.52,
    )
    if not ok:
        logger.warning(f"jrys_fortune 解签 LLM 失败: {(response or '')[:200]}")
        return None, None
    verse, line = _parse_interpretation_verse_and_line(response or "")
    if not line:
        logger.warning(
            "jrys_fortune 解签已返回但无法解析为正文（将用兜底短句）。"
            f" 模型原始片段: {(response or '')[:400]!r}"
        )
        return verse, None
    line = _ensure_nickname_in_line(line, nickname)
    return verse, line


async def _llm_single_dimension_reading(
    *,
    nickname: str,
    bot_name: str,
    persona_snippet: str,
    bind_key: str,
    day_iso: str,
    title: str,
    stars: int,
    dimension: str,
) -> Tuple[int, str, str | None] | None:
    """只算一个分项：返回 (该项星级, 白话解签, 可选文言断语)。"""
    task = model_config.model_task_config.jrys_fortune
    ps = (persona_snippet or "").strip()
    persona_tail = "\n请保持与下面机器人人设口吻一致（内化即可，勿复述设定）：\n" + ps + "\n" if ps else ""
    prompt = (
        f"你是分项运势助手。只针对「{dimension}」这一项给出星级与短解签（仅供娱乐）。\n"
        f"用户今日总签（供语气参考，勿堆砌抄写）：「{title}」，总运 {stars}/5。\n"
        f"用户昵称：{nickname}\n"
        f"机器人名字：{bot_name}\n"
        f"绑定：{bind_key}  日期：{day_iso}\n"
        + persona_tail
        + f"""
要求：
1) STAR：只表示「{dimension}」这一项，1～5 的整数。
2) VERSE（可选但尽量写）：**8～20 个汉字**，该项的文言断语一句，不要昵称与机器人名。
3) LINE：只写「{dimension}」白话，约 30～90 个汉字；必须出现用户昵称「{nickname}」一次；必须出现「{bot_name}」一次；禁止 markdown；禁止列举其他分项名。

请严格只输出下面三行（键名大写英文，冒号后一个空格）：
STAR: （1～5 的整数）
VERSE: （文言断语，一句）
LINE: （白话该项解签）"""
    )

    ok, response, _r, _m = await llm_api.generate_with_model(
        prompt,
        task,
        request_type=_REQ_SINGLE_DIM,
        max_tokens=320,
        temperature=0.52,
    )
    if not ok:
        logger.warning(f"jrys_fortune 单项分项 LLM 失败: {(response or '')[:200]}")
        return None
    st, verse, ln = _parse_star_verse_line_block(response or "")
    if not ln:
        logger.warning(
            "jrys_fortune 单项分项已返回但无法解析 LINE。"
            f" 原始片段: {(response or '')[:400]!r}"
        )
        return None
    if st is None:
        st = 3
    return st, ln, verse


async def get_or_create_daily_lot(
    *,
    bind_key: str,
    day_iso: str,
    plugin_dir: str,
    try_llm_for_new: bool,
) -> Dict[str, Any]:
    """只固定「总签」title+stars；分项不入库，仅详版触发时再摇。"""
    existing = await database_api.db_get(
        JrysDailyLot,
        filters={"bind_key": bind_key, "day_iso": day_iso},
        single_result=True,
    )
    if existing:
        return {
            "title": str(existing["title"]),
            "stars": int(existing["stars"]),
        }

    day_key = f"{day_iso}:{bind_key}"
    lot: Dict[str, Any] | None = None
    if try_llm_for_new:
        lot = await _llm_draw_daily_lot(bind_key=bind_key, day_iso=day_iso)
    if not lot:
        e = pick_local_fortune_entry(plugin_dir, day_key)
        lot = {
            "title": str(e.get("title", "吉"))[:12],
            "stars": max(1, min(5, int(e.get("stars", 3)))),
        }

    await database_api.db_query(
        JrysDailyLot,
        query_type="create",
        data={
            "bind_key": bind_key,
            "day_iso": day_iso,
            "title": lot["title"],
            "stars": lot["stars"],
            "created_at": time.time(),
        },
    )
    refetched = await database_api.db_get(
        JrysDailyLot,
        filters={"bind_key": bind_key, "day_iso": day_iso},
        single_result=True,
    )
    if refetched:
        return {
            "title": str(refetched["title"]),
            "stars": int(refetched["stars"]),
        }
    return dict(lot)


async def _run_jrys_for_message(
    cmd: BaseCommand,
    *,
    split: bool,
    use_llm: bool,
    include_sub_luck: bool = False,
) -> Tuple[bool, str, bool]:
    if not cmd.get_config("plugin.enabled", True):
        return False, "插件已关闭", False

    try:
        ui = getattr(cmd.message, "message_info", None)
        u = getattr(ui, "user_info", None) if ui else None
        platform = str(getattr(u, "platform", None) or getattr(ui, "platform", None) or "unknown")
        uid = str(getattr(u, "user_id", None) or "")
        nickname = (
            str(getattr(u, "user_nickname", None) or "").strip()
            or uid
            or "你"
        )
        bind_key = f"{platform}:{uid}" if uid else f"{platform}:anonymous"
    except Exception:
        nickname, bind_key = "你", "unknown:anonymous"

    nickname = _safe_display_text(nickname)
    reply_anchor = cmd.message

    if cmd.get_config("confirm.enabled", True):
        try:
            await cmd.send_text(
                _safe_display_text(_pick_confirm_message(cmd, nickname)),
                set_reply=True,
                reply_message=reply_anchor,
            )
        except Exception as e:
            logger.debug(f"jrys 确认语发送跳过: {e}")

    day_iso = date.today().isoformat()
    w = int(cmd.get_config("card.width", 480) or 480)
    h = int(cmd.get_config("card.height", 640) or 640)
    rs = int(cmd.get_config("card.render_scale", 2) or 2)

    entry_override: Dict[str, Any] | None = None
    bot_name = _resolve_bot_self_name(cmd)
    if use_llm and cmd.get_config("llm.enabled", True):
        n_steps = 4 if include_sub_luck else 3
        logger.info(
            f"jrys: 进入 LLM 运势流程 day={day_iso} bind={bind_key} "
            f"detail_sub_luck={include_sub_luck}"
        )
        try:
            logger.info(f"jrys: 1/{n_steps} 获取或创建当日总签…")
            lot = await get_or_create_daily_lot(
                bind_key=bind_key,
                day_iso=day_iso,
                plugin_dir=str(PLUGIN_DIR),
                try_llm_for_new=True,
            )
            logger.info(f"jrys: 1/{n_steps} 完成 总签={lot['title']} 星级={lot['stars']}")
            luck: Dict[str, int] | None = None
            if include_sub_luck:
                logger.info(f"jrys: 2/{n_steps} 摇分项运（LLM）…")
                luck = await roll_sub_luck_for_reading(
                    title=str(lot["title"]),
                    stars=int(lot["stars"]),
                    bind_key=bind_key,
                    day_iso=day_iso,
                )
                logger.info(f"jrys: 2/{n_steps} 完成 分项运已生成")
            interp_step = 3 if include_sub_luck else 2
            logger.info(f"jrys: {interp_step}/{n_steps} 解签（LLM）…")
            persona_snip = _personality_snippet_for_jrys()
            verse_raw, interp = await _llm_daily_interpretation(
                nickname=nickname,
                bot_name=bot_name,
                persona_snippet=persona_snip,
                bind_key=bind_key,
                day_iso=day_iso,
                title=lot["title"],
                stars=int(lot["stars"]),
                card_has_sub_luck=include_sub_luck,
            )
            if not interp:
                interp = _ensure_nickname_in_line(
                    f"{bot_name}看了眼签筒：今日签是「{lot['title']}」，星级 {lot['stars']}/5。保持平常心，按自己的节奏来就好。",
                    nickname,
                )
            verse_disp: str | None = None
            if verse_raw and str(verse_raw).strip():
                verse_disp = _soft_clamp_interp(str(verse_raw).strip(), max_chars=52)
            interp = _soft_clamp_interp(
                _ensure_bot_name_in_line(_ensure_nickname_in_line(interp, nickname), bot_name),
                max_chars=130,
            )
            logger.info(f"jrys: {interp_step}/{n_steps} 完成 解签字数={len(interp)}")
            entry_override = {
                "title": _safe_display_text(str(lot["title"])),
                "stars": lot["stars"],
                "line": _safe_display_text(interp),
            }
            if verse_disp:
                entry_override["verse"] = _safe_display_text(verse_disp)
            if include_sub_luck and luck is not None:
                entry_override["luck"] = luck
        except Exception as e:
            logger.exception(f"jrys: LLM 运势流程异常（签文/分项/解签）: {e}")
            try:
                await cmd.send_text(
                    _safe_display_text(f"运势生成中断：{e}"),
                    set_reply=True,
                    reply_message=reply_anchor,
                )
            except Exception as send_e:
                logger.warning(f"jrys: 发送错误提示失败: {send_e}")
            return False, str(e), True

    logger.info("jrys: 渲染运势卡片…")
    try:
        png, summary = render_fortune_png(
            plugin_dir=str(PLUGIN_DIR),
            user_name=str(nickname),
            width=w,
            height=h,
            entry_override=entry_override,
            fortune_seed_key=bind_key,
            render_scale=rs,
        )
    except Exception as e:
        logger.error(f"jrys 生成卡片失败: {e}", exc_info=True)
        await cmd.send_text(
            f"运势卡片生成失败：{e}",
            set_reply=True,
            reply_message=reply_anchor,
        )
        return False, str(e), True

    b64 = png_to_base64(png)
    b64 = _limit_image_base64_for_send(b64)

    if split:
        await cmd.send_text(
            _safe_display_text(f"今日运势\n{summary}"),
            set_reply=True,
            reply_message=reply_anchor,
        )
    await cmd.send_image(b64, set_reply=True, reply_message=reply_anchor)
    logger.info("jrys: 流程结束 运势卡片已发送")
    return True, "已发送运势卡片", True


async def _run_single_luck_dimension_for_message(cmd: BaseCommand) -> Tuple[bool, str, bool]:
    """「今日桃花」等：只算一项，发分项运势 PNG（与主卡同渲染器；出图失败则回退文字）。"""
    if not cmd.get_config("plugin.enabled", True):
        return False, "插件已关闭", False

    text = getattr(cmd.message, "processed_plain_text", None) or ""
    dim = _match_single_luck_phrase(text)
    if not dim:
        return False, "未匹配到分项关键词", False

    try:
        ui = getattr(cmd.message, "message_info", None)
        u = getattr(ui, "user_info", None) if ui else None
        platform = str(getattr(u, "platform", None) or getattr(ui, "platform", None) or "unknown")
        uid = str(getattr(u, "user_id", None) or "")
        nickname = (
            str(getattr(u, "user_nickname", None) or "").strip()
            or uid
            or "你"
        )
        bind_key = f"{platform}:{uid}" if uid else f"{platform}:anonymous"
    except Exception:
        nickname, bind_key = "你", "unknown:anonymous"

    nickname = _safe_display_text(nickname)
    bot_name = _resolve_bot_self_name(cmd)
    day_iso = date.today().isoformat()
    use_llm = bool(cmd.get_config("llm.enabled", True))
    reply_anchor = cmd.message

    logger.info(f"jrys_single: dim={dim} day={day_iso} bind={bind_key}")

    if cmd.get_config("confirm.enabled", True):
        try:
            await cmd.send_text(
                _safe_display_text(_pick_confirm_message(cmd, nickname, dimension=dim)),
                set_reply=True,
                reply_message=reply_anchor,
            )
        except Exception as e:
            logger.debug(f"jrys_single 确认语发送跳过: {e}")

    try:
        lot = await get_or_create_daily_lot(
            bind_key=bind_key,
            day_iso=day_iso,
            plugin_dir=str(PLUGIN_DIR),
            try_llm_for_new=use_llm,
        )
        title_s = str(lot["title"])
        stars_i = int(lot["stars"])
        line_body: str
        star_n: int
        verse_raw: str | None = None
        if use_llm:
            persona_snip = _personality_snippet_for_jrys()
            got = await _llm_single_dimension_reading(
                nickname=nickname,
                bot_name=bot_name,
                persona_snippet=persona_snip,
                bind_key=bind_key,
                day_iso=day_iso,
                title=title_s,
                stars=stars_i,
                dimension=dim,
            )
            if got:
                star_n, line_body, verse_raw = got
            else:
                seed = f"{bind_key}:{day_iso}:{dim}:{time.time_ns()}"
                star_n = random.Random(seed).randint(1, 5)
                line_body = (
                    f"{nickname}，{bot_name}这边「{dim}」先给个{star_n}星档～模型开小差了，"
                    "这句是本地兜底，娱乐向别当真。"
                )
        else:
            seed = f"{bind_key}:{day_iso}:{dim}:{time.time_ns()}"
            star_n = random.Random(seed).randint(1, 5)
            line_body = (
                f"{nickname}，LLM 关了，{bot_name}只能本地瞎摇「{dim}」{star_n}星，图一乐就好。"
            )

        line_body = _soft_clamp_interp(
            _ensure_bot_name_in_line(_ensure_nickname_in_line(line_body, nickname), bot_name),
            max_chars=180,
        )
        verse_disp = (
            _soft_clamp_interp(str(verse_raw).strip(), max_chars=44)
            if (verse_raw and str(verse_raw).strip())
            else None
        )
        bar = _star_bar(star_n)
        parts: List[str] = [f"【今日{dim}】{bar}"]
        if verse_disp:
            parts.append(verse_disp)
        parts.append(line_body)
        parts.append(f"（仅供娱乐；你今日总签「{title_s}」总运 {stars_i}/5）")
        msg = "\n".join(parts)

        w = int(cmd.get_config("card.width", 480) or 480)
        h = int(cmd.get_config("card.height", 640) or 640)
        rs = int(cmd.get_config("card.render_scale", 2) or 2)
        card_entry: Dict[str, Any] = {
            "title": _safe_display_text(dim),
            "stars": star_n,
            "line": _safe_display_text(line_body),
            "verse": _safe_display_text(verse_disp) if verse_disp else "",
            "header_title": _safe_display_text(f"今日{dim}")[:24],
            "footer_note": _safe_display_text(
                f"结合今日总签「{title_s}」总运 {stars_i}/5"
            )[:100],
        }
        try:
            png, _summary = render_fortune_png(
                plugin_dir=str(PLUGIN_DIR),
                user_name=str(nickname),
                width=w,
                height=h,
                entry_override=card_entry,
                fortune_seed_key=f"{bind_key}:{dim}",
                render_scale=rs,
            )
            b64 = png_to_base64(png)
            b64 = _limit_image_base64_for_send(b64)
            await cmd.send_image(b64, set_reply=True, reply_message=reply_anchor)
        except Exception as re:
            logger.warning(f"jrys_single: 出图失败，改发文字: {re}")
            await cmd.send_text(
                _safe_display_text(msg),
                set_reply=True,
                reply_message=reply_anchor,
            )
    except Exception as e:
        logger.exception(f"jrys_single: 失败 dim={dim}: {e}")
        try:
            await cmd.send_text(
                _safe_display_text(f"「{dim}」运势生成失败：{e}"),
                set_reply=True,
                reply_message=reply_anchor,
            )
        except Exception as send_e:
            logger.warning(f"jrys_single: 发送错误提示失败: {send_e}")
        return False, str(e), True

    logger.info(f"jrys_single: 已发送 dim={dim}（图片或文字回退）")
    return True, f"已发送今日{dim}运势图", True


class JrysSingleLuckKeywordCommand(BaseCommand):
    """「今日桃花」「今日财运」等：只算一项，单独发一条文字解签。"""

    command_name = "jrys_single_luck_keyword"
    command_description = "今日桃花/财运等：单项运势 PNG（独立触发）"
    command_pattern = _single_luck_command_pattern()
    command_help = (
        "消息含「今日桃花」「今日感情」「恋爱运势」「工作运势」「事业运势」「学业运势」"
        "「今日财运」「健康运势」「社交运势」等之一时触发（不含「今日运势」四字）；"
        "若开启确认语会先引用你的消息再回一条；确认语、出图/文字均带引用，多人同时抽不易混。"
        "每次只生成该项签诗式断语+白话解签，单独发图片（与主卡同款卡片样式）。"
    )
    command_examples = ["今日桃花", "今日感情", "工作运势", "学业运势"]

    async def execute(self) -> Tuple[bool, str, bool]:
        return await _run_single_luck_dimension_for_message(self)


class JrysPrprCommand(BaseCommand):
    """今日运势：发一张 PNG 卡片；加 -s / --split 时先发文字摘要再发图。"""

    command_name = "jrys_prpr"
    command_description = "生成今日运势卡片（MaiBot 简化版，非 Koishi 插件）"
    command_pattern = r"^/?jrysprpr\s*(?P<rest>.*)$"
    command_help = (
        "jrysprpr 出简卡（总签+解签）；jrysprpr 详 / -d 带桃花财运等分项并重新解签；"
        "-s 先发文字摘要；回复均引用你触发命令的那条消息（含确认语与出图）。"
    )
    command_examples = ["jrysprpr", "jrysprpr 详", "jrysprpr -d -s", "/jrysprpr"]

    async def execute(self) -> Tuple[bool, str, bool]:
        rest = str(self.matched_groups.get("rest") or "").strip()
        split, detail = _parse_jrysprpr_extra(rest)
        return await _run_jrys_for_message(
            self, split=split, use_llm=True, include_sub_luck=detail
        )


class JrysTodayKeywordCommand(BaseCommand):
    """消息中含「今日运势」时触发（整段文本匹配，与 jrysprpr 共用生成逻辑）。"""

    command_name = "jrys_today_keyword"
    command_description = "关键词「今日运势」等触发生成运势卡片"
    command_pattern = r"^[\s\S]{0,800}今日运势[\s\S]{0,800}$"
    command_help = (
        "「今日运势」出简卡；「今日运势详」「今日运势详细」「分项运势」出带分项的详卡并重新解签；"
        "回复均引用触发消息。"
    )
    command_examples = ["今日运势", "今日运势详", "分项运势"]

    async def execute(self) -> Tuple[bool, str, bool]:
        text = getattr(self.message, "processed_plain_text", None) or ""
        split = bool(re.search(r"(?:^|[\s,，;；])(-s|--split)(?:$|[\s,，;；])", text))
        detail = _keyword_requests_detail_luck(text)
        return await _run_jrys_for_message(
            self, split=split, use_llm=True, include_sub_luck=detail
        )


@register_plugin
class JrysPrprMaimbotPlugin(BasePlugin):
    """今日运势（MaiBot / NapCat 用；与 Koishi 的 koishi-plugin-jrys-prpr 不是同一实现）"""

    plugin_name = "jrys_prpr_maimbot"
    plugin_description = (
        "今日运势：同日总签入库；主卡与分项关键字均出图；详版卡与分项触发各自独立（DeepSeek 等）；"
        "群聊下确认语与结果均引用用户触发消息，避免多人同时抽时串台。"
    )
    plugin_version = "1.5.5"
    plugin_author = "MaiM fork"
    enable_plugin = True
    config_file_name = "config.toml"
    dependencies: List[str] = []
    python_dependencies: List[str] = []

    config_section_descriptions = {
        "plugin": "总开关",
        "card": "卡片尺寸（像素）；长解签时高度会自动加大，直至上限",
        "llm": "占卜相关大模型（model_config.toml → jrys_fortune）",
        "confirm": "收到占卜请求后先发的确认语（总签与分项均会发；口吻模板随机）",
    }

    config_schema = {
        "plugin": {
            "enabled": ConfigField(type=bool, default=True, description="是否启用本插件"),
        },
        "card": {
            "width": ConfigField(type=int, default=480, description="卡片宽度"),
            "height": ConfigField(type=int, default=640, description="卡片最小高度（解签过长时会增高）"),
        },
        "llm": {
            "enabled": ConfigField(
                type=bool,
                default=True,
                description="是否调用大模型；关闭则仅用本地 fortune_quotes.json（不写签表）",
            ),
        },
        "confirm": {
            "enabled": ConfigField(
                type=bool,
                default=True,
                description="是否在抽牌/出图前先发送一条随机确认消息（今日总签与今日桃花等分项均适用）",
            ),
            "self_name": ConfigField(
                type=str,
                default="君君",
                description="确认语模板里的自称 {name}；留空则尝试用 bot_config 里的机器人昵称",
            ),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return [
            (JrysPrprCommand.get_command_info(), JrysPrprCommand),
            (JrysSingleLuckKeywordCommand.get_command_info(), JrysSingleLuckKeywordCommand),
            (JrysTodayKeywordCommand.get_command_info(), JrysTodayKeywordCommand),
        ]
