"""
Pixiv小说插件 - Pixiv Novel Plugin

基于 Pixiv 官方 Web API 的小说抓取插件
下载整部小说系列/单篇并保存为 txt 文件发送

Author: Claude
Version: 1.2.0
"""

from typing import List, Tuple, Type, Any, Optional, Dict
import asyncio
import aiohttp
import time
import re
import os
import json
import urllib.parse
import urllib.request

from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseCommand,
    ComponentInfo,
    ConfigField,
)
from src.common.logger import get_logger
from src.config.config import global_config

logger = get_logger("pixiv_novel")


class PixivNovelAPI:
    """Pixiv 小说 Web API 封装类

    通过模拟浏览器请求 Pixiv 官方 AJAX 接口抓取小说系列与正文。
    需要配置 PHPSESSID Cookie 才能抓取登录后可见内容（R-18 等）。
    """

    BASE_URL = "https://www.pixiv.net"
    AJAX_NOVEL = "https://www.pixiv.net/ajax/novel/{}"
    AJAX_SERIES = "https://www.pixiv.net/ajax/novel/series/{}"
    AJAX_SERIES_CONTENT = "https://www.pixiv.net/ajax/novel/series_content/{}"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    MAX_CONCURRENT_REQUESTS = 3
    SERIES_PAGE_LIMIT = 30

    def __init__(self, cookie: str = "", proxy: str = "", timeout: int = 30):
        self.cookie = cookie.strip()
        self.proxy = proxy.strip() if proxy else None
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

    def _headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ja-JP,ja;q=0.9,zh-CN;q=0.8,zh;q=0.7,en;q=0.6",
            "Referer": referer or (self.BASE_URL + "/"),
        }
        # 从 cookie 提取 x-user-id
        uid_match = re.search(r"PHPSESSID=(\d+)_", self.cookie)
        if uid_match:
            headers["x-user-id"] = uid_match.group(1)
        if self.cookie:
            headers["Cookie"] = self.cookie
        return headers

    async def _get_json(self, url: str, referer: Optional[str] = None) -> Dict[str, Any]:
        try:
            async with self.semaphore:
                timeout_cfg = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers=self._headers(referer),
                        proxy=self.proxy,
                        timeout=timeout_cfg,
                    ) as resp:
                        text = await resp.text()
                        if resp.status != 200:
                            logger.error("请求失败 %s 状态码 %s: %s", url, resp.status, text[:200])
                            return {"error": "HTTP " + str(resp.status)}
                        try:
                            data = json.loads(text)
                        except Exception as e:
                            logger.error("JSON 解析失败: %s 原文: %s", e, text[:200])
                            return {"error": "响应不是有效 JSON"}
                        if data.get("error"):
                            return {"error": data.get("error"), "message": data.get("message", "")}
                        return data.get("body", {}) or {}
        except asyncio.TimeoutError:
            logger.error("请求超时: %s", url)
            return {"error": "请求超时"}
        except aiohttp.ClientConnectorError as e:
            logger.error("网络连接失败: %s", e)
            return {"error": "网络连接失败，请检查网络或代理设置"}
        except Exception as e:
            logger.error("请求异常: %s", e, exc_info=True)
            return {"error": str(e)}

    async def get_novel_meta(self, novel_id: str) -> Dict[str, Any]:
        url = self.AJAX_NOVEL.format(novel_id)
        referer = self.BASE_URL + "/novel/show.php?id=" + novel_id
        return await self._get_json(url, referer)

    async def get_series_meta(self, series_id: str) -> Dict[str, Any]:
        url = self.AJAX_SERIES.format(series_id)
        referer = self.BASE_URL + "/novel/series/" + series_id
        return await self._get_json(url, referer)

    async def get_series_novels(
        self, series_id: str, limit: int = 30, last_order: int = 0, order_by: str = "asc"
    ) -> Dict[str, Any]:
        url = (
            self.AJAX_SERIES_CONTENT.format(series_id)
            + "?limit=" + str(limit) + "&last_order=" + str(last_order) + "&order_by=" + order_by
        )
        referer = self.BASE_URL + "/novel/series/" + series_id
        return await self._get_json(url, referer)


    AJAX_SEARCH = "https://www.pixiv.net/ajax/search/novels/{}"

    async def search_novels(self, keyword: str, page: int = 1) -> Dict[str, Any]:
        """搜索 Pixiv 小说

        返回 body 字典，结果列表在 body['novel']['data']。
        """
        kw = (keyword or "").strip()
        if not kw:
            return {"error": "关键词为空"}
        enc = urllib.parse.quote(kw)
        url = (
            self.AJAX_SEARCH.format(enc)
            + "?word=" + enc
            + "&order=date_d&mode=all&p=" + str(page)
            + "&type=all&s_mode=s_tag&r18=off"
        )
        referer = self.BASE_URL + "/tags/"
        return await self._get_json(url, referer)


    async def fetch_series_all_novels(
        self, series_id: str, max_count: int = 999
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """分页抓取整个系列的所有章节

        Returns:
            (series_meta, novels) novels 为每篇简要信息列表
        """
        series_meta = await self.get_series_meta(series_id)
        if series_meta.get("error"):
            return series_meta, []

        total = 0
        try:
            total = int(series_meta.get("total", 0))
        except Exception:
            total = 0
        if total <= 0:
            try:
                total = int(series_meta.get("novel_count", 0))
            except Exception:
                total = 0

        cap = min(total if total > 0 else max_count, max_count)

        all_novels: List[Dict[str, Any]] = []
        last_order = 0
        while len(all_novels) < cap:
            batch = await self.get_series_novels(
                series_id, limit=self.SERIES_PAGE_LIMIT, last_order=last_order, order_by="asc"
            )
            if batch.get("error"):
                return series_meta, all_novels
            # 接口结构: body.page.seriesContents
            page = batch.get("page") or {}
            contents = page.get("seriesContents") or batch.get("series_contents") or []
            if not contents:
                break
            for item in contents:
                nid = item.get("id")
                if nid is None:
                    continue
                all_novels.append(item)
                if len(all_novels) >= cap:
                    break
            if len(contents) < self.SERIES_PAGE_LIMIT:
                break
            last_id = contents[-1].get("id")
            if last_id is None:
                break
            try:
                last_order = int(last_id) if str(last_id).isdigit() else last_order
            except Exception:
                pass
            if last_order == 0:
                break

        return series_meta, all_novels

    async def fetch_novel_full(self, novel_id: str) -> Dict[str, Any]:
        """获取单篇小说元信息 + 正文

        正文直接在 /ajax/novel/{id} 的 body.content 字段中，
        无需单独请求 /content 接口（该接口已弃用/404）。
        """
        meta = await self.get_novel_meta(novel_id)
        if meta.get("error"):
            return meta
        text = meta.get("content") or ""
        meta["text"] = text
        return meta


class PixivNovelCommand(BaseCommand):
    """Pixiv 小说抓取命令（下载为 txt 文件发送）"""

    MAX_COOLDOWN_CACHE_SIZE = 200
    COOLDOWN_CLEANUP_THRESHOLD = 240
    SEARCH_CACHE_MAX = 50

    # 搜索关键词黑名单：涉及未成年人保护，命中即拒绝搜索
    BLOCKED_KEYWORDS = [
        "幼女", "未成年", "儿童", "小孩",
        "toddler", "baby", "小学生", "中学生",
        "初中", "初中生", "未成年者", "teen", "underage", "jc", "js",
    ]

    # 类级搜索结果缓存：{user_id: [items...]}，跨命令调用持久保留
    _search_cache: Dict[str, List[Dict[str, Any]]] = {}

    GROUP_REJECT_MSG = "该功能暂不支持群聊使用，请在私聊中发送 /novel search <关键词> 搜索小说"

    SERIES_URL_PATTERN = re.compile(r"pixiv\.net/novel/series/(?P<id>\d+)", re.IGNORECASE)
    NOVEL_URL_PATTERN = re.compile(r"pixiv\.net/novel/show\.php\?id=(?P<id>\d+)", re.IGNORECASE)
    NOVEL_SHORT_PATTERN = re.compile(r"pixiv\.net/n/(?P<id>\d+)", re.IGNORECASE)

    MAX_TEXT_PER_NODE = 3500

    command_name = "novel"
    command_description = "下载 Pixiv 小说（系列或单篇）为 txt 文件并发送"
    command_pattern = r"^/novel(?:\s+(?P<args>.+))?$"
    command_help = """使用方法:
基础命令:
/novel <系列URL或ID> - 下载整个小说系列，合成一个 txt 文件发送
/novel read <单篇URL或ID> - 仅下载单篇小说为 txt 文件发送
/novel list <系列URL或ID> - 只列出系列章节目录，不下载正文
搜索命令（仅私聊可用）:
/novel search <关键词> - 搜索小说，返回编号列表
/novel dl <编号> - 下载搜索结果中对应编号的小说
/novel help - 显示此帮助

示例:
/novel https://www.pixiv.net/novel/series/14998441
/novel 14998441
/novel read https://www.pixiv.net/novel/show.php?id=12345678
/novel read 12345678
/novel list 14998441
/novel search 異世界転生
/novel dl 3
说明: 搜索结果每次重新编号，第1页第1个为1，输入编号即可下载"""

    command_examples = [
        "/novel https://www.pixiv.net/novel/series/14998441 - 下载整个系列为 txt",
        "/novel 14998441 - 直接使用系列ID",
        "/novel read 12345678 - 下载单篇为 txt",
        "/novel list 14998441 - 只看章节目录",
        "/novel search 異世界転生 - 搜索小说",
        "/novel dl 3 - 下载编号3对应的小说",
        "/novel help - 显示帮助",
    ]
    enable_command = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = PixivNovelAPI(
            cookie=self.get_config("auth.pixiv_cookie", ""),
            proxy=self.get_config("network.proxy", ""),
            timeout=self.get_config("features.api_timeout", 30),
        )
        self.cooldown_cache: Dict[str, float] = {}

    def _is_group_chat(self) -> bool:
        info = self.message.message_info
        if info.group_info and getattr(info.group_info, "group_id", None):
            gid = info.group_info.group_id
            if str(gid) not in ("0", "", "None"):
                return True
        return False

    def _check_blocked_keywords(self, keyword: str) -> bool:
        kw = (keyword or "").lower()
        for bad in self.BLOCKED_KEYWORDS:
            if bad.lower() in kw:
                return True
        return False

    async def execute(self) -> Tuple[bool, str, bool]:
        try:
            args_str = ""
            if self.matched_groups and "args" in self.matched_groups:
                args_str = self.matched_groups["args"] or ""
            args_str = args_str.strip()

            if not args_str or args_str.lower() in ["help", "帮助", "?", "？"]:
                await self.send_text(self.command_help)
                return True, "显示帮助信息", True

            user_id = str(self.message.message_info.user_info.user_id)

            # 群聊拦截：除 help 外，小说功能仅限私聊使用（涉及 R18 管控）
            if self._is_group_chat():
                logger.info("群聊触发小说命令，统一拒绝: user=%s", user_id)
                await self.send_text(self.GROUP_REJECT_MSG)
                return False, "群聊不可用", True

            # 权限校验：QQ 白名单（涉及 R18 内容管控）
            allow_list = self.get_config("auth.allow_qq_list", []) or []
            allow_str_list = [str(x) for x in allow_list]
            if allow_str_list and user_id not in allow_str_list:
                logger.warning("用户 %s 不在小说插件白名单中，拒绝触发", user_id)
                await self.send_text("⛔ 你没有使用该命令的权限")
                return False, "无权限", True

            cooldown = self.get_config("features.cooldown_seconds", 30)
            cooldown_result = self._check_cooldown(user_id, cooldown)
            if not cooldown_result["ready"]:
                remaining = cooldown_result["remaining"]
                await self.send_text("⏰ 冷却中，还需等待 " + str(remaining) + " 秒")
                return False, "冷却中", True

            sub, target = self._parse_subcommand(args_str)

            # search / dl 不需要 URL，单独处理
            if sub == "search":
                if not target:
                    await self.send_text("❌ 请输入搜索关键词\n用法: /novel search <关键词>")
                    return False, "参数无效", True
                if self._check_blocked_keywords(target):
                    logger.warning("用户 %s 搜索敏感关键词被拦截: %s", user_id, target)
                    await self.send_text("⛔ 该关键词受限制，无法搜索")
                    return False, "关键词受限", True
                self._update_cooldown(user_id)
                ok = await self._handle_search(target, user_id)
                return ok, "搜索完成" if ok else "搜索失败", True

            if sub == "dl":
                if not target or not target.isdigit():
                    await self.send_text("❌ 请输入有效的编号\n用法: /novel dl <编号>")
                    return False, "参数无效", True
                self._update_cooldown(user_id)
                ok = await self._handle_download_by_number(int(target), user_id)
                return ok, "下载完成" if ok else "下载失败", True

            if not target:
                await self.send_text("❌ 未识别到有效的小说系列/单篇 URL 或 ID\n\n" + self.command_help)
                return False, "参数无效", True

            self._update_cooldown(user_id)

            if sub == "read":
                ok = await self._handle_single(target)
            elif sub == "list":
                ok = await self._handle_series_list_only(target)
            else:
                ok = await self._handle_series_full(target)

            return ok, "完成" if ok else "失败", True

        except Exception as e:
            logger.error("命令执行失败: %s", str(e), exc_info=True)
            await self.send_text("❌ 执行失败: " + str(e))
            return False, "执行失败: " + str(e), True

    def _parse_subcommand(self, args_str: str) -> Tuple[str, str]:
        tokens = args_str.split()
        sub = "series"
        target = ""
        if not tokens:
            return sub, target
        first = tokens[0].lower()
        if first in ("read", "读", "正文"):
            sub = "read"
            target = " ".join(tokens[1:]).strip()
        elif first in ("list", "目录", "列表"):
            sub = "list"
            target = " ".join(tokens[1:]).strip()
        elif first in ("search", "搜索", "搜", "find"):
            sub = "search"
            target = " ".join(tokens[1:]).strip()
        elif first in ("dl", "download", "下载", "下"):
            sub = "dl"
            target = " ".join(tokens[1:]).strip()
        else:
            target = args_str.strip()
        return sub, target

    def _extract_id(self, target: str) -> Tuple[str, str]:
        target = target.strip()
        m = self.SERIES_URL_PATTERN.search(target)
        if m and m.group("id"):
            return "series", m.group("id")
        m = self.NOVEL_URL_PATTERN.search(target)
        if m and m.group("id"):
            return "novel", m.group("id")
        m = self.NOVEL_SHORT_PATTERN.search(target)
        if m and m.group("id"):
            return "novel", m.group("id")
        digits = re.sub(r"\D", "", target)
        if digits:
            return "series", digits
        return "", ""

    def _get_target_ids(self) -> Tuple[Optional[str], Optional[str]]:
        info = self.message.message_info
        group_id = None
        user_id = None
        if info.group_info and getattr(info.group_info, "group_id", None):
            gid = info.group_info.group_id
            if str(gid) not in ("0", "", "None"):
                group_id = str(gid)
        if info.user_info and getattr(info.user_info, "user_id", None):
            uid = info.user_info.user_id
            if str(uid) not in ("0", "", "None"):
                user_id = str(uid)
        return group_id, user_id

    def _make_unique_filename(self, base_name: str, nid: str, ext: str = ".txt") -> str:
        """生成带时间戳+PID的唯一文件名，避免同名覆盖"""
        ts = time.strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()
        ms = int((time.time() % 1) * 1000)
        safe = re.sub(r'[\\/:*?"<>|]', "_", base_name)[:40]
        return safe + "_" + nid + "_" + ts + "_" + str(pid) + "_" + str(ms) + ext

    async def _send_file(self, file_path: str, filename: str = "") -> bool:
        if not os.path.exists(file_path):
            logger.error("文件不存在: %s", file_path)
            return False
        host = str(self.get_config("napcat.host", "127.0.0.1"))
        port = int(self.get_config("napcat.port", 5700))
        token = str(self.get_config("napcat.token", "")).strip()
        group_id, user_id = self._get_target_ids()
        if group_id:
            api_url = "http://" + host + ":" + str(port) + "/send_group_msg"
            params_key = "group_id"
            params_val = group_id
        elif user_id:
            api_url = "http://" + host + ":" + str(port) + "/send_private_msg"
            params_key = "user_id"
            params_val = user_id
        else:
            logger.error("无法获取 group_id 或 user_id，无法发送文件")
            return False

        display_name = filename or os.path.basename(file_path)
        # file:/// URI 形式
        file_uri = "file:///" + urllib.request.pathname2url(file_path).lstrip("/")
        # 备选：绝对路径原始形式
        abs_path = os.path.abspath(file_path).replace("\\", "/")
        abs_path_win = os.path.abspath(file_path)

        request_data = {
            params_key: params_val,
            "message": [{"type": "file", "data": {"file": file_uri, "name": display_name}}],
        }
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token

        req_log = "[" + str(int(time.time())) + "-" + str(os.getpid()) + "] 文件发送请求: " + api_url + " | " + display_name + " | 目标 " + params_key + "=" + str(params_val) + " | file=" + file_uri
        logger.info(req_log)

        # 三种 file 字段格式依次尝试
        file_variants = [
            ("file_uri", file_uri),
            ("abs_win", abs_path_win),
            ("file_url_prefix", "file://" + abs_path),
        ]

        timeout_cfg = aiohttp.ClientTimeout(total=120)
        try:
            async with aiohttp.ClientSession() as session:
                for variant_name, file_val in file_variants:
                    msg = [{"type": "file", "data": {"file": file_val, "name": display_name}}]
                    request_data["message"] = msg
                    try:
                        async with session.post(api_url, json=request_data, headers=headers, timeout=timeout_cfg) as resp:
                            text = await resp.text()
                            logger.info("[" + variant_name + "] HTTP %s, 响应: %s", resp.status, text[:500])
                            ok = self._check_napcat_send_result(resp.status, text)
                            if ok:
                                logger.info("[发送成功] %s | 变体=%s | %s", display_name, variant_name, text[:200])
                                return True
                            # 401/403 带 token 重试
                            if resp.status in (401, 403) and token:
                                retry_url = api_url + "?access_token=" + urllib.parse.quote(token)
                                async with session.post(retry_url, json=request_data, headers=headers, timeout=timeout_cfg) as retry_resp:
                                    rtext = await retry_resp.text()
                                    logger.info("[retry] HTTP %s, 响应: %s", retry_resp.status, rtext[:500])
                                    if self._check_napcat_send_result(retry_resp.status, rtext):
                                        logger.info("[发送成功retry] %s | 变体=%s", display_name, variant_name)
                                        return True
                    except asyncio.TimeoutError:
                        logger.warning("[%s] 发送超时，尝试下一变体", variant_name)
                        continue
                    except Exception as e:
                        logger.warning("[%s] 发送异常: %s，尝试下一变体", variant_name, str(e))
                        continue
                logger.error("[发送失败] 所有 file 变体均未成功: %s", display_name)
                return False
        except Exception as e:
            logger.error("文件发送整体异常: %s", e, exc_info=True)
            return False

    def _check_napcat_send_result(self, status: int, text: str) -> bool:
        """解析 NapCat 响应，确认是否真正发送成功"""
        if status != 200:
            return False
        try:
            data = json.loads(text)
        except Exception:
            # 非 JSON 响应，HTTP 200 姑且算成功
            logger.warning("响应非 JSON，按 HTTP 200 视为成功: %s", text[:200])
            return True
        st = (data.get("status") or "").lower()
        msg = data.get("msg") or data.get("message") or ""
        retcode = data.get("retcode")
        # status=ok 或 retcode=0 视为成功
        if st == "ok" or retcode == 0:
            return True
        # 显式失败
        if st == "failed" or (retcode is not None and retcode != 0):
            logger.error("NapCat 返回失败: status=%s retcode=%s msg=%s", st, retcode, msg)
            return False
        # 无法判断，保守视为失败但记录
        logger.warning("NapCat 响应无法判定: %s", text[:300])
        return False

    def _extract_search_item_fields(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """从搜索结果条目提取统一字段。"""
        nid = str(item.get("id") or item.get("novelId") or "")
        series_id = item.get("seriesId") or item.get("series_id")
        if series_id in (None, "", "null"):
            series_id = None
        else:
            series_id = str(series_id)
        title = item.get("title") or "(无标题)"
        author = item.get("userName") or item.get("user_name") or ""
        xres = item.get("xRestrict")
        r18 = bool(xres and int(xres) >= 1)
        tags_raw = item.get("tags") or []
        tags = []
        for t in tags_raw:
            if isinstance(t, str):
                tags.append(t)
            elif isinstance(t, dict):
                tags.append(t.get("tag") or t.get("name") or "")
        desc = (item.get("description") or item.get("caption") or "").strip()
        series_title = item.get("seriesTitle") or item.get("series_title")
        if series_title in (None, "", "null"):
            series_title = None
        else:
            series_title = str(series_title).strip()
        # 显示名：有系列则用系列名，否则用章节名/单篇标题
        if series_id and series_title:
            display_title = series_title
            chapter_title = title
        else:
            display_title = title
            chapter_title = None
        return {
            "id": nid,
            "series_id": series_id,
            "series_title": series_title,
            "title": title,            # 章节/单篇原标题
            "display_title": display_title,  # 列表显示用
            "chapter_title": chapter_title,  # 系列时为章节名，单篇为 None
            "author": author,
            "r18": r18,
            "tags": tags,
            "desc": desc,
        }

    async def _handle_search(self, keyword: str, user_id: str) -> bool:
        await self.send_text("🔍 正在搜索: " + keyword + " ...")
        result = await self.api.search_novels(keyword, page=1)
        if result.get("error"):
            await self.send_text("❌ 搜索失败: " + str(result["error"]))
            return False
        novel_block = result.get("novel") or {}
        data_list = novel_block.get("data") or []
        if not data_list:
            await self.send_text("😢 未找到相关小说，换个关键词试试")
            return True

        items = [self._extract_search_item_fields(it) for it in data_list[:10]]
        # 缓存（类级，跨命令调用持久）
        PixivNovelCommand._search_cache[user_id] = items
        if len(PixivNovelCommand._search_cache) > self.SEARCH_CACHE_MAX:
            # 丢弃最早的
            extra = len(PixivNovelCommand._search_cache) - self.SEARCH_CACHE_MAX
            for k in list(PixivNovelCommand._search_cache.keys())[:extra]:
                PixivNovelCommand._search_cache.pop(k, None)

        # 每条结果作为一条聊天记录，合并转发发送（先发给自己再转发）
        total = len(items)
        bot_qq = str(global_config.bot.qq_account)
        bot_name = str(global_config.bot.nickname)
        forward_messages: List[Tuple[str, str, List[Tuple[str, str]]]] = []
        forward_messages.append((bot_qq, bot_name, [("text", "🔍 搜索「" + keyword + "」共 " + str(total) + " 条结果")]))
        for i, it in enumerate(items, 1):
            mark = " [R18]" if it["r18"] else ""
            tagstr = ""
            if it["tags"]:
                tagstr = " #" + " #".join(it["tags"][:4])
            disp = it.get("display_title") or it.get("title") or "(无标题)"
            line = str(i) + ". " + disp + mark
            # 系列作品：标注系列ID + 最新章节名（副标题）
            if it.get("series_id"):
                line += "  [系列 " + it["series_id"] + "]"
                ch = it.get("chapter_title")
                if ch and ch != disp:
                    line += "\n  └ 最新章: " + ch[:60]
            else:
                line += "  [单篇]"
            line += "\n作者: " + it["author"] + tagstr
            forward_messages.append((bot_qq, bot_name, [("text", line)]))
        forward_messages.append((bot_qq, bot_name, [("text", "输入 /novel dl <编号> 下载对应小说\n（有系列的下载整部，单篇的直接下载；编号为本列表序号，非p站ID）")]))
        try:
            ok = await self.send_forward(forward_messages, storage_message=True)
            if not ok:
                # 回退：逐条文本发送
                for _bid, _bname, body in forward_messages:
                    if body and body[0][1]:
                        await self.send_text(body[0][1])
                        await asyncio.sleep(0.6)
        except Exception as e:
            logger.warning("转发发送失败，回退逐条文本: %s", str(e))
            for _bid, _bname, body in forward_messages:
                if body and body[0][1]:
                    await self.send_text(body[0][1])
                    await asyncio.sleep(0.6)
        return True

    async def _handle_download_by_number(self, number: int, user_id: str) -> bool:
        items = PixivNovelCommand._search_cache.get(user_id) or []
        if not items:
            await self.send_text("❌ 没有搜索记录，请先用 /novel search <关键词> 搜索\n（搜索记录会保留一段时间，若刚搜过仍提示此条，请重新 /novel search）")
            return False
        if number < 1 or number > len(items):
            await self.send_text("❌ 编号超出范围（1-" + str(len(items)) + "）")
            return False
        it = items[number - 1]
        series_id = it.get("series_id")
        nid = it.get("id")
        title = it.get("title", "(无标题)")
        try:
            if series_id:
                disp = it.get("display_title") or title
                await self.send_text("📥 编号 " + str(number) + " → 系列: " + disp + " (系列ID:" + series_id + ")")
                ok = await self._handle_series_by_id(series_id, number, user_id)
            elif nid:
                await self.send_text("📥 编号 " + str(number) + " → 单篇: " + title + " (作品ID:" + nid + ")")
                ok = await self._handle_single_by_id(nid, number, user_id)
            else:
                await self.send_text("❌ 该条目缺少小说 ID，无法下载")
                return False
            if ok:
                await self.send_text("✅ 编号 " + str(number) + " 下载完成")
            else:
                await self.send_text("❌ 编号 " + str(number) + " 下载失败，请检查 Cookie/代理或该作品是否可访问")
            return ok
        except Exception as e:
            logger.error("编号下载异常: %s", str(e), exc_info=True)
            await self.send_text("❌ 下载失败: " + str(e))
            return False

    async def _handle_series_by_id(self, series_id: str, number: int = 0, user_id: str = "") -> bool:
        """直接按系列ID下载（绕过 _extract_id，用于搜索结果编号下载）

        number 为搜索列表内部编号（非p站ID），用于文件名唯一索引便于对照。
        """
        sid = str(series_id)
        await self.send_text("📥 正在抓取系列信息: " + sid + " ...")
        series_meta, novels = await self.api.fetch_series_all_novels(
            sid, max_count=self.get_config("features.max_chapters_per_series", 999)
        )
        if series_meta.get("error"):
            await self.send_text("❌ 获取系列失败: " + str(series_meta['error']))
            return False
        if not novels:
            await self.send_text("😢 该系列没有抓取到任何章节，可能需要配置 Pixiv Cookie")
            return False

        title = series_meta.get("title", "未知系列")
        author = series_meta.get("userName", "") or series_meta.get("user_name", "")
        total_count = len(novels)
        await self.send_text("📚 《" + title + "》共 " + str(total_count) + " 章，开始下载全部正文，请稍候...")

        chapters_text: List[str] = []
        success_count = 0
        for idx, item in enumerate(novels, 1):
            nid = str(item.get("id"))
            ctitle = item.get("title", "(无标题)")
            await self.send_text("⬇️ [" + str(idx) + "/" + str(total_count) + "] " + ctitle)
            data = await self.api.fetch_novel_full(nid)
            if data.get("error"):
                logger.warning("第 %s 章抓取失败: %s", idx, data['error'])
                chapters_text.append("\n\n" + ("=" * 40) + "\n第" + str(idx) + "章: " + ctitle + "\n[抓取失败: " + str(data['error']) + "]\n" + ("=" * 40) + "\n")
                await asyncio.sleep(1)
                continue
            text = data.get("text") or data.get("content") or ""
            chapters_text.append(self._format_chapter(idx, total_count, ctitle, nid, data, text))
            success_count += 1
            await asyncio.sleep(1)

        await self.send_text("✅ 下载完成！成功 " + str(success_count) + "/" + str(total_count) + " 章\n📁 正在发送 txt 文件...")

        full_text = self._build_series_header(title, author, sid, total_count, success_count) + "\n\n"
        full_text += ("=" * 60) + "\n\n"
        full_text += ("=" * 60 + "\n\n").join(chapters_text)

        save_dir = self.get_config("features.save_dir", "data/pixiv_novel")
        os.makedirs(save_dir, exist_ok=True)
        # 文件名用内部编号做唯一索引，便于和搜索列表对照
        idx_tag = "N" + str(number) if number else "sid" + sid
        filename = self._make_unique_filename(title, idx_tag)
        file_path = os.path.join(save_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        logger.info("[保存] 编号%s 系列《%s》文件: %s", number, title, file_path)
        await self.send_text("📁 文件已保存: " + filename)
        ok = await self._send_file(file_path, filename)
        if not ok:
            await self.send_text("⚠️ 文件发送失败，回退为分段文本发送...")
            await self._send_long_text(full_text)
        return True

    async def _handle_single_by_id(self, novel_id: str, number: int = 0, user_id: str = "") -> bool:
        """直接按单篇ID下载（绕过 _extract_id，用于搜索结果编号下载）"""
        nid = str(novel_id)
        await self.send_text("📥 正在抓取小说 " + nid + " ...")
        data = await self.api.fetch_novel_full(nid)
        if data.get("error"):
            await self.send_text("❌ 获取小说失败: " + str(data['error']))
            return False
        title = data.get("title", "(无标题)")
        text = data.get("text") or data.get("content") or ""
        if not text:
            await self.send_text("⚠️ " + title + " 正文为空（可能需要配置 Cookie 或该作品为 R-18）")
            return False
        author = data.get("userName", "") or data.get("user_name", "")
        chapter_text = self._format_chapter(1, 1, title, nid, data, text)
        header = self._build_single_header(title, author, nid)
        full_text = header + "\n\n" + ("=" * 60) + "\n\n" + chapter_text

        save_dir = self.get_config("features.save_dir", "data/pixiv_novel")
        os.makedirs(save_dir, exist_ok=True)
        idx_tag = "N" + str(number) if number else "nid" + nid
        filename = self._make_unique_filename(title, idx_tag)
        file_path = os.path.join(save_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        logger.info("[保存] 编号%s 单篇《%s》文件: %s", number, title, file_path)
        await self.send_text("📁 文件已保存: " + filename + "\n✅ 正在发送 txt 文件...")
        ok = await self._send_file(file_path, filename)
        if not ok:
            await self.send_text("⚠️ 文件发送失败，回退为分段文本发送...")
            await self._send_long_text(full_text)
        return True

    async def _handle_series_full(self, target: str) -> bool:
        kind, sid = self._extract_id(target)
        if not sid:
            await self.send_text("❌ 无法识别系列 ID")
            return False
        if kind == "novel":
            return await self._handle_single(target)

        await self.send_text("📥 正在抓取系列信息: " + sid + " ...")
        series_meta, novels = await self.api.fetch_series_all_novels(
            sid, max_count=self.get_config("features.max_chapters_per_series", 999)
        )
        if series_meta.get("error"):
            await self.send_text("❌ 获取系列失败: " + str(series_meta['error']))
            return False
        if not novels:
            await self.send_text("😢 该系列没有抓取到任何章节，可能需要配置 Pixiv Cookie")
            return False

        title = series_meta.get("title", "未知系列")
        author = series_meta.get("userName", "") or series_meta.get("user_name", "")
        total_count = len(novels)
        await self.send_text("📚 《" + title + "》共 " + str(total_count) + " 章，开始下载全部正文，请稍候...")

        chapters_text: List[str] = []
        success_count = 0
        for idx, item in enumerate(novels, 1):
            nid = str(item.get("id"))
            ctitle = item.get("title", "(无标题)")
            await self.send_text("⬇️ [" + str(idx) + "/" + str(total_count) + "] " + ctitle)
            data = await self.api.fetch_novel_full(nid)
            if data.get("error"):
                logger.warning("第 %s 章抓取失败: %s", idx, data['error'])
                chapters_text.append("\n\n" + ("=" * 40) + "\n第" + str(idx) + "章: " + ctitle + "\n[抓取失败: " + str(data['error']) + "]\n" + ("=" * 40) + "\n")
                await asyncio.sleep(1)
                continue
            text = data.get("text", "")
            if not text:
                logger.warning("第 %s 章正文为空", idx)
                chapters_text.append("\n\n" + ("=" * 40) + "\n第" + str(idx) + "章: " + ctitle + "\n[正文为空]\n" + ("=" * 40) + "\n")
                await asyncio.sleep(1)
                continue
            chapters_text.append(self._format_chapter(idx, total_count, ctitle, nid, data, text))
            success_count += 1
            await asyncio.sleep(1)

        header = self._build_series_header(title, author, sid, total_count, success_count)
        full_text = header + "\n\n" + ("=" * 60) + "\n\n" + "\n".join(chapters_text)

        save_dir = self.get_config("features.save_dir", "data/pixiv_novel")
        os.makedirs(save_dir, exist_ok=True)
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:50]
        filename = safe_title + "_" + sid + ".txt"
        file_path = os.path.join(save_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        await self.send_text("✅ 下载完成！成功 " + str(success_count) + "/" + str(total_count) + " 章\n📁 正在发送 txt 文件...")
        ok = await self._send_file(file_path, filename)
        if not ok:
            await self.send_text("⚠️ 文件发送失败，回退为分段文本发送...")
            await self._send_long_text(full_text)
        return True

    async def _handle_series_list_only(self, target: str) -> bool:
        kind, sid = self._extract_id(target)
        if not sid:
            await self.send_text("❌ 无法识别系列 ID")
            return False
        if kind == "novel":
            await self.send_text("❌ list 子命令仅支持小说系列 URL/ID")
            return False
        series_meta, novels = await self.api.fetch_series_all_novels(
            sid, max_count=self.get_config("features.max_chapters_per_series", 999)
        )
        if series_meta.get("error"):
            await self.send_text("❌ 获取系列失败: " + str(series_meta['error']))
            return False
        if not novels:
            await self.send_text("😢 该系列没有抓取到任何章节")
            return False
        await self._send_series_overview(series_meta, novels, sid)
        return True

    async def _handle_single(self, target: str) -> bool:
        kind, nid = self._extract_id(target)
        if not nid:
            await self.send_text("❌ 无法识别小说 ID")
            return False
        if kind == "series":
            await self.send_text("❌ read 子命令仅支持单篇小说 URL/ID")
            return False
        await self.send_text("📥 正在抓取小说 " + nid + " ...")
        data = await self.api.fetch_novel_full(nid)
        if data.get("error"):
            await self.send_text("❌ 获取小说失败: " + str(data['error']))
            return False
        title = data.get("title", "(无标题)")
        text = data.get("text", "")
        if not text:
            await self.send_text("⚠️ " + title + " 正文为空（可能需要配置 Cookie 或该作品为 R-18）")
            return False
        author = data.get("userName", "") or data.get("user_name", "")
        chapter_text = self._format_chapter(1, 1, title, nid, data, text)
        header = self._build_single_header(title, author, nid)
        full_text = header + "\n\n" + ("=" * 60) + "\n\n" + chapter_text

        save_dir = self.get_config("features.save_dir", "data/pixiv_novel")
        os.makedirs(save_dir, exist_ok=True)
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:50]
        filename = safe_title + "_" + nid + ".txt"
        file_path = os.path.join(save_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        await self.send_text("✅ 下载完成！\n📁 正在发送 txt 文件...")
        ok = await self._send_file(file_path, filename)
        if not ok:
            await self.send_text("⚠️ 文件发送失败，回退为分段文本发送...")
            await self._send_long_text(full_text)
        return True

    def _build_series_header(self, title: str, author: str, sid: str, total: int, success: int) -> str:
        lines = ["=" * 60, "  " + title, "=" * 60]
        if author:
            lines.append("作者: " + author)
        lines.append("系列ID: " + sid)
        lines.append("章节数: " + str(success) + "/" + str(total))
        lines.append("来源: https://www.pixiv.net/novel/series/" + sid)
        lines.append("抓取时间: " + time.strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("=" * 60)
        return "\n".join(lines)

    def _build_single_header(self, title: str, author: str, nid: str) -> str:
        lines = ["=" * 60, "  " + title, "=" * 60]
        if author:
            lines.append("作者: " + author)
        lines.append("小说ID: " + nid)
        lines.append("来源: https://www.pixiv.net/novel/show.php?id=" + nid)
        lines.append("抓取时间: " + time.strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("=" * 60)
        return "\n".join(lines)

    def _format_chapter(self, idx: int, total: int, title: str, nid: str, data: Dict[str, Any], text: str) -> str:
        author = data.get("userName", "") or data.get("user_name", "")
        tags = data.get("tags", {})
        if isinstance(tags, dict):
            tag_list = [t.get("tag") or t for t in (tags.get("tags") or [])]
        else:
            tag_list = list(tags)
        lines = ["第 " + str(idx) + "/" + str(total) + " 章  " + title, "-" * 40]
        if author:
            lines.append("作者: " + author)
        if tag_list:
            lines.append("标签: " + " ".join(str(t) for t in tag_list[:10]))
        lines.append("链接: https://www.pixiv.net/novel/show.php?id=" + nid)
        lines.append("-" * 40)
        lines.append("")
        lines.append(text)
        return "\n".join(lines)

    async def _send_series_overview(self, series_meta: Dict[str, Any], novels: List[Dict[str, Any]], sid: str) -> None:
        title = series_meta.get("title", "未知系列")
        author = series_meta.get("userName", "") or series_meta.get("user_name", "")
        total = series_meta.get("total") or series_meta.get("novel_count") or len(novels)
        desc = (series_meta.get("caption", "") or "").strip()
        header = "📚 小说系列: " + title + "\n"
        if author:
            header += "👤 作者: " + author + "\n"
        header += "🔢 共 " + str(total) + " 章"
        if desc:
            header += "\n📝 " + desc[:300]
        header += "\n🔗 https://www.pixiv.net/novel/series/" + sid + "\n"
        toc_lines = ["", "📖 章节目录:"]
        for i, item in enumerate(novels, 1):
            ntitle = item.get("title", "(无标题)")
            nnid = item.get("id", "")
            toc_lines.append(str(i) + ". " + ntitle + " (id:" + str(nnid) + ")")
        text = header + "\n".join(toc_lines)
        text += "\n\n(仅列出目录，如需下载全文请用 /novel <系列ID> 或 /novel read <单篇ID>)"
        await self._send_long_text(text)

    async def _send_long_text(self, text: str) -> None:
        chunks = self._split_text(text, self.MAX_TEXT_PER_NODE)
        use_forward = self.get_config("features.use_forward_message", True)
        if use_forward and len(chunks) > 1:
            bot_qq = str(global_config.bot.qq_account)
            bot_name = str(global_config.bot.nickname)
            forward_messages = [(bot_qq, bot_name, [("text", chunk)]) for chunk in chunks]
            await self.send_forward(forward_messages, storage_message=True)
        else:
            for i, chunk in enumerate(chunks):
                await self.send_text(chunk)
                if i < len(chunks) - 1:
                    await asyncio.sleep(1)

    def _split_text(self, text: str, max_len: int) -> List[str]:
        if len(text) <= max_len:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + max_len, len(text))
            if end < len(text):
                nl = text.rfind("\n", start, end)
                if nl != -1 and nl > start + max_len // 2:
                    end = nl + 1
            chunks.append(text[start:end])
            start = end
        return chunks

    def _check_cooldown(self, user_id: str, cooldown: int) -> dict:
        self._cleanup_cooldown_cache(cooldown)
        if user_id not in self.cooldown_cache:
            return {"ready": True, "remaining": 0}
        elapsed = time.time() - self.cooldown_cache[user_id]
        if elapsed >= cooldown:
            return {"ready": True, "remaining": 0}
        return {"ready": False, "remaining": int(cooldown - elapsed) + 1}

    def _update_cooldown(self, user_id: str):
        self.cooldown_cache[user_id] = time.time()

    def _cleanup_cooldown_cache(self, cooldown: int):
        if len(self.cooldown_cache) <= self.COOLDOWN_CLEANUP_THRESHOLD:
            return
        current_time = time.time()
        expired = [uid for uid, t in self.cooldown_cache.items() if current_time - t > cooldown]
        for uid in expired:
            del self.cooldown_cache[uid]
        if len(self.cooldown_cache) > self.MAX_COOLDOWN_CACHE_SIZE:
            sorted_items = sorted(self.cooldown_cache.items(), key=lambda x: x[1])
            excess = len(self.cooldown_cache) - self.MAX_COOLDOWN_CACHE_SIZE
            for uid, _ in sorted_items[:excess]:
                del self.cooldown_cache[uid]
            logger.info("冷却缓存已清理 %s 个过期条目", len(expired))


@register_plugin
class PixivNovelPlugin(BasePlugin):
    """Pixiv 小说抓取插件（下载为 txt 文件发送）"""

    plugin_name: str = "pixiv_novel_plugin"
    enable_plugin: bool = True
    dependencies: List[str] = []
    python_dependencies: List[str] = ["aiohttp"]
    config_file_name: str = "config.toml"

    config_section_descriptions = {
        "plugin": "插件基本配置",
        "components": "组件启用控制",
        "auth": "Pixiv 鉴权与权限配置",
        "network": "网络配置",
        "napcat": "NapCat OneBot HTTP API 配置（用于发送文件）",
        "features": "功能配置",
    }

    config_schema: dict = {
        "plugin": {
            "config_version": ConfigField(type=str, default="1.4.4", description="配置文件版本"),
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
        },
        "components": {
            "enable_command": ConfigField(type=bool, default=True, description="是否启用/novel命令"),
        },
        "auth": {
            "pixiv_cookie": ConfigField(
                type=str, default="",
                description="Pixiv 登录 Cookie (PHPSESSID=...)，用于抓取登录后可见内容。留空则匿名访问",
            ),
            "allow_qq_list": ConfigField(
                type=list, default=[],
                description="允许触发 /novel 命令的 QQ 号白名单，如 [123456, 789012]。留空则所有人可用（不推荐，涉及R18管控）",
            ),
        },
        "network": {
            "proxy": ConfigField(
                type=str, default="",
                description="HTTP 代理地址 (如 http://127.0.0.1:7890)，留空不使用代理",
            ),
        },
        "napcat": {
            "host": ConfigField(type=str, default="127.0.0.1", description="OneBot HTTP API 主机"),
            "port": ConfigField(type=int, default=5700, description="OneBot HTTP API 端口"),
            "token": ConfigField(type=str, default="", description="OneBot HTTP API Token，未启用鉴权留空"),
        },
        "features": {
            "cooldown_seconds": ConfigField(type=int, default=30, description="命令冷却时间(秒)"),
            "api_timeout": ConfigField(type=int, default=30, description="API请求超时时间(秒)"),
            "max_chapters_per_series": ConfigField(type=int, default=999, description="抓取系列时最多下载的章节数，999 表示全部"),
            "use_forward_message": ConfigField(type=bool, default=True, description="文件发送失败时是否用合并转发格式回退发送长文"),
            "save_dir": ConfigField(type=str, default="data/pixiv_novel", description="txt 文件保存目录"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        self._validate_config()
        components = []
        if self.get_config("components.enable_command", True):
            components.append((PixivNovelCommand.get_command_info(), PixivNovelCommand))
        return components

    def _validate_config(self):
        max_ch = self.get_config("features.max_chapters_per_series", 999)
        if not isinstance(max_ch, int) or max_ch < 1:
            logger.warning("配置 max_chapters_per_series 无效: %s，将使用默认值 999", max_ch)
        timeout = self.get_config("features.api_timeout", 30)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            logger.warning("配置 api_timeout 无效: %s，将使用默认值 30", timeout)
        cooldown = self.get_config("features.cooldown_seconds", 30)
        if not isinstance(cooldown, (int, float)) or cooldown < 0:
            logger.warning("配置 cooldown_seconds 无效: %s，将使用默认值 30", cooldown)
        port = self.get_config("napcat.port", 5700)
        if not isinstance(port, int) or port <= 0:
            logger.warning("配置 napcat.port 无效: %s，将使用默认值 5700", port)
        cookie = self.get_config("auth.pixiv_cookie", "")
        if not cookie:
            logger.warning("未配置 pixiv_cookie，匿名访问可能无法抓取 R-18 及部分作品")
        logger.info("Pixiv小说插件配置校验完成")
