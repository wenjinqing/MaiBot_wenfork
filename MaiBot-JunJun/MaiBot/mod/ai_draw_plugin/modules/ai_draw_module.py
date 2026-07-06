"""
AI绘图模块 —— 统一走 ModelScope 文生图 API (api-inference.modelscope.cn)

AIDrawTool (LLM 自主调用) 和 AIDrawCommand (/draw 命令) 共用 generate_modelscope_images()。
"""

import re
import json
import urllib.parse
import aiohttp
import asyncio
import random
import time
from typing import Tuple, List, Dict, Optional, Any
from src.common.logger import get_logger
from src.plugin_system.base.base_action import BaseAction
from src.plugin_system.base.base_command import BaseCommand
from src.plugin_system.base.component_types import ActionActivationType
from src.config.config import global_config, model_config
from src.llm_models.utils_model import LLMRequest
from src.plugin_system.apis import send_api

logger = get_logger("entertainment_plugin.ai_draw")

# ---------------------------------------------------------------------------
# Prompt 扩写模板（生图提示词专家）—— 与 auto_image_tool.py 共用
# ---------------------------------------------------------------------------
_PROMPT_EXPAND_HEADER = """你是AI绘画提示词助手。用户给你一个【主体】，你只负责为它补充画面细节，帮它生成更好的图。

铁律：
1. 【绝不改变主体】用户画「猫娘」就必须是猫娘，严禁把它替换或引申成石头、风景、极简、禅意等任何别的东西。主体是用户定的，你只是配角。
2. 你只补充这些：场景/背景、光照、氛围、构图、画质标签（如 masterpiece, best quality）、与主体协调的服饰/表情/动作。
3. 【不要重复或翻译主体本身】主体会被自动放在最前面，你只输出补充的细节。
4. 补充的细节必须和主体协调：画猫娘就配二次元/室内/温馨等场景，绝不配工业废墟、极简留白这种不搭的风格。
5. 输出中英文混合标签，逗号分隔，15-35个词。
6. 只输出补充的细节标签，不要解释、不要引号、不要写出主体词本身。

示例：
主体：猫娘
补充：cozy bedroom, warm sunlight through window, soft bokeh, anime illustration, masterpiece, best quality, detailed eyes, gentle smile, cat ears, fluffy tail, 温馨室内 柔光 二次元
主体：jk少女
补充：school rooftop, blue sky, cherry blossoms, soft daylight, masterpiece, best quality, detailed serafuku, gentle breeze, depth of field, 校园 春天 日系
主体：星空
补充：milky way, glowing stars, nebula, deep night, cinematic lighting, masterpiece, best quality, ultra detailed, wide angle, dreamy atmosphere, 夜空 银河 唯美"""


def _build_expand_prompt(user_prompt: str) -> str:
    return f"""{_PROMPT_EXPAND_HEADER}

主体：{user_prompt}
补充："""


# 图片缓存：{chat_id: {"images": [...], "sent_indices": set(), "prompt": str, "timestamp": float}}
_image_cache: Dict[str, Dict] = {}
_image_cache_lock = asyncio.Lock()  # 缓存并发保护
CACHE_EXPIRE_TIME = 300  # 缓存过期时间（秒）- 5分钟
_cache_cleanup_task: Optional[asyncio.Task] = None


async def _cleanup_expired_image_cache():
    """后台任务：定期清理过期的图片缓存"""
    while True:
        try:
            await asyncio.sleep(300)  # 每5分钟检查一次

            async with _image_cache_lock:
                current_time = time.time()
                expired_keys = [
                    key for key, data in _image_cache.items()
                    if current_time - data.get("timestamp", 0) >= CACHE_EXPIRE_TIME
                ]

                for key in expired_keys:
                    del _image_cache[key]

                if expired_keys:
                    logger.info(f"清理了 {len(expired_keys)} 个过期图片缓存")

        except asyncio.CancelledError:
            logger.debug("图片缓存清理任务被取消")
            break
        except Exception as e:
            logger.error(f"图片缓存清理任务出错: {e}", exc_info=True)


def start_image_cache_cleanup():
    """启动图片缓存清理任务"""
    global _cache_cleanup_task
    if _cache_cleanup_task is None or _cache_cleanup_task.done():
        _cache_cleanup_task = asyncio.create_task(_cleanup_expired_image_cache())
        logger.info("图片缓存清理任务已启动")


