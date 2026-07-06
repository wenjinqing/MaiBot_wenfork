"""
美女图片模块 - JK / 白丝 / 黑丝

使用 xxapi（JSON 或 302 跟跳到直链）。
"""

from typing import Optional, Tuple

import aiohttp

from src.common.logger import get_logger
from src.plugin_system.base.base_action import BaseAction, ActionActivationType
from src.plugin_system.base.base_command import BaseCommand
from src.plugin_system.base.component_types import ChatMode

logger = get_logger("entertainment_plugin.body_part")

JK_XXAPI_DEFAULT_URL = "https://v2.xxapi.cn/api/jk?return=json"
BAISI_XXAPI_DEFAULT_URL = "https://v2.xxapi.cn/api/baisi?return=json"
HEISI_XXAPI_DEFAULT_URL = "https://v2.xxapi.cn/api/heisi?return=json"


async def fetch_xxapi_image_url(api_url: str, log_prefix: str) -> Optional[str]:
    """请求 xxapi 随机图接口，返回可直接发送的图片 URL。

    - ``return=json``：解析 ``{"code":200,"data":"https://..."}``.
    - ``return=302``：跟随重定向，使用最终 URL。
    """
    timeout = aiohttp.ClientTimeout(total=20)
    headers = {"User-Agent": "MaiBot-JunJun/entertainment_plugin"}
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url, headers=headers, allow_redirects=True) as resp:
                final_url = str(resp.url)
                if resp.status != 200:
                    logger.error(f"{log_prefix} xxapi HTTP {resp.status} final={final_url}")
                    return None

                payload = None
                try:
                    payload = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError, TypeError):
                    pass

                if isinstance(payload, dict):
                    if payload.get("code") != 200:
                        logger.error(f"{log_prefix} xxapi 业务错误: {payload}")
                        return None
                    data = payload.get("data")
                    if isinstance(data, str) and data.startswith(("http://", "https://")):
                        return data

                text_ct = (resp.headers.get("Content-Type") or "").lower()
                if resp.history or "image/" in text_ct:
                    if final_url.startswith(("http://", "https://")):
                        return final_url

                logger.error(f"{log_prefix} xxapi 无有效图片 URL payload={payload!r} final={final_url}")
                return None
    except Exception as e:
        logger.error(f"{log_prefix} xxapi 请求失败: {e}", exc_info=True)
        return None


class XxapiImageActionBase(BaseAction):
    """xxapi 图片 Action 基类：取图—发图—错误兜底。子类只需声明配置 key 和文案。"""

    # 子类必须覆盖
    _config_key: str = ""
    _default_url: str = ""
    _unavailable_msg: str = "❌ 图片接口暂时不可用，稍后再试喵。"
    _log_name: str = "图片"

    activation_type = ActionActivationType.KEYWORD
    mode_enable = ChatMode.ALL
    parallel_action = False
    action_parameters = {}
    associated_types = ["image"]

    async def execute(self) -> Tuple[bool, str]:
        try:
            api_url = self.get_config(self._config_key, self._default_url)
            image_url = await fetch_xxapi_image_url(api_url, self.log_prefix)
            if not image_url:
                await self.send_text(self._unavailable_msg)
                return False, f"{self._log_name} API 无有效图片地址"

            await self.send_text("看吧！涩批！")
            await self.send_custom("imageurl", image_url)
            logger.info(f"{self.log_prefix} {self._log_name}发送成功")
            return True, f"成功获取并发送{self._log_name}"
        except Exception as e:
            logger.error(f"{self.log_prefix} {self._log_name}获取出错: {e}")
            await self.send_text(f"❌ 图片获取出错: {e}")
            return False, f"图片获取出错: {e}"


class BaisiImageAction(XxapiImageActionBase):
    """白丝图 Action — xxapi baisi。"""

    action_name = "baisi_image_action"
    action_description = "获取白丝主题图片并发送（非 JK）"

    activation_keywords = ["看看白丝", "看白丝", "康康白丝"]
    keyword_case_sensitive = False

    action_require = [
        "当用户明确要看白丝、白丝类图片时使用",
        "当用户说「看看白丝」等与 JK 无关时使用",
        "不要用于用户只说看看JK或JK制服的场景（应使用 jk_image_action）",
    ]

    _config_key = "body_part.baisi_api_url"
    _default_url = BAISI_XXAPI_DEFAULT_URL
    _unavailable_msg = "❌ 白丝图接口暂时不可用，稍后再试喵。"
    _log_name = "白丝图"


class HeisiImageAction(XxapiImageActionBase):
    """黑丝图 Action — xxapi heisi。"""

    action_name = "heisi_image_action"
    action_description = "获取黑丝主题图片并发送（非 JK）"

    activation_keywords = ["看看黑丝", "看黑丝", "康康黑丝"]
    keyword_case_sensitive = False

    action_require = [
        "当用户明确要看黑丝、黑丝类图片时使用",
        "当用户说「看看黑丝」等与 JK 无关时使用",
        "不要用于用户只说看看JK或JK制服的场景（应使用 jk_image_action）",
    ]

    _config_key = "body_part.heisi_api_url"
    _default_url = HEISI_XXAPI_DEFAULT_URL
    _unavailable_msg = "❌ 黑丝图接口暂时不可用，稍后再试喵。"
    _log_name = "黑丝图"


class JKImageAction(XxapiImageActionBase):
    """JK 图片 Action — xxapi jk。"""

    action_name = "jk_image_action"
    action_description = "获取JK图片并发送"

    activation_keywords = ["看看JK", "看看jk", "看JK", "看jk", "康康JK", "康康jk"]
    keyword_case_sensitive = False

    action_require = [
        "当用户要求看JK、JK制服类图片时使用",
        "当用户说'看看JK'或'看看jk'等时使用",
        "当用户明确要看黑丝或白丝时不要使用本动作（应使用 heisi_image_action 或 baisi_image_action）",
    ]

    _config_key = "body_part.jk_api_url"
    _default_url = JK_XXAPI_DEFAULT_URL
    _unavailable_msg = "❌ JK 图片接口暂时不可用，稍后再试喵。"
    _log_name = "JK图片"


class JKImageCommand(BaseCommand):
    """JK图片 Command - 手动图片获取命令"""

    command_name = "jk_image_command"
    command_description = "获取JK图片"

    command_pattern = r"^/(看看[Jj][Kk]|看[Jj][Kk]|康康[Jj][Kk])(?:\s+(?P<class_param>\d+))?$"
    command_help = "获取JK图片。用法：/看看JK"
    command_examples = ["/看看JK", "/看JK"]
    intercept_message = True

    async def execute(self) -> Tuple[bool, str, bool]:
        try:
            if self.matched_groups.get("class_param"):
                logger.debug(f"{self.log_prefix} /看看JK 附带分类参数已忽略（当前使用 xxapi，不支持指定 class）")

            jk_api_url = self.get_config("body_part.jk_api_url", JK_XXAPI_DEFAULT_URL)
            image_url = await fetch_xxapi_image_url(jk_api_url, self.log_prefix)
            if not image_url:
                await self.send_text("❌ JK 图片接口暂时不可用，稍后再试喵。")
                return False, "JK API 无有效图片地址", True

            await self.send_text("看吧！涩批！")
            await self.send_custom("imageurl", image_url)
            logger.info(f"{self.log_prefix} 执行看看JK命令，已发送")
            return True, "成功获取并发送JK图片", True

        except Exception as e:
            logger.error(f"看看JK命令执行出错: {e}")
            await self.send_text(f"❌ 图片获取出错: {e}")
            return False, f"图片获取出错: {e}", True
