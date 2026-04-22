# -*- coding: utf-8 -*-
"""抖音分享链接解析：调用星知阁 API，发送图集或视频摘要（QQ 侧视频直链默认以文字发送，见 send.qq_video_as_text_link）。"""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Type

import aiohttp
from maim_message import Seg

from src.chat.message_receive.chat_stream import get_chat_manager
from src.chat.message_receive.message import MessageRecv
from src.common.logger import get_logger
from src.config.config import global_config
from src.plugin_system import (
    BaseCommand,
    BaseEventHandler,
    BasePlugin,
    ComponentInfo,
    ConfigField,
    EventType,
    MaiMessages,
    register_plugin,
    send_api,
)

logger = get_logger("douyin_video_plugin")

# 解析前确认语（短句，随机一条；与 jrys 类似便于群内对应触发消息）
_DOUYIN_CONFIRM_TEMPLATES: Tuple[str, ...] = (
    "收到，正在帮你解析这条抖音…",
    "抖音链接我看到了，稍等片刻～",
    "在扒视频/图集了，别走开。",
    "解析接口走一趟，马上回来。",
    "链接已丢进解析器，等我一下。",
    "正在拉取抖音内容，网络慢的话要多等几秒。",
    "好嘞，这条抖音我去拆一下。",
    "收到抖音分享，解析中…",
    "稍等，正在把链接换成能发的视频/图。",
    "已排队解析，马上出结果。",
    "抖音解析开工，先喝口水等我。",
    "链接有效，正在请求解析服务。",
    "在努力了，解析完就发你。",
    "已收到链接，正在向解析站要数据。",
    "这条抖音我接手了，解析中。",
    "稍候，正在下载元数据与媒体地址。",
)


def _pick_douyin_confirm() -> str:
    return random.choice(_DOUYIN_CONFIRM_TEMPLATES)


def _reply_anchor_from_mai(message: Optional[MaiMessages]) -> Optional[MessageRecv]:
    """从当前聊天流上下文取入站 MessageRecv，供引用回复（与命令路径 self.message 一致）。"""
    if not message or not message.stream_id:
        return None
    try:
        stream = get_chat_manager().get_stream(message.stream_id)
        if stream and stream.context:
            return stream.context.get_last_message()
    except Exception as e:
        logger.debug(f"douyin: 无法获取引用锚点: {e}")
    return None


# 常见抖音分享/详情链接（短链 path 常含 - _，如 v.douyin.com/UW8-u_REUP8/）
DOUYIN_URL_RE = re.compile(
    r"https?://(?:"
    r"v\.douyin\.com/[A-Za-z0-9._~-]+/?|"
    r"(?:www\.)?douyin\.com/video/\d+[^ \t\n\r\f\v\u200b]*|"
    r"(?:www\.)?douyin\.com/note/[A-Za-z0-9._~-]+[^ \t\n\r\f\v\u200b]*"
    r")",
    re.IGNORECASE,
)

_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 MaiBot-Douyin/1.0",
    "Accept": "application/json,text/plain,*/*",
}


def _first_douyin_url(text: str) -> Optional[str]:
    if not text:
        return None
    m = DOUYIN_URL_RE.search(text)
    return m.group(0).rstrip(".,;!?，。；！？）】>") if m else None


def _is_short_douyin(url: str) -> bool:
    return bool(url and re.search(r"v\.douyin\.com/", url, re.I))