def calculate_prompt_similarity(user_prompt: str, creation_prompt: str) -> float:
    """
    计算用户描述词和生成提示词的相似度（智能匹配算法）

    算法说明：
    - 使用加权词匹配：风格关键词（如"二次元"、"日系"）权重更高
    - 综合三种匹配方式：子串匹配(60%) + 风格加分(30%) + 字符匹配(10%)
    - 自动降低不符合人设的风格（如"手绘"、"素描"）权重

    Args:
        user_prompt: 用户输入的描述词（如"猫娘 可爱 二次元"）
        creation_prompt: API返回的创作提示词（如"日系二次元插画风格 猫娘少女"）

    Returns:
        相似度分数 (0.0-1.0之间，越高越匹配)
    """
    if not user_prompt or not creation_prompt:
        return 0.0

    # 转换为小写进行匹配
    user_lower = user_prompt.lower()
    creation_lower = creation_prompt.lower()

    # 定义风格关键词及其权重（这些词更重要）
    style_keywords = {
        '二次元': 2.0, '日系': 2.0, '插画': 1.8, '动漫': 1.8,
        'anime': 2.0, '唯美': 1.5, '精致': 1.5, '细腻': 1.5,
        '可爱': 1.3, '萌': 1.3, '猫娘': 1.5, '少女': 1.3,
        # 降低某些不太符合人设的风格权重
        '手绘': 0.5, '绘本': 0.5, '水彩': 0.5, '素描': 0.5
    }

    # 方法1: 加权子串匹配
    substring_score = 0.0
    user_words = user_lower.split()
    total_weight = 0.0

    for word in user_words:
        # 获取该词的权重（默认为1.0）
        weight = style_keywords.get(word, 1.0)
        total_weight += weight

        if word in creation_lower:
            substring_score += weight

    if total_weight > 0:
        substring_score = substring_score / total_weight

    # 方法2: 检查creation_prompt中的风格关键词
    style_bonus = 0.0
    for style_word, weight in style_keywords.items():
        if style_word in creation_lower:
            # 如果用户描述词中也有这个词，给予额外加分
            if style_word in user_lower:
                style_bonus += 0.1 * weight
            # 如果是负权重的词（如"手绘"），扣分
            elif weight < 1.0:
                style_bonus -= 0.1 * (1.0 - weight)

    # 方法3: 字符级匹配 (适合中文单字匹配)
    char_score = 0.0
    user_chars = set(user_lower)
    creation_chars = set(creation_lower)

    if user_chars:
        common_chars = user_chars & creation_chars
        char_score = len(common_chars) / len(user_chars)

    # 综合得分 (子串匹配权重最高，风格加分次之，字符匹配最低)
    final_score = substring_score * 0.6 + style_bonus * 0.3 + char_score * 0.1

    # 确保分数在0-1范围内
    final_score = max(0.0, min(1.0, final_score))

    return final_score


def select_best_image(user_prompt: str, images: List[Dict], mode: str = "best") -> Tuple[List[Dict], int]:
    """
    从多张图片中选择最佳图片（支持三种模式）

    工作原理：
    - best模式：使用智能算法计算每张图的相似度，选择最匹配的
    - random模式：随机选择一张图片
    - all模式：返回所有图片

    Args:
        user_prompt: 用户输入的描述词（如"猫娘 可爱"）
        images: API返回的图片列表，每张图包含url和creation_prompt
        mode: 选择模式
            - "best" = 最佳匹配（默认，优先匹配日系二次元风格）
            - "random" = 随机选择
            - "all" = 返回全部图片

    Returns:
        (选择的图片列表, 选择的索引)
        - 图片列表：包含选中的图片数据
        - 索引：选中图片在原列表中的位置（用于缓存管理）
    """
    if not images:
        return [], -1

    if mode == "all":
        return images, -1
    elif mode == "random":
        idx = random.randint(0, len(images) - 1)
        return [images[idx]], idx
    elif mode == "best":
        # 计算每张图片的匹配分数
        scored_images = []
        for idx, img in enumerate(images):
            creation_prompt = img.get("creation_prompt", "")
            similarity = calculate_prompt_similarity(user_prompt, creation_prompt)
            scored_images.append((similarity, idx, img))
            logger.debug(f"图片相似度: {similarity:.2f} - {creation_prompt[:50]}...")

        # 选择得分最高的图片
        scored_images.sort(key=lambda x: x[0], reverse=True)
        best_score, best_idx, best_image = scored_images[0]

        logger.info(f"选择最佳图片,相似度: {best_score:.2f}")
        return [best_image], best_idx
    else:
        # 默认返回第一张
        return [images[0]], 0


