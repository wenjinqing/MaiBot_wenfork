# -*- coding: utf-8 -*-
"""网盘分享链接转直链：识别蓝奏云/123/奶牛等网盘分享链接，调用本地 netdisk-fast-download 服务取直链。

服务默认地址 http://127.0.0.1:6400，接口 /json/parser?url=<分享链接>&pwd=<密码>。
自动识别 + 命令 /直链 <链接> 双触发。
"""

from __future__ import annotations

import asyncio
import random
import re
import time
from typing import Dict, List, Optional, Tuple, Type

import aiohttp

from src.chat.message_receive.chat_stream import get_chat_manager
from src.chat.message_receive.message import MessageRecv
from src.common.logger import get_logger
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

logger = get_logger("netdisk_parser_plugin")

# 网盘域名 → 中文名（用于确认语里报出是哪个网盘）
_PAN_NAME_RULES: Tuple[Tuple[str, str], ...] = (
    ("lanzou", "蓝奏云"),
    ("ilanzou", "蓝奏云优享"),
    ("feiji", "小飞机网盘"),
    ("cowtransfer", "奶牛快传"),
    ("123pan", "123网盘"),
    ("123865", "123网盘"),
    ("123684", "123网盘"),
    ("wenshushu", "文叔叔"),
    ("ws", "文叔叔"),
    ("fangcloud", "亿方云"),
    ("lecloud.lenovo", "联想乐云"),
    ("ctfile", "城通网盘"),
    ("474b", "城通网盘"),
    ("ghpym", "城通网盘"),
    ("ecpan", "移动云空间"),
    ("118pan", "118网盘"),
    ("vyuyun", "微雨云存储"),
    ("115", "115网盘"),
    ("anxia", "115网盘"),
    ("pan.baidu", "百度网盘"),
    ("yun.baidu", "百度网盘"),
    ("drive.google", "谷歌网盘"),
    ("onedrive", "OneDrive"),
    ("dropbox", "Dropbox"),
    ("icloud", "iCloud"),
)


def _pan_name(url: str) -> str:
    """从链接识别网盘中文名，认不出就用「这个网盘」兜底。"""
    low = (url or "").lower()
    for key, name in _PAN_NAME_RULES:
        if key in low:
            return name
    return "这个网盘"


# 解析前确认语模板（{pan} 会替换成网盘名）；君君人设：涩气小猫娘 + 二次元宅，软乎乎不黏人
_CONFIRM_TEMPLATES: Tuple[str, ...] = (
    "诶，{pan}的链接？收到啦，君君这就帮你扒直链~",
    "{pan}的分享喵，交给我，马上给你拆开看看 (｡･ω･｡)",
    "看到{pan}链接啦，稍等一下下，正在变魔术呢欸嘿",
    "好耶，{pan}的~ 君君去取直链，乖乖等我一会儿哦",
    "收到{pan}链接，本喵这就去解析，别走开嘛~",
    "嗯哼，{pan}的分享我接住了，这就拆给你看 (･ω<)",
    "{pan}的呀，让我康康……正在努力扒拉直链中，等我喵",
    "诶嘿，{pan}链接到手，君君开工啦，马上回来~",
)


def _pick_confirm(pan: str = "这个网盘") -> str:
    return random.choice(_CONFIRM_TEMPLATES).format(pan=pan)


# 支持的网盘分享链接（与 netdisk-fast-download 覆盖范围对齐；百度需服务端配置 cookie）
NETDISK_URL_RE = re.compile(
    r"https?://(?:"
    r"[a-zA-Z0-9-]+\.)?(?:"
    r"lanzou[a-z]?\.com|lanzoui?\.com|ilanzou\.com|"          # 蓝奏云 / 蓝奏云优享
    r"feijipan\.com|feijix\.com|"                              # 小飞机
    r"cowtransfer\.com|"                                       # 奶牛快传
    r"123pan\.com|123865\.com|123684\.com|"                    # 123网盘
    r"wenshushu\.cn|ws\d{2}\.cn|"                              # 文叔叔
    r"fangcloud\.(?:com|cn)|"                                  # 亿方云
    r"lecloud\.lenovo\.com|"                                   # 联想乐云
    r"ctfile\.com|474b\.com|ct\.ghpym\.com|"                   # 城通
    r"ecpan\.cn|"                                              # 移动云空间
    r"118pan\.com|vyuyun\.com|"                                # 118 / 微雨
    r"115\.com|115cdn\.com|anxia\.com|"                        # 115
    r"pan\.baidu\.com|yun\.baidu\.com|"                        # 百度（需服务端支持）
    r"drive\.google\.com|onedrive\.live\.com|"                 # 海外盘
    r"dropbox\.com|icloud\.com\.cn"
    r")/[^\s​]+",
    re.IGNORECASE,
)