async def expand_douyin_share_url(
    share_url: str,
    *,
    connect_timeout_sec: int = 30,
    proxy: Optional[str] = None,
) -> str:
    """将 v.douyin.com 短链展开为落地页 URL；部分解析站对短链报「资源id获取失败」。"""
    if not _is_short_douyin(share_url):
        return share_url
    conn_t = max(int(connect_timeout_sec or 30), 15)
    timeout = aiohttp.ClientTimeout(total=conn_t + 45, connect=conn_t, sock_connect=conn_t, sock_read=conn_t)
    proxy = (proxy or "").strip() or None
    try:
        connector = aiohttp.TCPConnector(ssl=True, limit=5)
        async with aiohttp.ClientSession(headers=_HTTP_HEADERS, connector=connector) as session:
            async with session.get(
                share_url,
                allow_redirects=True,
                timeout=timeout,
                proxy=proxy,
            ) as resp:
                final = str(resp.url)
                if "douyin.com" in final and "v.douyin.com" not in final:
                    # 去掉查询串里易过期的 token，保留主路径
                    base = final.split("?", 1)[0].split("#", 1)[0]
                    logger.info(f"抖音短链已展开: {share_url[:48]}... -> {base[:96]}...")
                    return base
    except Exception as e:
        logger.debug(f"抖音短链展开失败，仍用原链请求解析接口: {e}")
    return share_url


def _unwrap_payload(root: dict) -> dict:
    """兼容 { data: { item, stat } } 与顶层即 item/stat。"""
    if not isinstance(root, dict):
        return {}
    if "item" in root or "stat" in root or "jx" in root:
        return root
    inner = root.get("data")
    if isinstance(inner, dict):
        if "item" in inner or "stat" in inner or "jx" in inner:
            return inner
        deeper = inner.get("data")
        if isinstance(deeper, dict):
            return deeper
    return root


def _msg_suggests_parse_ok(msg: str) -> bool:
    """部分镜像站返回的 code 与 msg 不一致（如 code≠200 但 msg 为「解析成功」），以文案为准。"""
    if not msg:
        return False
    if "解析失败" in msg or "未能解析" in msg or "无法解析" in msg:
        return False
    return "解析成功" in msg


def _api_success(root: dict) -> bool:
    if not isinstance(root, dict):
        return False
    msg = str(root.get("msg") or root.get("message") or "")
    if _msg_suggests_parse_ok(msg):
        return True
    if root.get("success") is True:
        return True
    if "code" not in root:
        return True
    c = root.get("code")
    try:
        return int(c) == 200
    except (TypeError, ValueError):
        s = str(c).strip().lower()
        return s in ("200", "ok", "success")


def _has_sendable_media(item: Optional[dict]) -> bool:
    if not item:
        return False
    u = item.get("url")
    if isinstance(u, str) and u.startswith("http"):
        return True
    return bool(_image_urls_from_item(item))


def _extract_item_stat(jx_root: dict) -> Tuple[dict, dict, list]:
    stat = jx_root.get("stat") if isinstance(jx_root.get("stat"), dict) else {}
    item = jx_root.get("item") if isinstance(jx_root.get("item"), dict) else {}
    jx = jx_root.get("jx")
    if not isinstance(jx, list):
        jx = []
    return stat, item, jx


def _resolve_item_stat(inner: dict) -> Tuple[dict, dict]:
    """从根对象或 jx[0] 等位置取出 item/stat。"""
    stat, item, jx = _extract_item_stat(inner)
    if item:
        return stat, item
    for entry in jx:
        if not isinstance(entry, dict):
            continue
        sub_item = entry.get("item")
        if isinstance(sub_item, dict):
            sub_stat = entry.get("stat") if isinstance(entry.get("stat"), dict) else stat
            return sub_stat, sub_item
        if entry.get("url") or _image_urls_from_item(entry):
            sub_stat = entry.get("stat") if isinstance(entry.get("stat"), dict) else stat
            return sub_stat, entry
    return stat, item


def _image_urls_from_item(item: dict) -> List[str]:
    raw = item.get("images")
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for x in raw:
        if isinstance(x, str) and x.startswith("http"):
            out.append(x)
        elif isinstance(x, dict):
            u = x.get("url") or x.get("src") or x.get("image")
            if isinstance(u, str) and u.startswith("http"):
                out.append(u)
    return out


def _plain_has_at_bot(plain: str) -> bool:
    q = str(getattr(global_config.bot, "qq_account", "") or "")
    if not q:
        return True
    return f"[CQ:at,qq={q}]" in (plain or "")