async def get_cached_images(chat_id: str) -> Optional[Dict]:
    """
    获取缓存的图片（线程安全），如果过期则返回None

    Args:
        chat_id: 聊天ID

    Returns:
        缓存数据或None
    """
    async with _image_cache_lock:
        if chat_id not in _image_cache:
            return None

        cache = _image_cache[chat_id]
        # 检查是否过期
        if time.time() - cache.get("timestamp", 0) > CACHE_EXPIRE_TIME:
            del _image_cache[chat_id]
            logger.debug(f"图片缓存已过期并删除: {chat_id}")
            return None

        return cache


async def cache_images(chat_id: str, images: List[Dict], prompt: str, sent_index: int):
    """
    缓存图片列表（线程安全）

    Args:
        chat_id: 聊天ID
        images: 图片列表
        prompt: 描述词
        sent_index: 已发送的图片索引
    """
    async with _image_cache_lock:
        _image_cache[chat_id] = {
            "images": images,
            "sent_indices": {sent_index} if sent_index >= 0 else set(),
            "prompt": prompt,
            "timestamp": time.time()
        }
        logger.debug(f"图片缓存已设置: {chat_id}, 描述词={prompt}, 图片数={len(images)}")


async def get_next_unsent_image(chat_id: str) -> Optional[Tuple[Dict, int]]:
    """
    从缓存中获取下一张未发送的图片（线程安全）

    Args:
        chat_id: 聊天ID

    Returns:
        (图片数据, 索引) 或 None
    """
    async with _image_cache_lock:
        if chat_id not in _image_cache:
            return None

        cache = _image_cache[chat_id]
        # 检查是否过期
        if time.time() - cache.get("timestamp", 0) > CACHE_EXPIRE_TIME:
            del _image_cache[chat_id]
            logger.debug(f"图片缓存已过期: {chat_id}")
            return None

        images = cache["images"]
        sent_indices = cache["sent_indices"]

        # 找到未发送的图片
        for idx, img in enumerate(images):
            if idx not in sent_indices:
                sent_indices.add(idx)
                return img, idx

        # 所有图片都已发送
        return None


# ============ 生图模型路由 ============
# 红线：明确指向真实幼龄/未成年的词，命中即拒绝，绝不调用任何模型生成。
# 注意：「萝莉/正太/童颜」属于二次元画风/萌系词（可对应成年角色），不在此列；
#       只拦明确的幼龄指向词。底线词宁可漏放画风词，也不能漏拦「幼女」类。
_MINOR_BLOCK_WORDS: Tuple[str, ...] = (
    "幼女", "幼童", "幼儿", "幼齿", "幼龄", "低龄",
    "婴儿", "婴幼", "儿童", "女童", "男童", "童女",
    "小学生", "小学", "小女孩", "小男孩", "小孩", "未成年",
    "underage", "underaged", "preteen", "minor", "child", "children",
)

# 软色情/身体部位暗示词：命中则路由到微调模型（仅成人向，非露骨）。
_SUGGESTIVE_WORDS: Tuple[str, ...] = (
    "脚", "足", "丝袜", "黑丝", "白丝", "美腿", "大腿", "腿",
    "胸", "事业线", "乳", "爆乳", "巨乳", "胸部", "deep cleavage", "cleavage",
    "泳装", "比基尼", "bikini", "内衣", "内裤", "lingerie", "underwear",
    "屁股", "臀", "翘臀", "ass", "butt", "thigh", "feet", "foot", "stocking",
    "情趣", "诱惑", "性感", "sexy", "ecchi", "涩", "色气", "裸", "湿身",
    "捆绑", "兔女郎", "情趣内衣", "深沟", "露出",
)

