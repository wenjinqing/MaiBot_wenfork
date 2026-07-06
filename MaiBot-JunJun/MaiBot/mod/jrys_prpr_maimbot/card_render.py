"""用 Pillow 生成「今日运势」卡片：按运势内容配色 + 程序化装饰（无外链素材）。"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from PIL import Image, ImageDraw, ImageFont


def _load_quotes(plugin_dir: str) -> Dict[str, Any]:
    p = Path(plugin_dir) / "fortune_quotes.json"
    if not p.is_file():
        return {
            "disclaimer": "仅供娱乐",
            "entries": [{"title": "吉", "line": "今天也会是不错的一天。", "stars": 3}],
        }
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def _pick_entry(data: Dict[str, Any], seed: str) -> Dict[str, Any]:
    entries = data.get("entries") or []
    if not entries:
        return {"title": "?", "line": "暂无运势文案。", "stars": 3}
    rng = random.Random(seed)
    return dict(rng.choice(entries))


def _star_bar(n: int) -> str:
    """总运 0～5 星；0 为全空星（大凶）。"""
    n = max(0, min(5, int(n)))
    if n <= 0:
        return "☆" * 5
    return "★" * n + "☆" * (5 - n)


_LUCK_ORDER_DISPLAY: Tuple[str, ...] = ("桃花", "财运", "仕途", "健康", "人缘")


def _luck_lines_for_card(luck: Any) -> List[str]:
    if not isinstance(luck, dict) or not luck:
        return []
    segs: List[str] = []
    for k in _LUCK_ORDER_DISPLAY:
        if k not in luck:
            continue
        try:
            n = max(1, min(5, int(luck[k])))
        except (TypeError, ValueError):
            continue
        segs.append(f"{k}{_star_bar(n)}")
    if not segs:
        return []
    mid = (len(segs) + 1) // 2
    return ["  ".join(segs[:mid]), "  ".join(segs[mid:])]


def _luck_summary_suffix(luck: Any) -> str:
    if not isinstance(luck, dict) or not luck:
        return ""
    parts: List[str] = []
    for k in _LUCK_ORDER_DISPLAY:
        if k not in luck:
            continue
        try:
            parts.append(f"{k}{int(luck[k])}")
        except (TypeError, ValueError):
            continue
    return (" | " + " ".join(parts)) if parts else ""


def pick_local_fortune_entry(plugin_dir: str, seed: str) -> Dict[str, Any]:
    """从本地 JSON 按 seed 稳定抽签（用于无库/无模型时的签文）。"""
    return _pick_entry(_load_quotes(plugin_dir), seed)


def _stable_digest(seed: str) -> bytes:
    return hashlib.sha256(seed.encode("utf-8")).digest()


def daily_jrrp_luck(bind_key: str, day_iso: str) -> int:
    """每日人品 1～99（与常见 jrrp 思路一致：用户绑定键 + 日期 → 固定值，不含 0）。"""
    d = _stable_digest(f"jrrp|v1|{day_iso}|{bind_key}")
    return 1 + (int.from_bytes(d[:4], "big") % 99)


# 总签档位：从差到好；人品 1～99 线性映射到索引（与 stars 列一致供卡片配色）
_TOTAL_LOT_TIERS: Tuple[Tuple[str, int], ...] = (
    ("大凶", 0),
    ("凶", 1),
    ("小凶", 2),
    ("末吉", 2),
    ("微末", 2),
    ("半吉", 3),
    ("吉", 3),
    ("小吉", 4),
    ("中吉", 4),
    ("大吉", 5),
    ("上吉", 5),
    ("特吉", 5),
)


def local_fallback_line_for_title(plugin_dir: str, title: str) -> str:
    """按签档标题取 fortune_quotes.json 中的默认短句（与星级一致）。"""
    t = str(title or "").strip()
    for e in (_load_quotes(plugin_dir).get("entries") or []):
        if str(e.get("title", "")).strip() == t:
            return str(e.get("line", "") or "").strip()
    return ""


def draw_daily_lot_from_seed(*, plugin_dir: str, bind_key: str, day_iso: str) -> Dict[str, Any]:
    """
    本地抽签：人品 1～99 均匀映射到多档总签（签档 + 星级），默认短句来自 fortune_quotes.json。
    大模型不参与 TITLE/STARS，仅可用于后续解签。
    """
    jrrp = daily_jrrp_luck(bind_key, day_iso)
    n = len(_TOTAL_LOT_TIERS)
    idx = min(n - 1, (jrrp - 1) * n // 99)
    title, stars = _TOTAL_LOT_TIERS[idx]
    stars = max(0, min(5, int(stars)))

    local_line = local_fallback_line_for_title(plugin_dir, title)
    if not local_line:
        entries = _load_quotes(plugin_dir).get("entries") or []

        def _entry_stars(e: Dict[str, Any]) -> int:
            return max(0, min(5, int(e.get("stars", 0) or 0)))

        subs = [e for e in entries if _entry_stars(e) == stars]
        if subs:
            pick_seed = f"jrys-lot|v2|{day_iso}|{bind_key}|i{idx}"
            h2 = int.from_bytes(_stable_digest(pick_seed)[:4], "big")
            e = subs[h2 % len(subs)]
            local_line = str(e.get("line", "") or "").strip()
    if not local_line:
        local_line = "今天也会是不错的一天。"

    return {
        "title": str(title)[:12],
        "stars": stars,
        "jrrp": jrrp,
        "local_line": local_line,
    }


def _safe_display_text(s: str) -> str:
    """避免非法 Unicode 导致下游 UTF-8 / 字体渲染异常。"""
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    return s.encode("utf-8", errors="replace").decode("utf-8")


def _wrap_text_to_lines(
    text: str,
    draw: ImageDraw.ImageDraw,
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
    max_w: int,
) -> List[str]:
    words = list(text or "")
    lines: List[str] = []
    buf = ""
    for ch in words:
        test = buf + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w:
            buf = test
        else:
            if buf:
                lines.append(buf)
            buf = ch
    if buf:
        lines.append(buf)
    return lines


def _body_line_height(
    draw: ImageDraw.ImageDraw,
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
    *,
    scale: int = 1,
    pad: int = 8,
) -> int:
    bb = draw.textbbox((0, 0), "国国Ay", font=font)
    p = max(1, int(round(pad * scale)))
    return max(20 * scale, bb[3] - bb[1] + p)


def _truncate_to_width(
    draw: ImageDraw.ImageDraw,
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
    text: str,
    max_w: int,
) -> str:
    ell = "…"
    if draw.textbbox((0, 0), text, font=font)[2] - draw.textbbox((0, 0), text, font=font)[0] <= max_w:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        cand = text[:mid] + ell
        if draw.textbbox((0, 0), cand, font=font)[2] - draw.textbbox((0, 0), cand, font=font)[0] <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo] + ell) if lo > 0 else ell


def _lerp_rgb(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


@dataclass(frozen=True)
class _Palette:
    top: Tuple[int, int, int]
    mid: Tuple[int, int, int]
    bottom: Tuple[int, int, int]
    accent: Tuple[int, int, int]
    accent_soft: Tuple[int, int, int]
    orb: Tuple[int, int, int, int]
    line_gold: Tuple[int, int, int, int]
    panel_fill: Tuple[int, int, int, int]
    panel_outline: Tuple[int, int, int, int]
    text_title: Tuple[int, int, int]
    text_head: Tuple[int, int, int]
    text_body: Tuple[int, int, int]
    text_muted: Tuple[int, int, int]
    text_disclaimer: Tuple[int, int, int]


def _palette_for_fortune(title: str, stars: int, decor_seed: str) -> _Palette:
    """根据签档标题与星级选配色；大凶为 0 星专用暮色主题。"""
    t = (title or "").strip()
    raw = int(stars)
    if t == "大凶" or raw <= 0:
        return _Palette(
            top=(240, 232, 255),
            mid=(198, 172, 235),
            bottom=(108, 62, 98),
            accent=(210, 52, 88),
            accent_soft=(255, 175, 155),
            orb=(255, 220, 235, 38),
            line_gold=(255, 200, 210, 200),
            panel_fill=(255, 252, 255, 236),
            panel_outline=(255, 245, 250, 165),
            text_title=(78, 38, 92),
            text_head=(92, 48, 108),
            text_body=(48, 36, 64),
            text_muted=(118, 88, 132),
            text_disclaimer=(132, 102, 120),
        )

    stars = max(1, min(5, raw))
    if t in ("凶", "小凶"):
        mood = "dusty_rose"
    elif t in ("末吉", "微末"):
        mood = "lavender"
    elif t in ("大吉", "上吉", "特吉", "超吉"):
        mood = "dawn_gold"
    elif t in ("中吉", "小吉"):
        mood = "spring"
    elif t in ("半吉", "吉"):
        mood = "sea_glass"
    elif (("凶" in t) and ("吉" not in t) and ("半" not in t)) or ("大凶" in t):
        mood = "plum_soft"
    elif any(k in t for k in ("大吉", "上吉", "特吉", "祥", "昌")):
        mood = "dawn_gold"
    elif any(k in t for k in ("中吉", "小吉", "顺")):
        mood = "spring"
    elif stars >= 5:
        mood = "dawn_gold"
    elif stars == 4:
        mood = "spring"
    elif stars <= 2:
        mood = "dusty_rose"
    else:
        r = random.Random(decor_seed)
        mood = r.choice(["lavender", "sea_glass", "spring"])

    if mood == "dawn_gold":
        return _Palette(
            top=(255, 248, 232),
            mid=(255, 214, 168),
            bottom=(242, 158, 108),
            accent=(188, 72, 38),
            accent_soft=(255, 205, 140),
            orb=(255, 255, 250, 46),
            line_gold=(255, 195, 110, 215),
            panel_fill=(255, 255, 255, 84),
            panel_outline=(255, 245, 220, 135),
            text_title=(118, 52, 28),
            text_head=(98, 48, 32),
            text_body=(62, 40, 32),
            text_muted=(128, 88, 62),
            text_disclaimer=(155, 108, 78),
        )
    if mood == "spring":
        return _Palette(
            top=(232, 255, 248),
            mid=(185, 232, 255),
            bottom=(138, 198, 242),
            accent=(42, 118, 148),
            accent_soft=(120, 210, 200),
            orb=(240, 255, 255, 48),
            line_gold=(160, 225, 255, 195),
            panel_fill=(255, 255, 255, 82),
            panel_outline=(230, 250, 255, 128),
            text_title=(28, 92, 108),
            text_head=(32, 82, 102),
            text_body=(36, 62, 82),
            text_muted=(68, 108, 125),
            text_disclaimer=(88, 125, 142),
        )
    if mood == "sea_glass":
        return _Palette(
            top=(228, 246, 255),
            mid=(175, 218, 248),
            bottom=(118, 188, 232),
            accent=(52, 98, 168),
            accent_soft=(118, 185, 228),
            orb=(255, 255, 255, 44),
            line_gold=(185, 218, 255, 185),
            panel_fill=(255, 255, 255, 80),
            panel_outline=(220, 238, 255, 128),
            text_title=(38, 72, 128),
            text_head=(34, 68, 118),
            text_body=(34, 58, 92),
            text_muted=(72, 102, 138),
            text_disclaimer=(92, 120, 152),
        )
    if mood == "lavender":
        return _Palette(
            top=(248, 238, 255),
            mid=(218, 188, 250),
            bottom=(175, 145, 225),
            accent=(108, 62, 155),
            accent_soft=(205, 155, 245),
            orb=(255, 250, 255, 46),
            line_gold=(235, 200, 255, 200),
            panel_fill=(255, 255, 255, 82),
            panel_outline=(248, 235, 255, 130),
            text_title=(88, 48, 125),
            text_head=(78, 44, 112),
            text_body=(58, 40, 92),
            text_muted=(108, 78, 135),
            text_disclaimer=(125, 98, 148),
        )
    if mood == "dusty_rose":
        return _Palette(
            top=(255, 236, 244),
            mid=(248, 192, 212),
            bottom=(225, 148, 178),
            accent=(150, 48, 88),
            accent_soft=(255, 168, 195),
            orb=(255, 255, 255, 40),
            line_gold=(255, 190, 210, 175),
            panel_fill=(255, 255, 255, 84),
            panel_outline=(255, 235, 245, 125),
            text_title=(125, 42, 72),
            text_head=(110, 40, 68),
            text_body=(82, 36, 58),
            text_muted=(128, 78, 98),
            text_disclaimer=(142, 92, 112),
        )
    return _Palette(
        top=(248, 232, 255),
        mid=(215, 182, 245),
        bottom=(175, 138, 218),
        accent=(95, 48, 135),
        accent_soft=(215, 160, 245),
        orb=(255, 248, 255, 44),
        line_gold=(235, 190, 255, 190),
        panel_fill=(255, 255, 255, 80),
        panel_outline=(255, 248, 255, 128),
        text_title=(82, 42, 118),
        text_head=(72, 38, 105),
        text_body=(52, 34, 88),
        text_muted=(102, 72, 128),
        text_disclaimer=(118, 88, 142),
    )


def _draw_background_gradient(img: Image.Image, pal: _Palette) -> None:
    """四段纵向渐变 + 轻微对角浸色，背景更有层次。"""
    w, h = img.size
    draw = ImageDraw.Draw(img)
    c_tm = _lerp_rgb(pal.top, pal.mid, 0.42)
    c_mb = _lerp_rgb(pal.mid, pal.bottom, 0.48)
    for y in range(h):
        t = y / max(h - 1, 1)
        if t < 1 / 3:
            c = _lerp_rgb(pal.top, c_tm, t * 3)
        elif t < 2 / 3:
            c = _lerp_rgb(c_tm, c_mb, (t - 1 / 3) * 3)
        else:
            c = _lerp_rgb(c_mb, pal.bottom, (t - 2 / 3) * 3)
        draw.line([(0, y), (w - 1, y)], fill=c)
    # 对角暖/冷叠色（低透明度）
    over = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    diag = [
        (-w // 4, h + h // 6),
        (w + w // 6, -h // 8),
        (w + w // 4, h // 3),
        (w // 8, h + h // 4),
    ]
    od.polygon(diag, fill=(*pal.accent_soft[:3], 22))
    od.polygon(
        [(-30, -30), (w // 2 + 40, h // 3), (-40, h // 2)],
        fill=(*pal.accent[:3], 14),
    )
    blended = Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")
    img.paste(blended, (0, 0))


def _norm_ellipse_box(x0: int, y0: int, x1: int, y1: int) -> Tuple[int, int, int, int]:
    """Pillow 要求椭圆/弧 bbox 满足 x0<=x1、y0<=y1。"""
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    return (x0, y0, x1, y1)


def _draw_decor_layer(
    size: Tuple[int, int], pal: _Palette, rng: random.Random, *, scale: int = 1
) -> Image.Image:
    """程序化装饰：双色边条、多光斑、斜向光带、微粒、星光与角弧。"""
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    sc = max(1, int(scale))

    # 左侧双色条
    stripe = max(2, min(16, int(3 * sc)))
    for x in range(stripe):
        a1 = max(0, int(58 - x * 12))
        d.line([(x, 0), (x, h - 1)], fill=(*pal.accent_soft[:3], a1))
    stripe2 = max(1, stripe - 4)
    for x in range(stripe2):
        a2 = max(0, int(36 - x * 10))
        ox = w - 1 - x
        d.line([(ox, 0), (ox, h - 1)], fill=(*pal.accent[:3], a2))

    # 大光斑（角 + 中下氛围）
    orbs = [
        _norm_ellipse_box(-w // 4, -h // 5, w // 2 + 24, h // 2 + 28),
        _norm_ellipse_box(int(w * 0.36), -h // 5, w + w // 6, int(h * 0.55)),
        _norm_ellipse_box(-w // 8, int(h * 0.42), int(w * 0.78), h + h // 6),
        _norm_ellipse_box(int(w * 0.2), int(h * 0.55), int(w * 0.85), h + h // 5),
    ]
    for box in orbs:
        d.ellipse(box, fill=pal.orb)

    # 底部大柔光（主色浸染）
    d.ellipse(
        _norm_ellipse_box(int(-w * 0.15), int(h * 0.35), int(w * 1.12), int(h * 1.08)),
        fill=(*pal.bottom[:3], 26),
    )

    # 斜向柔光带
    d.polygon(
        [(-40, h // 3), (w // 2, -20), (w + 40, h // 4), (w // 3, h + 50)],
        fill=(*pal.mid, 24),
    )
    d.polygon(
        [(w + 20, h // 2), (w // 3, h + 30), (-20, h - h // 5)],
        fill=(*pal.accent_soft[:3], 18),
    )

    # 细网格点
    step = max(14, int(20 * sc / 2))
    for gx in range(step, w, step):
        for gy in range(step, h, step):
            if rng.random() < 0.28:
                d.ellipse(
                    (gx - 1, gy - 1, gx + 2, gy + 2),
                    fill=(*pal.accent_soft[:3], 20),
                )

    # 散景圆（少而大）
    for _ in range(4):
        hi = max(20, min(w, h) // 4)
        rr = rng.randint(14, max(15, hi))
        rr = min(rr, w // 2 - 6, h // 2 - 6)
        if rr < 10:
            continue
        cx = rng.randint(rr, w - rr)
        cy = rng.randint(rr, h - rr)
        bb = _norm_ellipse_box(cx - rr, cy - rr, cx + rr, cy + rr)
        d.ellipse(bb, fill=(*pal.accent_soft[:3], rng.randint(12, 22)))

    # 小星星
    for _ in range(26):
        cx = rng.randint(8, w - 8)
        cy = rng.randint(8, h - 8)
        s = rng.choice([3, 4, 5])
        a = rng.randint(38, 92)
        col = (255, 255, 255, a)
        for dx, dy in ((0, -s), (0, s), (-s, 0), (s, 0)):
            d.line([(cx + dx, cy + dy), (cx, cy)], fill=col, width=1)

    arc_w, arc_h = min(w, h) // 2, min(w, h) // 2
    aw = max(2, int(round(2.5 * sc)))
    d.arc(
        (-arc_w // 3, -arc_h // 3, arc_w, arc_h),
        start=0,
        end=90,
        fill=(*pal.accent[:3], 52),
        width=aw,
    )
    d.arc(
        (w - arc_w, h - arc_h, w + arc_w // 4, h + arc_h // 4),
        start=180,
        end=270,
        fill=(*pal.accent[:3], 46),
        width=aw,
    )

    return layer


def _composite_under_text(base_rgb: Image.Image, decor: Image.Image) -> Image.Image:
    base = base_rgb.convert("RGBA")
    return Image.alpha_composite(base, decor).convert("RGB")


def render_fortune_png(
    *,
    plugin_dir: str,
    user_name: str,
    width: int = 480,
    height: int = 640,
    entry_override: Dict[str, Any] | None = None,
    fortune_seed_key: str | None = None,
    render_scale: int = 2,
) -> Tuple[bytes, str]:
    """
    在 width/height 为「输出逻辑像素」的前提下，用 render_scale 在内部放大绘制再缩小，
    减轻客户端放大查看时的发糊；无矢量字体时自动退回 scale=1。

    Returns:
        png_bytes, plain_summary  (plain_summary 用于 -s 模式先发文字)
    """
    user_name = _safe_display_text(str(user_name or ""))
    data = _load_quotes(plugin_dir)
    seed_tail = fortune_seed_key if (fortune_seed_key or "").strip() else user_name
    day_key = f"{date.today().isoformat()}:{seed_tail}"
    if entry_override and str(entry_override.get("line", "")).strip():
        _lk = entry_override.get("luck")
        _verse = str(entry_override.get("verse") or "").strip()
        entry = {
            "title": str(entry_override.get("title", "吉")),
            "line": str(entry_override.get("line", "")).strip(),
            "stars": max(0, min(5, int(entry_override.get("stars", 3)))),
            "luck": _lk if isinstance(_lk, dict) else {},
            "verse": _verse,
            "header_title": str(entry_override.get("header_title") or "").strip(),
            "footer_note": str(entry_override.get("footer_note") or "").strip(),
        }
    else:
        entry = _pick_entry(data, day_key)
        entry.setdefault("header_title", "")
        entry.setdefault("footer_note", "")
    title = _safe_display_text(str(entry.get("title", "吉")))
    line = _safe_display_text(str(entry.get("line", "")))
    verse = _safe_display_text(str(entry.get("verse") or ""))
    stars = max(0, min(5, int(entry.get("stars", 3))))
    disclaimer = _safe_display_text(str(data.get("disclaimer", "仅供娱乐")))
    header_title = _safe_display_text(str(entry.get("header_title") or "").strip() or "今日运势")[:24]
    footer_note = _safe_display_text(str(entry.get("footer_note") or "").strip())

    decor_seed = f"{day_key}:{title}:{stars}"
    rng = random.Random(decor_seed)
    pal = _palette_for_fortune(title, stars, decor_seed)

    W0 = max(280, int(width))
    H0_min = max(400, int(height))
    scale_req = max(1, min(3, int(render_scale)))

    from os import environ

    windir = environ.get("WINDIR", "")
    msyh = (Path(windir) / "Fonts" / "msyh.ttc") if windir else Path("msyh.ttc")
    font_path = str(msyh) if msyh.is_file() else "msyh.ttc"
    try:
        ImageFont.truetype(font_path, 12)
        has_truetype = True
        s = scale_req
    except OSError:
        has_truetype = False
        s = 1

    def Z(n: Union[int, float]) -> int:
        return int(round(float(n) * s))

    w = W0 * s
    min_img_h = H0_min * s
    MAX_CARD_HEIGHT = Z(2200)
    footer_h = Z(56)
    max_w = max(80, w - Z(56))
    margin_x = Z(28)
    body_margin_x = Z(34)

    if has_truetype:

        def _body_font(sz: int) -> ImageFont.FreeTypeFont:
            return ImageFont.truetype(font_path, max(8, int(sz)))

        font_title = ImageFont.truetype(font_path, max(10, Z(28)))
        font_small = ImageFont.truetype(font_path, max(8, Z(14)))
        font_rank = ImageFont.truetype(font_path, max(12, Z(32)))
        font_header = ImageFont.truetype(font_path, max(9, Z(18)))
        font_star = ImageFont.truetype(font_path, max(10, Z(20)))
        font_luck = ImageFont.truetype(font_path, max(8, Z(13)))
        font_verse = ImageFont.truetype(font_path, max(9, Z(16)))
    else:

        def _body_font(sz: int) -> ImageFont.ImageFont:
            return ImageFont.load_default()

        font_title = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_rank = font_title
        font_header = font_title
        font_star = font_title
        font_luck = font_small
        font_verse = font_small

    scratch = Image.new("RGB", (w, Z(800)), (255, 255, 255))
    md = ImageDraw.Draw(scratch)
    star_y = Z(200)
    star_text = _star_bar(stars)
    sb = md.textbbox((0, 0), star_text, font=font_star)
    luck_lines = _luck_lines_for_card(entry.get("luck"))
    verse_lines: List[str] = (
        _wrap_text_to_lines(verse.strip(), md, font_verse, max_w) if verse.strip() else []
    )
    # 与绘制顺序一致：星级下 → 分项 → 签诗 → 白话正文
    cursor_y = star_y + (sb[3] - sb[1]) + Z(8)
    for lln in luck_lines:
        lb = md.textbbox((0, 0), lln, font=font_luck)
        cursor_y += lb[3] - lb[1] + Z(5)
    if luck_lines:
        cursor_y += Z(8)
    for vln in verse_lines:
        vb = md.textbbox((0, 0), vln, font=font_verse)
        cursor_y += vb[3] - vb[1] + Z(4)
    if verse_lines:
        cursor_y += Z(10)
    line_start_y = cursor_y

    body_lines: List[str]
    line_height: int
    font_body: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]
    img_h: int

    if has_truetype:
        chosen: Tuple[List[str], int, int, int] | None = None
        for fs in range(18, 10, -1):
            px = max(8, Z(fs))
            fb = _body_font(px)
            blines = _wrap_text_to_lines(line, md, fb, max_w)
            lh = _body_line_height(md, fb, scale=s, pad=9)
            need_h = line_start_y + len(blines) * lh + footer_h
            if need_h <= MAX_CARD_HEIGHT:
                chosen = (blines, lh, fs, max(min_img_h, need_h))
                break
        if chosen is None:
            fs = 11
            px = max(8, Z(fs))
            fb = _body_font(px)
            blines = _wrap_text_to_lines(line, md, fb, max_w)
            lh = _body_line_height(md, fb, scale=s, pad=9)
            cap_h = MAX_CARD_HEIGHT - line_start_y - footer_h
            max_lines = max(1, cap_h // lh)
            if len(blines) > max_lines:
                blines = blines[:max_lines]
                if blines:
                    blines[-1] = _truncate_to_width(md, fb, blines[-1], max_w)
            chosen = (blines, lh, fs, MAX_CARD_HEIGHT)
        body_lines, line_height, fs_used, img_h = chosen
        font_body = _body_font(max(8, Z(fs_used)))
    else:
        font_body = _body_font(12)
        body_lines = _wrap_text_to_lines(line, md, font_body, max_w)
        line_height = _body_line_height(md, font_body, scale=s, pad=9)
        need_h = line_start_y + len(body_lines) * line_height + footer_h
        img_h = max(min_img_h, min(need_h, MAX_CARD_HEIGHT))
        if need_h > MAX_CARD_HEIGHT:
            cap_h = MAX_CARD_HEIGHT - line_start_y - footer_h
            max_lines = max(1, cap_h // line_height)
            if len(body_lines) > max_lines:
                body_lines = body_lines[:max_lines]
                if body_lines:
                    body_lines[-1] = _truncate_to_width(md, font_body, body_lines[-1], max_w)
            img_h = MAX_CARD_HEIGHT

    base = Image.new("RGB", (w, img_h), pal.top)
    _draw_background_gradient(base, pal)
    decor = _draw_decor_layer((w, img_h), pal, rng, scale=s)
    img = _composite_under_text(base, decor)
    overlay = Image.new("RGBA", (w, img_h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    rule_y = Z(64)
    lw_rule = max(1, Z(2))
    od.line([(Z(20), rule_y), (w - Z(20), rule_y)], fill=pal.line_gold, width=lw_rule)
    panel_top = Z(120)
    panel_bottom = img_h - Z(52)
    if panel_bottom > panel_top + Z(44):
        od.rounded_rectangle(
            (Z(18), panel_top, w - Z(18), panel_bottom),
            radius=Z(22),
            fill=pal.panel_fill,
            outline=pal.panel_outline,
            width=max(1, Z(1)),
        )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    today = date.today().strftime("%Y-%m-%d")
    draw.text((margin_x, Z(24)), header_title, fill=pal.text_title, font=font_title)
    draw.text((margin_x, Z(70)), today, fill=pal.text_muted, font=font_small)
    draw.text((margin_x, Z(94)), user_name or "你", fill=pal.text_head, font=font_header)

    draw.text((margin_x + Z(1), Z(153)), title, fill=pal.accent_soft, font=font_rank)
    draw.text((margin_x, Z(152)), title, fill=pal.text_title, font=font_rank)
    draw.text((margin_x, star_y), star_text, fill=pal.accent, font=font_star)

    ly = star_y + (sb[3] - sb[1]) + Z(8)
    for lln in luck_lines:
        draw.text((margin_x, ly), lln, fill=pal.text_muted, font=font_luck)
        lb2 = draw.textbbox((0, 0), lln, font=font_luck)
        ly += lb2[3] - lb2[1] + Z(5)
    for vln in verse_lines:
        draw.text((body_margin_x - Z(4), ly), vln, fill=pal.text_head, font=font_verse)
        vb3 = draw.textbbox((0, 0), vln, font=font_verse)
        ly += vb3[3] - vb3[1] + Z(4)
    if verse_lines:
        ly += Z(10)

    y = ly
    for ln in body_lines:
        draw.text((body_margin_x, y), ln, fill=pal.text_body, font=font_body)
        y += line_height

    bottom_caption = (
        (footer_note + " ｜ " + disclaimer)[:120] if footer_note else disclaimer
    )
    draw.text(
        (margin_x, img_h - Z(44)),
        bottom_caption,
        fill=pal.text_disclaimer,
        font=font_small,
    )

    out_w = W0
    out_h = max(H0_min, int(round(img_h / s)))
    if s > 1:
        try:
            _down = Image.Resampling.LANCZOS
        except AttributeError:
            _down = Image.LANCZOS  # type: ignore[attr-defined]
        img = img.resize((out_w, out_h), _down)

    bio = io.BytesIO()
    img.save(bio, format="PNG", optimize=True, compress_level=6)
    png = bio.getvalue()
    verse_bit = f"{verse.strip()} " if verse.strip() else ""
    summary = f"【{title}】{_star_bar(stars)}{_luck_summary_suffix(entry.get('luck'))} {verse_bit}{line}"
    return png, summary


def png_to_base64(png: bytes) -> str:
    return base64.b64encode(png).decode("ascii")