async def fetch_douyin_parse(
    base_url: str,
    share_url: str,
    *,
    read_timeout_sec: int = 300,
    connect_timeout_sec: int = 90,
    retries: int = 2,
    proxy: Optional[str] = None,
) -> dict:
    """请求解析接口，返回完整 JSON 对象。连接/读超时加大，支持代理与重试。"""
    read_t = max(int(read_timeout_sec or 300), 60)
    conn_t = max(int(connect_timeout_sec or 90), 30)
    # total 放宽，避免读阶段被整体上限误杀
    timeout = aiohttp.ClientTimeout(
        total=read_t + conn_t + 120,
        connect=conn_t,
        sock_connect=conn_t,
        sock_read=read_t,
    )
    api = base_url.rstrip("/") + "/"
    proxy = (proxy or "").strip() or None
    share_url = await expand_douyin_share_url(
        share_url, connect_timeout_sec=connect_timeout_sec, proxy=proxy
    )
    attempts = max(0, int(retries or 0)) + 1
    last_err: Optional[BaseException] = None
    text = ""

    connector = aiohttp.TCPConnector(ssl=True, limit=10)
    async with aiohttp.ClientSession(headers=_HTTP_HEADERS, connector=connector) as session:
        for attempt in range(attempts):
            use_post = attempt == attempts - 1 and attempts > 1
            try:
                if use_post:
                    async with session.post(
                        api,
                        data={"url": share_url},
                        timeout=timeout,
                        proxy=proxy,
                    ) as resp:
                        text = await resp.text()
                else:
                    async with session.get(
                        api,
                        params={"url": share_url},
                        timeout=timeout,
                        proxy=proxy,
                    ) as resp:
                        text = await resp.text()
                try:
                    return json.loads(text)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"解析接口返回非 JSON: {e}; 开头: {text[:200]!r}") from e
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_err = e
                logger.warning(
                    f"抖音解析接口请求失败 ({attempt + 1}/{attempts}): {e}"
                    + ("，将重试…" if attempt + 1 < attempts else "")
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(1.5 * (attempt + 1))
                continue

    raise RuntimeError(f"解析接口多次请求失败: {last_err}") from last_err


def _fetch_api_kwargs(get_config_fn) -> dict:
    """从插件配置构造 fetch_douyin_parse 参数。"""
    p = (get_config_fn("api.proxy", "") or "").strip()
    return {
        "read_timeout_sec": int(get_config_fn("api.timeout", 300)),
        "connect_timeout_sec": int(get_config_fn("api.connect_timeout", 90)),
        "retries": int(get_config_fn("api.retries", 2)),
        "proxy": p if p else None,
    }


async def send_parsed_content(
    stream_id: str,
    stat: dict,
    item: dict,
    *,
    send_summary: bool,
    max_gallery: int,
    reply_anchor: Optional[MessageRecv] = None,
    qq_video_as_text_link: bool = True,
) -> None:
    title = (item.get("title") or item.get("desc") or "抖音").strip()
    like = stat.get("like", "—")
    comment = stat.get("comment", "—")
    collect = stat.get("collect", "—")
    share = stat.get("share", "—")

    summary: Optional[str] = None
    if send_summary:
        summary = f"{title}\n❤️{like}  💬{comment}  ⭐{collect}  ↗️{share}"

    use_reply = bool(reply_anchor)
    video_url = item.get("url")
    if isinstance(video_url, str) and video_url.startswith("http"):
        # QQ/NapCat 的 video 段通常不接受抖音 CDN 的 http 直链，易发送失败；默认改为正文里发直链。
        if qq_video_as_text_link:
            link_line = f"📎 视频：{video_url}"
            body = f"{summary}\n{link_line}" if summary else link_line
            await send_api.text_to_stream(
                body,
                stream_id,
                storage_message=True,
                set_reply=use_reply,
                reply_message=reply_anchor if use_reply else None,
            )
            return
        # 摘要与视频合并为一条 seglist（仅当显式关闭 qq_video_as_text_link 时尝试 videourl）
        if summary:
            await send_api.hybrid_to_stream(
                [Seg(type="text", data=summary), Seg(type="videourl", data=video_url)],
                stream_id,
                storage_message=True,
                set_reply=use_reply,
                reply_message=reply_anchor if use_reply else None,
            )
        else:
            await send_api.custom_to_stream(
                "videourl",
                video_url,
                stream_id,
                storage_message=True,
                set_reply=use_reply,
                reply_message=reply_anchor if use_reply else None,
            )
        return

    images = _image_urls_from_item(item)[: max(1, max_gallery)]
    if images:
        if summary:
            segs: List[Seg] = [Seg(type="text", data=summary)] + [
                Seg(type="imageurl", data=img) for img in images
            ]
            await send_api.hybrid_to_stream(
                segs,
                stream_id,
                storage_message=True,
                set_reply=use_reply,
                reply_message=reply_anchor if use_reply else None,
            )
        else:
            for img in images:
                await send_api.custom_to_stream(
                    "imageurl",
                    img,
                    stream_id,
                    storage_message=True,
                    set_reply=use_reply,
                    reply_message=reply_anchor if use_reply else None,
                )
    elif summary:
        await send_api.text_to_stream(
            summary,
            stream_id,
            storage_message=True,
            set_reply=use_reply,
            reply_message=reply_anchor if use_reply else None,
        )


class DouyinLinkEventHandler(BaseEventHandler):
    """自动识别消息中的抖音链接并解析发送。"""

    event_type = EventType.ON_MESSAGE
    handler_name = "douyin_link_handler"
    handler_description = "解析抖音分享链接并发送视频/图集（可选确认语；引用回复默认关）"
    intercept_message = True
    weight = 48

    _last_ts: Dict[str, float] = {}

    async def execute(
        self, message: MaiMessages | None
    ) -> Tuple[bool, bool, Optional[str], None, Optional[MaiMessages]]:
        try:
            if not message or not message.plain_text or not message.stream_id:
                return True, True, None, None, None

            reply_anchor = (
                _reply_anchor_from_mai(message)
                if self.get_config("behavior.reply_to_trigger", False)
                else None
            )

            share = _first_douyin_url(message.plain_text)
            if not share:
                return True, True, None, None, None

            group_at_only = self.get_config("behavior.group_at_only", False)
            if message.is_group_message and group_at_only and not _plain_has_at_bot(message.plain_text):
                return True, True, None, None, None

            stream_id = message.stream_id
            now = time.time()
            interval = float(self.get_config("behavior.min_interval_seconds", 3) or 0)
            last = DouyinLinkEventHandler._last_ts.get(stream_id, 0.0)
            if interval > 0 and now - last < interval:
                return True, True, None, None, None
            DouyinLinkEventHandler._last_ts[stream_id] = now

            if self.get_config("confirm.enabled", True):
                try:
                    await send_api.text_to_stream(
                        _pick_douyin_confirm(),
                        stream_id,
                        storage_message=True,
                        set_reply=bool(reply_anchor),
                        reply_message=reply_anchor,
                    )
                except Exception as e:
                    logger.debug(f"douyin 确认语发送跳过: {e}")

            base_url = self.get_config("api.base_url", "https://api.xingzhige.com/API/douyin/")
            kw = _fetch_api_kwargs(self.get_config)

            logger.info(f"抖音解析(自动): url={share[:80]}...")
            raw = await fetch_douyin_parse(base_url, share, **kw)
            inner = _unwrap_payload(raw)
            stat, item = _resolve_item_stat(inner)
            if not _api_success(raw) and not _has_sendable_media(item):
                msg = raw.get("msg") or raw.get("message") or str(raw)
                await send_api.text_to_stream(
                    f"❌ 抖音解析失败: {msg}",
                    stream_id,
                    storage_message=True,
                    set_reply=bool(reply_anchor),
                    reply_message=reply_anchor if reply_anchor else None,
                )
                return True, True, None, None, None

            if not _has_sendable_media(item):
                await send_api.text_to_stream(
                    "❌ 抖音解析成功但未返回可发送的视频或图集",
                    stream_id,
                    storage_message=True,
                    set_reply=bool(reply_anchor),
                    reply_message=reply_anchor if reply_anchor else None,
                )
                return True, True, None, None, None

            await send_parsed_content(
                stream_id,
                stat,
                item,
                send_summary=bool(self.get_config("send.send_summary_text", True)),
                max_gallery=int(self.get_config("send.max_gallery_images", 9)),
                reply_anchor=reply_anchor,
                qq_video_as_text_link=bool(self.get_config("send.qq_video_as_text_link", True)),
            )

            block = bool(self.get_config("behavior.block_ai_reply", True))
            return True, not block, "douyin_parsed", None, None

        except Exception as e:
            logger.error(f"抖音链接处理异常: {e}", exc_info=True)
            if message and message.stream_id:
                try:
                    ra = (
                        _reply_anchor_from_mai(message)
                        if self.get_config("behavior.reply_to_trigger", False)
                        else None
                    )
                    await send_api.text_to_stream(
                        f"❌ 抖音解析出错: {e}",
                        message.stream_id,
                        storage_message=True,
                        set_reply=bool(ra),
                        reply_message=ra,
                    )
                except Exception:
                    pass
            return True, True, str(e), None, None


class DouyinParseCommand(BaseCommand):
    """手动解析：/douyin <链接> 或 /抖音解析 <链接>"""

    command_name = "douyin_parse"
    command_description = "解析抖音分享链接并发送视频/图集"
    command_pattern = r"^/(douyin|抖音解析)(?:\s+(?P<url>\S+))?$"
    command_help = (
        "用法：/douyin <抖音分享链接>  或  /抖音解析 <链接>；"
        "可选确认语；若 behavior.reply_to_trigger=true 则确认语与结果引用触发消息。"
    )
    intercept_message = True

    async def execute(self) -> Tuple[bool, str, bool]:
        reply_anchor = self.message if self.get_config("behavior.reply_to_trigger", False) else None
        try:
            url = (self.matched_groups.get("url") or "").strip()
            if not url:
                await self.send_text(
                    "用法：/douyin <抖音链接>  或  /抖音解析 <链接>",
                    set_reply=bool(reply_anchor),
                    reply_message=reply_anchor,
                )
                return True, "提示用法", True

            if not DOUYIN_URL_RE.search(url):
                await self.send_text(
                    "请提供有效的抖音分享链接（如 v.douyin.com 或 douyin.com/video）",
                    set_reply=bool(reply_anchor),
                    reply_message=reply_anchor,
                )
                return False, "链接不匹配", True

            chat_stream = self.message.chat_stream
            if not chat_stream or not chat_stream.stream_id:
                await self.send_text(
                    "❌ 无法获取当前会话",
                    set_reply=bool(reply_anchor),
                    reply_message=reply_anchor,
                )
                return False, "无 stream", True
            stream_id = chat_stream.stream_id

            if self.get_config("confirm.enabled", True):
                try:
                    await self.send_text(
                        _pick_douyin_confirm(),
                        set_reply=bool(reply_anchor),
                        reply_message=reply_anchor,
                    )
                except Exception as e:
                    logger.debug(f"douyin 确认语发送跳过: {e}")

            base_url = self.get_config("api.base_url", "https://api.xingzhige.com/API/douyin/")
            kw = _fetch_api_kwargs(self.get_config)

            logger.info(f"抖音解析(命令): url={url[:80]}...")
            raw = await fetch_douyin_parse(base_url, url, **kw)
            inner = _unwrap_payload(raw)
            stat, item = _resolve_item_stat(inner)
            if not _api_success(raw) and not _has_sendable_media(item):
                msg = raw.get("msg") or raw.get("message") or str(raw)
                await self.send_text(
                    f"❌ 抖音解析失败: {msg}",
                    set_reply=bool(reply_anchor),
                    reply_message=reply_anchor,
                )
                return False, msg, True

            if not _has_sendable_media(item):
                await self.send_text(
                    "❌ 解析成功但未返回可发送的视频或图集",
                    set_reply=bool(reply_anchor),
                    reply_message=reply_anchor,
                )
                return False, "无媒体", True

            await send_parsed_content(
                stream_id,
                stat,
                item,
                send_summary=bool(self.get_config("send.send_summary_text", True)),
                max_gallery=int(self.get_config("send.max_gallery_images", 9)),
                reply_anchor=reply_anchor,
                qq_video_as_text_link=bool(self.get_config("send.qq_video_as_text_link", True)),
            )
            return True, "ok", True
        except Exception as e:
            logger.error(f"抖音命令失败: {e}", exc_info=True)
            await self.send_text(
                f"❌ 抖音解析出错: {e}",
                set_reply=bool(reply_anchor),
                reply_message=reply_anchor,
            )
            return False, str(e), True


@register_plugin
class DouyinVideoPlugin(BasePlugin):
    plugin_name = "douyin_video_plugin"
    enable_plugin = True
    dependencies: List[str] = []
    python_dependencies: List[str] = []
    config_file_name = "config.toml"

    config_section_descriptions = {
        "plugin": "插件开关",
        "api": "星知阁解析接口",
        "behavior": "触发与拦截",
        "send": "发送内容",
        "confirm": "解析前确认语（自动识别与命令均支持；引用回复取决于 behavior.reply_to_trigger）",
    }

    config_schema: dict = {
        "plugin": {
            "enabled": ConfigField(bool, default=True, description="是否启用插件"),
            "config_version": ConfigField(str, default="1.0.2", description="配置版本"),
        },
        "api": {
            "base_url": ConfigField(
                str,
                default="https://api.xingzhige.com/API/douyin/",
                description="解析接口根地址",
            ),
            "timeout": ConfigField(int, default=300, description="读超时（秒），慢速服务器可 300～600"),
            "connect_timeout": ConfigField(int, default=90, description="连接/SSL 超时（秒）"),
            "retries": ConfigField(int, default=2, description="失败重试次数（不含首次）"),
            "proxy": ConfigField(str, default="", description="HTTP 代理，如 http://127.0.0.1:7890，留空直连"),
        },
        "behavior": {
            "group_at_only": ConfigField(
                bool, default=False, description="群聊仅 @ 机器人时自动解析（命令不受限）"
            ),
            "block_ai_reply": ConfigField(
                bool, default=True, description="自动解析成功后是否阻止本条消息继续进入 AI"
            ),
            "min_interval_seconds": ConfigField(
                int, default=3, description="同一会话自动解析最小间隔（秒）"
            ),
            "reply_to_trigger": ConfigField(
                bool,
                default=False,
                description="确认语/解析结果是否引用回复用户触发消息（关闭可避免日志与部分客户端出现长引用预览）",
            ),
        },
        "send": {
            "send_summary_text": ConfigField(
                bool,
                default=True,
                description="是否发送标题与互动数据摘要（与视频/图集合并为同一条消息，避免分开发送导致超时）",
            ),
            "max_gallery_images": ConfigField(int, default=9, description="图集最多发送张数"),
            "qq_video_as_text_link": ConfigField(
                bool,
                default=True,
                description="视频类作品是否仅在正文发「📎 视频：URL」（QQ/NapCat 的 video 段常无法直接使用抖音 CDN 直链；设 false 则尝试 videourl）",
            ),
        },
        "confirm": {
            "enabled": ConfigField(
                bool,
                default=True,
                description="解析前是否发送一条随机短确认语（是否引用由 behavior.reply_to_trigger 决定）",
            ),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return [
            (DouyinLinkEventHandler.get_handler_info(), DouyinLinkEventHandler),
            (DouyinParseCommand.get_command_info(), DouyinParseCommand),
        ]