# 二次元/动漫画风词：命中则路由到二次元特化模型（正常向，画动漫角色）。
_ANIME_WORDS: Tuple[str, ...] = (
    "二次元", "动漫", "动画", "漫画", "番剧", "二刺螈", "acg", "anime", "manga",
    "插画", "立绘", "同人", "galgame", "gal", "卡通", "萌系", "厚涂", "赛璐璐",
    "猫娘", "兽耳", "猫耳", "女仆", "jk", "和服", "洛丽塔", "lolita", "萝莉", "正太",
    "原神", "明日方舟", "崩坏", "碧蓝航线", "miku", "初音", "vtuber", "vup",
    "角色", "少女", "少年", "girl", "boy", "1girl", "character", "waifu",
)


def _norm(text: str) -> str:
    return (text or "").lower()


def is_minor_blocked(prompt: str) -> bool:
    """命中未成年红线词 → True（必须拒绝生成）。"""
    low = _norm(prompt)
    return any(w.lower() in low for w in _MINOR_BLOCK_WORDS)


def is_suggestive(prompt: str) -> bool:
    """命中软色情/身体部位暗示词 → True（路由到微调模型）。"""
    low = _norm(prompt)
    return any(w.lower() in low for w in _SUGGESTIVE_WORDS)


def is_anime(prompt: str) -> bool:
    """命中二次元/动漫画风词 → True（路由到二次元特化模型）。"""
    low = _norm(prompt)
    return any(w.lower() in low for w in _ANIME_WORDS)


def route_image_model(
    prompt: str,
    sfw_model: str,
    nsfw_model: str = "",
    anime_model: str = "",
) -> str:
    """根据 prompt 选择生图模型。优先级：软色情 > 二次元 > 默认。

    软色情优先级最高，因为二次元特化模型不含软色情内容，涩向必须走微调模型。
    """
    if nsfw_model and is_suggestive(prompt):
        return nsfw_model
    if anime_model and is_anime(prompt):
        return anime_model
    return sfw_model