# ---- 待补密码：解析缺密码时，记下「会话+用户」在等密码，用户下一条消息当密码自动重试 ----
# key = f"{stream_id}:{user_id}"，value = {"url": 链接, "pan": 网盘名, "ts": 记录时间, "anchor": 引用锚点}
_PENDING_PWD: Dict[str, dict] = {}
_PENDING_TTL = 180.0  # 等待密码的有效期（秒），超时作废

# 一条消息「看起来像密码」：2-8 位字母数字，整条消息就这点内容（去掉空白）
_PWD_LIKE_RE = re.compile(r"^[A-Za-z0-9]{2,8}$")

# 解析返回里「需要密码 / 密码错误」的特征关键词（不同网盘措辞不一，宽松匹配）
_NEED_PWD_HINTS = ("密码", "提取码", "pwd", "password", "verify", "需要验证", "校验")


def _pending_key(stream_id: str, user_id: str) -> str:
    return f"{stream_id}:{user_id}"


def _looks_like_pwd(text: str) -> bool:
    return bool(text) and bool(_PWD_LIKE_RE.match(text.strip()))


def _err_needs_pwd(err: str) -> bool:
    """从失败信息粗略判断是不是缺密码/密码错。认不准就回 False（按普通失败处理）。"""
    low = (err or "").lower()
    return any(h.lower() in low for h in _NEED_PWD_HINTS)


def _first_netdisk_url(text: str) -> Optional[str]:
    if not text:
        return None
    m = NETDISK_URL_RE.search(text)
    return m.group(0).rstrip("，。、）)】」』") if m else None


