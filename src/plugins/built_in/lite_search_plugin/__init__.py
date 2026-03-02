"""
轻量级网络搜索插件 - 增强版
支持多个搜索引擎备用，token 消耗低
"""
import asyncio
import aiohttp
import json
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin

from src.common.logger import get_logger
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseTool,
    ComponentInfo,
    ToolParamType,
)

logger = get_logger("lite_search")


class LiteSearchTool(BaseTool):
    """轻量级搜索工具"""

    @property
    def info(self) -> ComponentInfo:
        return ComponentInfo(
            name="web_search",
            description="搜索互联网获取最新信息。返回简洁的搜索结果（标题+摘要）。适用于查询新闻、事实、定义等。",
            parameters={
                "query": {
                    "type": ToolParamType.STRING,
                    "description": "搜索关键词",
                    "required": True,
                }
            },
        )

    async def execute(self, query: str, **kwargs) -> str:
        """执行搜索"""
        try:
            logger.info(f"[搜索] 关键词: {query}")

            # 尝试多个搜索引擎
            results = await self._search_with_fallback(query)

            if not results:
                return "未找到相关结果，请尝试更换关键词"

            # 格式化结果（简洁格式，减少 token）
            output = [f"搜索结果（共 {len(results)} 条）：\n"]
            for i, result in enumerate(results[:5], 1):  # 最多5条
                output.append(
                    f"{i}. {result['title']}\n"
                    f"   {result['snippet']}\n"
                    f"   {result['url']}"
                )

            return "\n\n".join(output)

        except Exception as e:
            logger.error(f"[搜索] 失败: {e}")
            return f"搜索失败: {str(e)}"

    async def _search_with_fallback(self, query: str) -> List[Dict[str, str]]:
        """使用多个搜索引擎，自动切换（优先使用最稳定的引擎）"""
        # 优先：Bing（测试显示最稳定）
        results = await self._search_bing(query)
        if results:
            logger.info(f"[搜索] Bing 成功，返回 {len(results)} 条结果")
            return results

        # 备用：百度
        results = await self._search_baidu(query)
        if results:
            logger.info(f"[搜索] Baidu 成功，返回 {len(results)} 条结果")
            return results

        # 备用：DuckDuckGo Lite
        results = await self._search_duckduckgo_lite(query)
        if results:
            logger.info(f"[搜索] DuckDuckGo 成功，返回 {len(results)} 条结果")
            return results

        return []

    async def _search_duckduckgo_lite(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """DuckDuckGo Lite 版本（HTML）"""
        try:
            url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        return []

                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    results = []

                    # 查找结果表格
                    for row in soup.find_all("tr")[:max_results * 2]:  # 多取一些以防过滤
                        try:
                            # 查找链接
                            link = row.find("a", class_="result-link")
                            if not link:
                                continue

                            title = link.get_text(strip=True)
                            url_val = link.get("href", "")

                            # 查找摘要
                            snippet_td = row.find("td", class_="result-snippet")
                            snippet = snippet_td.get_text(strip=True) if snippet_td else ""

                            if title and url_val and not url_val.startswith("/"):
                                results.append({
                                    "title": title,
                                    "url": url_val,
                                    "snippet": snippet[:200]
                                })

                                if len(results) >= max_results:
                                    break

                        except Exception:
                            continue

                    return results

        except Exception as e:
            logger.debug(f"[搜索] DuckDuckGo 失败: {e}")
            return []

    async def _search_bing(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Bing 搜索"""
        try:
            url = f"https://www.bing.com/search?q={quote_plus(query)}&ensearch=1"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        return []

                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    results = []

                    # Bing 搜索结果
                    for item in soup.find_all("li", class_="b_algo", limit=max_results):
                        try:
                            title_tag = item.find("h2")
                            if not title_tag:
                                continue

                            link = title_tag.find("a")
                            if not link:
                                continue

                            title = link.get_text(strip=True)
                            url_val = link.get("href", "")

                            # 摘要
                            snippet_tag = item.find("p") or item.find("div", class_="b_caption")
                            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                            if title and url_val:
                                results.append({
                                    "title": title,
                                    "url": url_val,
                                    "snippet": snippet[:200]
                                })

                        except Exception:
                            continue

                    return results

        except Exception as e:
            logger.debug(f"[搜索] Bing 失败: {e}")
            return []

    async def _search_baidu(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """百度搜索（备用）"""
        try:
            url = f"https://www.baidu.com/s?wd={quote_plus(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        return []

                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    results = []

                    # 百度搜索结果
                    for item in soup.find_all("div", class_="result", limit=max_results):
                        try:
                            title_tag = item.find("h3") or item.find("a")
                            if not title_tag:
                                continue

                            link = title_tag if title_tag.name == "a" else title_tag.find("a")
                            if not link:
                                continue

                            title = link.get_text(strip=True)
                            url_val = link.get("href", "")

                            # 摘要
                            snippet_tag = item.find("div", class_="c-abstract") or item.find("span", class_="content-right_8Zs40")
                            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                            if title and url_val:
                                results.append({
                                    "title": title,
                                    "url": url_val,
                                    "snippet": snippet[:200]
                                })

                        except Exception:
                            continue

                    return results

        except Exception as e:
            logger.debug(f"[搜索] Baidu 失败: {e}")
            return []


@register_plugin
class LiteSearchPlugin(BasePlugin):
    """轻量级搜索插件"""

    @property
    def info(self) -> ComponentInfo:
        return ComponentInfo(
            name="lite_search",
            description="轻量级网络搜索插件（低 token 消耗，支持多搜索引擎）",
            version="1.0.1",
            author="MaiBot",
        )

    def on_load(self):
        """加载插件时注册工具"""
        self.register_tool(LiteSearchTool())
        logger.info("[轻量级搜索] 插件已加载（支持 Bing/Baidu/DuckDuckGo，优先 Bing）")

    def on_unload(self):
        """卸载插件"""
        logger.info("[轻量级搜索] 插件已卸载")