async def generate_modelscope_images(
    prompt: str,
    api_key: str,
    model: str = "Tongyi-MAI/Z-Image-Turbo",
    timeout_sec: int = 60,
    poll_interval: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    使用 ModelScope 文生图异步生成图片。
    提交任务后轮询直至完成，返回 [{"url": str, "creation_prompt": str}, ...]。
    poll_interval: 轮询间隔（秒），默认 1 秒（ModelScope 图任务一般几秒完成）。
    """
    if not api_key:
        raise RuntimeError("未配置 ModelScope api_key（music_plugin config.toml [ai_draw].api_key）")

    # 红线拦截：未成年相关一律拒绝
    if is_minor_blocked(prompt):
        raise RuntimeError("MINOR_BLOCKED")

    base_url = "https://api-inference.modelscope.cn/"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    read_timeout = max(int(timeout_sec or 60), 30)
    timeout_obj = aiohttp.ClientTimeout(total=read_timeout + 120, connect=20, sock_read=read_timeout)
    interval = max(float(poll_interval or 0), 0.3)

    logger.info(f"ModelScope 生图: model={model} suggestive={is_suggestive(prompt)}")

    async with aiohttp.ClientSession() as session:
        # 1. 提交异步生成任务
        async with session.post(
            f"{base_url}v1/images/generations",
            headers={**headers, "X-ModelScope-Async-Mode": "true"},
            data=json.dumps({"model": model, "prompt": prompt}, ensure_ascii=False).encode("utf-8"),
            timeout=timeout_obj,
        ) as response:
            text = await response.text()
            if response.status != 200:
                snippet = text[:400].replace("\n", " ") if text else ""
                raise RuntimeError(f"提交生成任务失败 HTTP {response.status}: {snippet!r}")
            task_id = json.loads(text).get("task_id")
        if not task_id:
            raise RuntimeError("ModelScope 未返回 task_id")

        # 2. 轮询任务状态（最多约 120 次 * interval）
        for _ in range(120):
            await asyncio.sleep(interval)
            async with session.get(
                f"{base_url}v1/tasks/{task_id}",
                headers={**headers, "X-ModelScope-Task-Type": "image_generation"},
                timeout=timeout_obj,
            ) as result:
                result.raise_for_status()
                data = await result.json()

            status = data.get("task_status")
            if status == "SUCCEED":
                urls = data.get("output_images") or []
                images = [{"url": str(u), "creation_prompt": prompt} for u in urls if u]
                if not images:
                    raise RuntimeError("ModelScope 任务成功但未返回图片 URL")
                return images
            if status == "FAILED":
                raise RuntimeError(f"ModelScope 生成失败: {str(data)[:300]!r}")

        raise RuntimeError("ModelScope 生成超时")


class AIDrawAction(BaseAction):
    """AI绘画 Action —— planner 可见,LLM 可直接调用画图功能。

    LLM 不能画图,这是个工具调用桥梁:
    通过 LLM_JUDGE 激活,LLM 自主判断何时需要画图。
    执行时内部走原有扩写+ModelScope 生图链路。
    """

    action_name = "ai_draw"
    action_description = "AI绘图/生图：当用户要求画图、画个xxx、来张xxx、帮我画xxx时使用。根据描述词生成AI图片并发送。"
    activation_type = ActionActivationType.LLM_JUDGE
    parallel_action = False

    llm_judge_prompt = """
    # AI绘图工具
    当用户明确请求"画图"、"画xxx"、"帮我画xxx"、"来张xxx"、"生成xxx图"时触发。

    触发条件示例：
    - "画个猫娘"  "帮我画个jk"
    - "来张风景图"  "生成一张星空图"
    - "能帮我画一个xxx吗"

    以下情况 **不要触发**：
    - "每日一图"、"看看美女"等（这是随机图片,不是AI绘图,有专门的图片查看功能处理）
    - 用户发送图片/表情包求保存（这是表情包管理,跟AI绘图无关）
    - "换个风格/再来一张"（用专门的换风格功能）

    注意：这是AI绘图,可以根据描述词生成新图片。不是搜索已有图片。
    """

    async def check(self) -> bool:
        # LLM_JUDGE 模式,由 LLM 判断；这里兜底检查消息原文
        msg = getattr(getattr(self, "action_message", None), "processed_plain_text", "") or ""
        if not msg:
            return False
        patterns = [
            r"画个?([一]?[张幅]?)?\S",   # 画个xxx / 画一张xxx
            r"帮我画",
            r"来[张幅].*图",
            r"生成.*图",
            r"画[一]?[下个].*图",
            r"ai?画|绘画|绘图|生图|文生图",
        ]
        return any(re.search(p, msg) for p in patterns)

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行AI绘图: 从消息中提取描述词 → 扩写 → 路由 → 生图 → 发送"""
        try:
            # 从消息中提取描述词
            msg = getattr(getattr(self, "action_message", None), "processed_plain_text", "") or ""
            prompt = self._extract_prompt(msg)
            if not prompt or not prompt.strip():
                await self.send_text("要画什么呀？告诉我描述词喵~")
                return False, "未提取到描述词"

            logger.info(f"AI绘图 Action: 描述词={prompt!r}")

            # 1) prompt 扩写
            enable_expand = self.get_config("ai_draw.prompt_expand_enabled", True)
            if enable_expand:
                prompt = await self._expand_prompt(prompt)

            # 2) 未成年红线
            if is_minor_blocked(prompt):
                await self.send_text("这种不行哦，君君只画成年角色喵，换个描述吧~")
                return False, "命中未成年红线，拒绝生成"

            # 3) 路由模型
            image_model = self.get_config("ai_draw.image_model", "Tongyi-MAI/Z-Image-Turbo")
            nsfw_model = self.get_config("ai_draw.image_model_nsfw", "")
            anime_model = self.get_config("ai_draw.image_model_anime", "")
            use_model = route_image_model(prompt, image_model, nsfw_model, anime_model)

            # 4) 生图
            api_key = self.get_config("ai_draw.api_key", "")
            poll_interval = float(self.get_config("ai_draw.poll_interval", 1.0))
            timeout = self.get_config("ai_draw.timeout", 60)
            selection_mode = self.get_config("ai_draw.selection_mode", "best")

            images = await generate_modelscope_images(
                prompt, api_key, use_model, int(timeout) if timeout else 60, poll_interval
            )
            logger.info(f"ModelScope 返回 {len(images)} 张图片")

            # 5) 选最佳
            selected_images, selected_idx = select_best_image(prompt, images, selection_mode)
            if not selected_images:
                await self.send_text("图生成了但没选出来，再试一次喵~")
                return False, "选择图片失败"

            # 6) 缓存
            chat_id = self.chat_stream.stream_id if self.chat_stream else None
            if chat_id:
                await cache_images(chat_id, images, prompt, selected_idx)

            # 7) 发送
            img_url = selected_images[0].get("url")
            if not img_url:
                await self.send_text("图片地址为空喵…重试一下？")
                return False, "图片 URL 为空"

            if self.chat_stream:
                await send_api.custom_to_stream("imageurl", img_url, self.chat_stream.stream_id)

            creation_prompt = selected_images[0].get("creation_prompt", "")
            logger.info(f"AI绘图 Action 成功: {creation_prompt[:50]}...")
            return True, f"成功生成图片 (描述: {prompt})"

        except Exception as e:
            logger.error(f"AI绘图 Action 出错: {e}", exc_info=True)
            await self.send_text(f"AI绘图出错了喵: {e}")
            return False, f"AI绘图出错: {e}"

    def _extract_prompt(self, msg: str) -> str:
        """从消息中提取绘画描述词。

        例：「调用绘图工具给我画一个猫娘」→「猫娘」；「画个jk」→「jk」；
            「帮我画一张星空」→「星空」；直接发「猫娘」→「猫娘」。
        """
        bot_name = global_config.bot.nickname or ""
        s = msg.replace(f"@{bot_name}", "").strip()

        # 1) 去掉「调用/使用 …… 工具/功能/插件」这类元指令短语（避免"绘图工具"干扰后续匹配）
        s = re.sub(
            r"(调用|使用|用一下|用)\s*(ai)?\s*(绘图|画图|绘画|生图|文生图)?\s*(工具|功能|插件)",
            "", s, flags=re.IGNORECASE,
        ).strip()

        # 2) 取「画/生成/绘制/来」等动词之后的内容（描述词通常跟在动词后面）
        m = re.search(
            r"(?:帮我|给我|请|帮忙)?\s*(?:画一?[张幅个]?|生成一?[张幅个]?|绘制|绘出|来一?[张幅个])\s*(.+)$",
            s,
        )
        if m:
            s = m.group(1).strip()

        # 3) 去掉开头残留的量词（一个/一张/一幅/个/张/幅/只）
        s = re.sub(r"^(?:一?[个张幅只])+\s*", "", s).strip()

        # 4) 去掉结尾的语气词/标点
        s = re.sub(r"[的吧呗啦呀吗呢嘛~，。！？!?\s]+$", "", s).strip()

        return s

    async def _expand_prompt(self, raw_prompt: str) -> str:
        """扩写 prompt (与 AIDrawCommand 共用逻辑)"""
        word_count = len(raw_prompt.split())
        if word_count >= 15:
            return raw_prompt
        try:
            llm = LLMRequest(
                model_set=model_config.model_task_config.utils_small,
                request_type="ai_draw.prompt_expand",
            )
            expand_prompt_text = _build_expand_prompt(raw_prompt)
            result, _ = await llm.generate_response_async(
                prompt=expand_prompt_text, temperature=0.7, max_tokens=200,
            )
            if result and result.strip():
                expanded = result.strip()
                if len(expanded) > 400:
                    expanded = expanded[:400]
                # 主体强制前置：扩写只产出补充细节，把用户原始主体拼在最前，确保主体绝不丢失/被替换
                final_prompt = f"{raw_prompt}，{expanded}"
                logger.info(f"prompt 扩写: {raw_prompt!r} → {final_prompt!r}")
                return final_prompt
            return raw_prompt
        except Exception as e:
            logger.warning(f"prompt 扩写失败: {e}")
            return raw_prompt


class AIDrawCommand(BaseCommand):
    """AI绘图 Command - 手动AI绘图命令"""

    command_name = "ai_draw_command"
    command_description = "根据描述词生成AI图片"

    # 命令匹配模式：/draw <prompt> 或 /绘图 <prompt>
    command_pattern = r"^/(draw|绘图|画图)(?:\s+(?P<prompt>.+))?$"
    command_help = "根据描述词生成AI图片。用法：/draw <描述词> 或 /绘图 <描述词>"
    command_examples = [
        "/draw jk",
        "/draw 可爱的猫咪",
        "/绘图 美丽的风景",
        "/画图 动漫少女"
    ]
    intercept_message = True

    async def _expand_prompt(self, raw_prompt: str) -> str:
        """用 LLM 将用户简短描述扩写成高质量生图提示词（fail-open）。"""
        word_count = len(raw_prompt.split())
        if word_count >= 15:
            logger.debug(f"prompt 已有 {word_count} 个词（≥15），跳过扩写")
            return raw_prompt

        try:
            llm = LLMRequest(
                model_set=model_config.model_task_config.utils_small,
                request_type="ai_draw.prompt_expand",
            )
            expand_prompt_text = _build_expand_prompt(raw_prompt)
            result, _ = await llm.generate_response_async(
                prompt=expand_prompt_text,
                temperature=0.7,
                max_tokens=200,
            )

            if result and result.strip():
                expanded = result.strip()
                if len(expanded) > 400:
                    logger.warning(f"扩写结果异常长 ({len(expanded)} 字符)，截断至 400")
                    expanded = expanded[:400]
                # 主体强制前置：扩写只产出补充细节，把用户原始主体拼在最前，确保主体绝不丢失/被替换
                final_prompt = f"{raw_prompt}，{expanded}"
                logger.info(f"prompt 扩写: {raw_prompt!r} → {final_prompt!r}")
                return final_prompt

            logger.warning("prompt 扩写返回空结果，使用原始 prompt")
            return raw_prompt

        except Exception as e:
            logger.warning(f"prompt 扩写失败 (fail-open, 已跳过): {e}")
            return raw_prompt

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行AI绘图命令"""
        try:
            # 从配置获取设置（ModelScope 文生图）
            api_key = self.get_config("ai_draw.api_key", "")
            image_model = self.get_config("ai_draw.image_model", "Tongyi-MAI/Z-Image-Turbo")
            nsfw_model = self.get_config("ai_draw.image_model_nsfw", "")
            anime_model = self.get_config("ai_draw.image_model_anime", "")
            poll_interval = float(self.get_config("ai_draw.poll_interval", 1.0))
            default_prompt = self.get_config(
                "ai_draw.default_prompt",
                "jk"
            )
            timeout = self.get_config("ai_draw.timeout", 60)
            selection_mode = self.get_config("ai_draw.selection_mode", "best")

            # 解析命令参数（使用 matched_groups 获取正则匹配结果）
            prompt = self.matched_groups.get("prompt")

            if not prompt or not prompt.strip():
                # 如果没有提供描述词,使用默认值
                prompt = default_prompt
                logger.info(f"未提供描述词,使用默认值: {prompt}")
            else:
                prompt = prompt.strip()
                logger.info(f"用户指定描述词: {prompt}")

            # prompt 扩写：简短描述 → LLM 扩写成高质量生图提示词
            enable_expand = self.get_config("ai_draw.prompt_expand_enabled", True)
            if enable_expand:
                prompt = await self._expand_prompt(prompt)

            # 未成年红线：命中即拒绝
            if is_minor_blocked(prompt):
                await self.send_text("这种不行哦，君君只画成年角色喵，换个描述吧~")
                return False, "命中未成年红线，拒绝生成", True

            # 路由模型：软色情→微调，二次元→特化，其余→默认
            use_model = route_image_model(prompt, image_model, nsfw_model, anime_model)
            logger.info(f"执行AI绘图命令,描述词: {prompt}, 模型: {use_model}, 选择模式: {selection_mode}")

            images = await generate_modelscope_images(
                prompt, api_key, use_model, int(timeout) if timeout else 60, poll_interval
            )
            logger.info(f"ModelScope 返回 {len(images)} 张图片")

            # 根据配置选择图片
            selected_images, selected_idx = select_best_image(prompt, images, selection_mode)

            # 缓存所有图片（用于"下一张"功能）
            chat_id = self.message.chat_stream.stream_id if self.message and self.message.chat_stream else None
            if chat_id:
                await cache_images(chat_id, images, prompt, selected_idx)
                logger.debug(f"已缓存 {len(images)} 张图片，可用于换风格")

            sent = 0
            for idx, img_data in enumerate(selected_images):
                img_url = img_data.get("url")
                if img_url:
                    await self.send_custom("imageurl", img_url)
                    sent += 1
                    creation_prompt = img_data.get("creation_prompt", "")
                    logger.info(
                        f"发送AI绘图 [{idx+1}/{len(selected_images)}] "
                        f"创作提示: {creation_prompt[:50]}..."
                    )

            if not sent:
                raise RuntimeError("解析到图片记录但缺少有效 url 字段")

            return True, f"成功生成并发送 {sent} 张AI图片 (描述词: {prompt})", True

        except Exception as e:
            logger.error(f"AI绘图命令执行出错: {e}")
            await self.send_text(f"❌ AI绘图出错: {e}")
            return False, f"AI绘图出错: {e}", True