def _extract_pwd(text: str, url: str) -> str:
    """从触发文本中提取分享密码（支持「密码:xxxx / 提取码 xxxx / pwd=xxxx / @xxxx」等常见写法）。"""
    if not text:
        return ""
    tail = text.split(url, 1)[-1] if url in text else text
    # 链接后直接 @密码
    m = re.search(r"@([A-Za-z0-9]{2,8})\b", tail)
    if m:
        return m.group(1)
    # 「密码/提取码/访问码/pwd」+ 分隔符 + 码
    m = re.search(r"(?:密码|提取码|访问码|pwd|password)\s*[:：=\s]\s*([A-Za-z0-9]{2,8})", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return ""


def _plain_has_at_bot(text: str) -> bool:
    return bool(text) and ("@" in text)


def _reply_anchor_from_mai(message: Optional[MaiMessages]) -> Optional[MessageRecv]:
    if not message or not message.stream_id:
        return None
    try:
        stream = get_chat_manager().get_stream(message.stream_id)
        if stream and stream.context:
            return stream.context.get_last_message()
    except Exception as e:
        logger.debug(f"netdisk: 无法获取引用锚点: {e}")
    return None


async def fetch_direct_link(
    base_url: str,
    share_url: str,
    pwd: str = "",
    *,
    read_timeout_sec: int = 60,
    connect_timeout_sec: int = 20,
    retries: int = 1,
    proxy: str = "",
) -> dict:
    """调用 netdisk-fast-download 的 /json/parser 接口，返回解析后的 JSON dict。"""
    api = base_url.rstrip("/") + "/json/parser"
    params = {"url": share_url}
    if pwd:
        params["pwd"] = pwd

    timeout = aiohttp.ClientTimeout(
        total=read_timeout_sec + connect_timeout_sec + 10,
        connect=connect_timeout_sec,
        sock_read=read_timeout_sec,
    )
    last_err: Optional[str] = None
    for attempt in range(retries + 1):
        try:
            connector = aiohttp.TCPConnector(limit=5)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(api, params=params, timeout=timeout, proxy=proxy or None) as resp:
                    text = await resp.text()
                    try:
                        import json

                        return json.loads(text)
                    except Exception:
                        # 非 JSON（常见于服务内部 500 / 加密链接缺密码崩溃）→ 标记 server_error
                        return {
                            "code": resp.status,
                            "success": False,
                            "msg": text[:200],
                            "_server_error": True,
                        }
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < retries:
                await asyncio.sleep(1.5)
                continue
    return {"code": -1, "success": False, "msg": f"无法连接解析服务: {last_err}"}


def _resolve_direct_link(raw: dict) -> Tuple[bool, str, str]:
    """从接口返回中提取 (是否成功, 直链, 错误信息)。"""
    if not isinstance(raw, dict):
        return False, "", "返回格式异常"
    data = raw.get("data") or {}
    direct = ""
    if isinstance(data, dict):
        direct = data.get("directLink") or data.get("direct_link") or ""
    ok = bool(raw.get("success")) and bool(direct)
    if ok:
        return True, direct, ""
    msg = raw.get("msg") or raw.get("message") or "解析失败"
    return False, direct, str(msg)


async def _do_parse_and_send(
    *,
    stream_id: str,
    share_url: str,
    pwd: str,
    get_config_fn,
    reply_anchor: Optional[MessageRecv],
    user_id: Optional[str] = None,
    send_confirm: bool = True,
) -> bool:
    """核心流程：确认语 → 调接口 → 发直链。返回是否解析成功。

    缺密码（且本次未提供密码）时不报"失效"，而是记下待补密码状态并提示用户回密码。
    """
    pan = _pan_name(share_url)
    if send_confirm and get_config_fn("confirm.enabled", True):
        try:
            await send_api.text_to_stream(
                _pick_confirm(pan),
                stream_id,
                storage_message=True,
                set_reply=bool(reply_anchor),
                reply_message=reply_anchor,
            )
        except Exception as e:
            logger.debug(f"netdisk 确认语发送跳过: {e}")

    base_url = get_config_fn("api.base_url", "http://127.0.0.1:6400")
    raw = await fetch_direct_link(
        base_url,
        share_url,
        pwd,
        read_timeout_sec=int(get_config_fn("api.timeout", 60)),
        connect_timeout_sec=int(get_config_fn("api.connect_timeout", 20)),
        retries=int(get_config_fn("api.retries", 1)),
        proxy=(get_config_fn("api.proxy", "") or "").strip(),
    )

    ok, direct, err = _resolve_direct_link(raw)
    if not ok:
        # 没带密码、且失败疑似缺密码（错误文字含密码关键词，或服务直接崩成 500/非JSON）→ 记下待补密码
        ask_pwd_enabled = bool(get_config_fn("behavior.ask_password", True))
        server_error = bool(raw.get("_server_error"))
        needs_pwd = _err_needs_pwd(err) or server_error
        if ask_pwd_enabled and user_id and not pwd and needs_pwd:
            pkey = _pending_key(stream_id, str(user_id))
            _PENDING_PWD[pkey] = {
                "url": share_url,
                "pan": pan,
                "ts": time.time(),
                "anchor": reply_anchor,
            }
            logger.info(f"网盘解析: 记录待补密码 key={pkey} url={share_url[:60]}")
            await send_api.text_to_stream(
                f"诶，这个{pan}链接要密码才能打开喵~ "
                f"把密码（提取码）单独回我一条就行，我马上帮你重拆 (｡･ω･｡)",
                stream_id,
                storage_message=True,
                set_reply=bool(reply_anchor),
                reply_message=reply_anchor,
            )
            return False

        await send_api.text_to_stream(
            f"呜…这条{pan}链接君君没扒动喵，可能是失效了或者密码不对~\n（{err}）",
            stream_id,
            storage_message=True,
            set_reply=bool(reply_anchor),
            reply_message=reply_anchor,
        )
        return False

    # 成功：清掉该用户在本会话的待补密码状态
    if user_id:
        _PENDING_PWD.pop(_pending_key(stream_id, str(user_id)), None)

    prefix = get_config_fn("send.link_prefix", "🔗 直链（有效期有限，尽快下载）：")
    await send_api.text_to_stream(
        f"{prefix}\n{direct}",
        stream_id,
        storage_message=True,
        set_reply=bool(reply_anchor),
        reply_message=reply_anchor,
    )
    return True


class NetdiskLinkEventHandler(BaseEventHandler):
    """自动识别消息中的网盘分享链接并解析为直链。"""

    event_type = EventType.ON_MESSAGE
    handler_name = "netdisk_link_handler"
    handler_description = "识别网盘分享链接并转直链（蓝奏云/123/奶牛等）"
    intercept_message = True
    weight = 47

    _last_ts: Dict[str, float] = {}

    async def execute(
        self, message: MaiMessages | None
    ) -> Tuple[bool, bool, Optional[str], None, Optional[MaiMessages]]:
        try:
            if not message or not message.plain_text or not message.stream_id:
                return True, True, None, None, None

            stream_id = message.stream_id
            user_id = ""
            if message.message_base_info:
                user_id = str(message.message_base_info.get("user_id") or "")

            text = message.plain_text.strip()
            block = bool(self.get_config("behavior.block_ai_reply", True))

            # —— 优先处理「补密码」：该用户在本会话有待补密码的链接，且这条消息像密码 ——
            if user_id and self.get_config("behavior.ask_password", True):
                pkey = _pending_key(stream_id, user_id)
                pending = _PENDING_PWD.get(pkey)
                if pending:
                    if time.time() - pending.get("ts", 0) > _PENDING_TTL:
                        _PENDING_PWD.pop(pkey, None)  # 过期作废
                    elif _looks_like_pwd(text) and not _first_netdisk_url(text):
                        _PENDING_PWD.pop(pkey, None)
                        logger.info(f"网盘解析(补密码): url={pending['url'][:60]} pwd=已提供")
                        await _do_parse_and_send(
                            stream_id=stream_id,
                            share_url=pending["url"],
                            pwd=text,
                            get_config_fn=self.get_config,
                            reply_anchor=pending.get("anchor"),
                            user_id=user_id,
                            send_confirm=False,  # 补密码重试不再发确认语，直接出结果
                        )
                        return True, not block, "netdisk_pwd_retry", None, None

            share = _first_netdisk_url(message.plain_text)
            if not share:
                return True, True, None, None, None

            group_at_only = self.get_config("behavior.group_at_only", False)
            if message.is_group_message and group_at_only and not _plain_has_at_bot(message.plain_text):
                return True, True, None, None, None

            now = time.time()
            interval = float(self.get_config("behavior.min_interval_seconds", 3) or 0)
            last = NetdiskLinkEventHandler._last_ts.get(stream_id, 0.0)
            if interval > 0 and now - last < interval:
                return True, True, None, None, None
            NetdiskLinkEventHandler._last_ts[stream_id] = now

            reply_anchor = (
                _reply_anchor_from_mai(message)
                if self.get_config("behavior.reply_to_trigger", False)
                else None
            )
            pwd = _extract_pwd(message.plain_text, share)

            logger.info(f"网盘解析(自动): url={share[:80]} pwd={'有' if pwd else '无'}")
            await _do_parse_and_send(
                stream_id=stream_id,
                share_url=share,
                pwd=pwd,
                get_config_fn=self.get_config,
                reply_anchor=reply_anchor,
                user_id=user_id,
            )

            return True, not block, "netdisk_parsed", None, None

        except Exception as e:
            logger.error(f"网盘链接处理异常: {e}", exc_info=True)
            if message and message.stream_id:
                try:
                    await send_api.text_to_stream(
                        f"❌ 网盘解析出错: {e}", message.stream_id, storage_message=True
                    )
                except Exception:
                    pass
            return True, True, str(e), None, None


class NetdiskParseCommand(BaseCommand):
    """手动解析：/直链 <链接> 或 /netdisk <链接>"""

    command_name = "netdisk_parse"
    command_description = "网盘分享链接转直链"
    command_pattern = r"^/(netdisk|直链|网盘解析)(?:\s+(?P<url>\S+))?(?:\s+(?P<pwd>\S+))?$"
    command_help = "用法：/直链 <网盘分享链接> [密码]  或  /netdisk <链接> [密码]"
    intercept_message = True

    async def execute(self) -> Tuple[bool, str, bool]:
        reply_anchor = self.message if self.get_config("behavior.reply_to_trigger", False) else None
        try:
            url = (self.matched_groups.get("url") or "").strip()
            pwd = (self.matched_groups.get("pwd") or "").strip()
            if not url:
                await self.send_text(
                    "用法：/直链 <网盘分享链接> [密码]",
                    set_reply=bool(reply_anchor),
                    reply_message=reply_anchor,
                )
                return True, "提示用法", True

            if not NETDISK_URL_RE.search(url):
                await self.send_text(
                    "请提供有效的网盘分享链接（蓝奏云/123/奶牛/文叔叔等）",
                    set_reply=bool(reply_anchor),
                    reply_message=reply_anchor,
                )
                return False, "链接不匹配", True

            chat_stream = self.message.chat_stream
            if not chat_stream or not chat_stream.stream_id:
                await self.send_text("❌ 无法获取当前会话", set_reply=bool(reply_anchor), reply_message=reply_anchor)
                return False, "无 stream", True

            # 命令未显式带密码时，尝试从原文里提取
            if not pwd:
                pwd = _extract_pwd(self.message.processed_plain_text or "", url)

            user_id = ""
            try:
                user_id = str(self.message.message_info.user_info.user_id or "")
            except Exception:
                pass

            logger.info(f"网盘解析(命令): url={url[:80]} pwd={'有' if pwd else '无'}")
            ok = await _do_parse_and_send(
                stream_id=chat_stream.stream_id,
                share_url=url,
                pwd=pwd,
                get_config_fn=self.get_config,
                reply_anchor=reply_anchor,
                user_id=user_id,
            )
            return ok, "ok" if ok else "解析失败", True

        except Exception as e:
            logger.error(f"网盘命令失败: {e}", exc_info=True)
            await self.send_text(f"❌ 网盘解析出错: {e}", set_reply=bool(reply_anchor), reply_message=reply_anchor)
            return False, str(e), True


@register_plugin
class NetdiskParserPlugin(BasePlugin):
    plugin_name = "netdisk_parser_plugin"
    enable_plugin = True
    dependencies: List[str] = []
    python_dependencies: List[str] = []
    config_file_name = "config.toml"

    config_section_descriptions = {
        "plugin": "插件开关",
        "api": "本地 netdisk-fast-download 解析服务",
        "behavior": "触发与拦截",
        "send": "发送内容",
        "confirm": "解析前确认语",
    }

    config_schema: dict = {
        "plugin": {
            "enabled": ConfigField(bool, default=True, description="是否启用插件"),
            "config_version": ConfigField(str, default="1.0.0", description="配置版本"),
        },
        "api": {
            "base_url": ConfigField(
                str,
                default="http://127.0.0.1:6400",
                description="netdisk-fast-download 服务地址（本机默认 6400 端口）",
            ),
            "timeout": ConfigField(int, default=60, description="读超时（秒）"),
            "connect_timeout": ConfigField(int, default=20, description="连接超时（秒）"),
            "retries": ConfigField(int, default=1, description="失败重试次数（不含首次）"),
            "proxy": ConfigField(str, default="", description="HTTP 代理，留空直连"),
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
                bool, default=False, description="是否引用回复用户触发消息"
            ),
            "ask_password": ConfigField(
                bool,
                default=True,
                description="加密分享缺密码时，提示用户补发密码并自动重试（3分钟内有效）",
            ),
        },
        "send": {
            "link_prefix": ConfigField(
                str,
                default="🔗 直链（有效期有限，尽快下载）：",
                description="直链前的提示文字",
            ),
        },
        "confirm": {
            "enabled": ConfigField(bool, default=True, description="解析前是否发送一条随机短确认语"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return [
            (NetdiskLinkEventHandler.get_handler_info(), NetdiskLinkEventHandler),
            (NetdiskParseCommand.get_command_info(), NetdiskParseCommand),
        ]
