"""
日语 TTS 插件 - 基于豆包 Seed-TTS 2.0
支持 /ja_tts 命令和 /ys 音色切换命令
"""

import asyncio
import json
import os
import random
import re as _re
import uuid
from typing import Tuple, Dict, Any, List, Optional, Type

from src.common.logger import get_logger
from src.plugin_system.base.base_plugin import BasePlugin
from src.plugin_system.apis.plugin_register_api import register_plugin
from src.plugin_system.base.base_action import BaseAction, ActionActivationType
from src.plugin_system.base.base_command import BaseCommand
from src.plugin_system.base.base_tool import BaseTool
from src.plugin_system.base.component_types import ComponentInfo, ChatMode, ToolParamType
from src.plugin_system.base.config_types import ConfigField
from src.plugin_system.apis import send_api

logger = get_logger("ja_tts_plugin")


# ========== 假名/汉字 -> 罗马字 转换(fallback) ==========
# 日语音色(ja_*)直接接受假名原文,无需转换。
# 仅当用中文音色(zh_*)读日语时,才转罗马字作为 fallback。
_kks = None


def _get_kakasi():
    global _kks
    if _kks is None:
        import pykakasi
        _kks = pykakasi.kakasi()
    return _kks


def to_romaji(text: str) -> str:
    """将日文(假名/汉字)转为罗马字。纯拉丁字母原样保留。"""
    try:
        kks = _get_kakasi()
        return " ".join(p["hepburn"] for p in kks.convert(text))
    except Exception as e:
        logger.warning(f"[ja_tts] 转罗马字失败,原样返回: {e}")
        return text


# ========== 音色配置 ==========
VOICE_PRESETS = {
    # 日语音色(原生日语,直接接受假名/汉字,清浊音/音调正确)
    "ja": "ja_female_bv521_uranus_bigtts",
    # 中文音色(fallback,读日语需转罗马字)
    "jiaochuannv": "zh_female_jiaochuannv_uranus_bigtts",
    "shuangkuaisisi": "zh_female_shuangkuaisisi_uranus_bigtts",
    "wenwanshanshan": "saturn_zh_female_wenwanshanshan_cs_tob",
    "tiaopigongzhu": "saturn_zh_female_tiaopigongzhu_tob",
    "youyoujunzi": "zh_male_youyoujunzi_uranus_bigtts",
    "shaonianzixin": "zh_male_shaonianzixin_uranus_bigtts",
    "wennuanahu": "zh_male_wennuanahu_uranus_bigtts",
    "vv": "zh_female_vv_uranus_bigtts",
}

VOICE_CN_NAMES = {
    "ja": "日语女声",
    "jiaochuannv": "娇喘女",
    "shuangkuaisisi": "爽快丝丝",
    "wenwanshanshan": "温婉珊珊",
    "tiaopigongzhu": "调皮公主",
    "youyoujunzi": "悠悠君子",
    "shaonianzixin": "少年自信",
    "wennuanahu": "温暖阿虎",
    "vv": "甜妹VV",
}

# 日语默认音色(原生日语音色,音质最佳)
DEFAULT_VOICE = "ja"


# ========== 文本处理 ==========
def parse_voice_directions(text: str) -> Tuple[str, List[str]]:
    """解析括号内的语音方向指令"""
    pattern = _re.compile(r"（([^）]+)）")
    directions = pattern.findall(text)
    clean = pattern.sub("", text).strip()
    clean = _re.sub(r"\s+", "", clean)
    return clean, directions


async def ja_tts_synthesize(
    text: str,
    api_key: str,
    speaker: str,
    context_texts: Optional[List[str]] = None,
    timeout: float = 30.0,
) -> bytes:
    from .doubao_tts import doubao_tts_synthesize

    # 日语音色(ja_*)直接接受假名原文;中文音色(zh_*)需转罗马字
    is_ja_speaker = speaker.startswith("ja_")
    if is_ja_speaker:
        synth_text = text
        synth_ctx = context_texts
    else:
        synth_text = to_romaji(text)
        if synth_text and synth_text != text:
            logger.info(f"[ja_tts] 中文音色转罗马字: {text!r} -> {synth_text!r}")
        synth_ctx = [to_romaji(c) for c in context_texts] if context_texts else None

    return await doubao_tts_synthesize(
        text=synth_text,
        api_key=api_key,
        speaker=speaker,
        resource_id="seed-tts-2.0",
        audio_format="mp3",
        sample_rate=24000,
        speech_rate=0,
        loudness_rate=0,
        context_texts=synth_ctx,
        timeout=timeout,
    )


def get_api_key(get_config) -> str:
    return (get_config("doubao.api_key", "") or os.environ.get("DOUBAO_TTS_API_KEY", "")).strip()


def get_speaker(get_config, voice: str) -> str:
    v = voice.strip().lower() if voice else DEFAULT_VOICE
    return VOICE_PRESETS.get(v, VOICE_PRESETS[DEFAULT_VOICE])


# ========== Tool (chat_v2 / Function Calling) ==========
class JaTTSTool(BaseTool):
    name: str = "ja_tts"
    description: str = (
        "豆包 Seed-TTS 日语语音合成工具，将日语文本转为语音并通过QQ发送"
    )
    parameters: List[Tuple[str, ToolParamType, str, bool, None]] = [
        ("text", ToolParamType.STRING,
         "要合成语音的日语文本内容",
         True, None),
        ("voice", ToolParamType.STRING,
         "可选音色: jiaochuannv/shuangkuaisisi/wenwanshanshan/tiaopigongzhu/youyoujunzi/shaonianzixin/wennuanahu/vv",
         False, None),
    ]
    available_for_llm: bool = True

    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        text = (function_args.get("text") or "").strip()
        voice = (function_args.get("voice") or "").strip() or DEFAULT_VOICE
        if not text:
            return {"name": self.name, "content": "缺少 text 参数"}
        if not self.chat_stream:
            return {"name": self.name, "content": "无法获取聊天流"}

        api_key = get_api_key(self.get_config)
        if not api_key:
            return {"name": self.name, "content": "豆包 API Key 未配置"}

        speaker = get_speaker(self.get_config, voice)
        timeout = int(self.get_config("general.timeout", 60))

        pure_text, voice_dirs = parse_voice_directions(text)
        if voice_dirs:
            text = pure_text
            logger.info(f"[ja_tts_tool] 语音方向指令: {voice_dirs}")

        try:
            audio_data = await asyncio.wait_for(
                ja_tts_synthesize(text, api_key, speaker, voice_dirs or None, timeout),
                timeout=timeout + 10,
            )
        except asyncio.TimeoutError:
            return {"name": self.name, "content": "豆包 TTS 超时"}
        except Exception as e:
            logger.error(f"[ja_tts_tool] 错误: {e}")
            return {"name": self.name, "content": f"豆包 TTS 错误: {e}"}

        if len(audio_data) < 100:
            return {"name": self.name, "content": "豆包 TTS 未返回音频数据"}

        audio_path = os.path.abspath("tts_ja_output.mp3")
        with open(audio_path, "wb") as f:
            f.write(audio_data)
        await self.send_custom(message_type="voiceurl", content=audio_path)
        return {"name": self.name, "content": "日语语音已发送"}


# ========== Action (LLM 判断触发) ==========
class JaTTSAction(BaseAction):
    action_name = "ja_tts_action"
    action_description = "日语语音合成：当用户要求发日语语音、说日语时，将日语文本转为语音发送"
    activation_type = ActionActivationType.LLM_JUDGE
    parallel_action = False
    action_parameters = {
        "text": "要合成语音的日语文本",
        "voice": "可选音色名(vv/jiaochuannv/shuangkuaisisi等)",
    }
    action_require = [
        "当用户要求发送日语语音时使用",
        "当用户使用 /ja_tts 命令时使用",
        "当用户明确要求听日语语音时使用",
    ]

    async def execute(self) -> Tuple[bool, str]:
        text = (self.action_data.get("text") or "").strip()
        voice = (self.action_data.get("voice") or "").strip() or DEFAULT_VOICE

        if not text:
            return False, "缺少要合成的日语文本"

        api_key = get_api_key(self.get_config)
        if not api_key:
            return False, "豆包 API Key 未配置"

        speaker = get_speaker(self.get_config, voice)
        timeout = int(self.get_config("general.timeout", 60))

        pure_text, voice_dirs = parse_voice_directions(text)
        if voice_dirs:
            text = pure_text

        try:
            audio_data = await asyncio.wait_for(
                ja_tts_synthesize(text, api_key, speaker, voice_dirs or None, timeout),
                timeout=timeout + 10,
            )
        except asyncio.TimeoutError:
            return False, "豆包 TTS 超时"
        except Exception as e:
            logger.error(f"{self.log_prefix} 错误: {e}")
            return False, f"错误: {e}"

        if len(audio_data) < 100:
            return False, "豆包 TTS 未返回音频数据"

        audio_path = os.path.abspath("tts_ja_output.mp3")
        with open(audio_path, "wb") as f:
            f.write(audio_data)
        await self.send_custom(message_type="voiceurl", content=audio_path)
        return True, f"日语语音已发送 ({VOICE_CN_NAMES.get(voice, voice)})"


# ========== Command: /ys 切换音色 ==========
class YSVoiceCommand(BaseCommand):
    command_name = "ys"
    command_description = "切换 TTS 音色: /ys [音色名]，不带参数显示可选音色列表"
    command_pattern = r"^/ys(?:\s+(?P<voice>\S+))?$"
    mode_enable = ChatMode.ALL

    async def execute(self) -> Tuple[bool, str, bool]:
        voice = (self.matched_groups.get("voice") or "").strip().lower()
        if not voice:
            lines = ["可选音色:"]
            for k, cn in VOICE_CN_NAMES.items():
                marker = " [当前]" if get_speaker(self.get_config, "") == VOICE_PRESETS[k] else ""
                lines.append(f"  {k}({cn}){marker}")
            return True, "\n".join(lines), True

        if voice in VOICE_PRESETS:
            self.set_config("doubao.speaker", VOICE_PRESETS[voice])
            cn = VOICE_CN_NAMES.get(voice, voice)
            return True, f"已切换音色为: {cn} ({VOICE_PRESETS[voice]})", True

        keys = "/".join(VOICE_PRESETS.keys())
        return False, f"未知音色: {voice}，可选: {keys}", True


# ========== Command: /ja_tts 手动日语TTS ==========
class JaTTSManualCommand(BaseCommand):
    command_name = "ja_tts"
    command_description = "日语语音合成命令: /ja_tts <日语文本> [音色]"
    command_pattern = r"^/ja_tts\s+(?P<text>.+?)(?:\s+(?P<voice>\S+))?$"
    mode_enable = ChatMode.ALL

    async def execute(self) -> Tuple[bool, str, bool]:
        text = (self.matched_groups.get("text") or "").strip()
        voice = (self.matched_groups.get("voice") or "").strip() or DEFAULT_VOICE
        if not text:
            return False, "用法: /ja_tts <日语文本> [音色]", True

        api_key = get_api_key(self.get_config)
        if not api_key:
            return False, "API Key 未配置", True

        speaker = get_speaker(self.get_config, voice)
        timeout = int(self.get_config("general.timeout", 60))

        pure_text, voice_dirs = parse_voice_directions(text)
        if voice_dirs:
            text = pure_text

        try:
            audio_data = await asyncio.wait_for(
                ja_tts_synthesize(text, api_key, speaker, voice_dirs or None, timeout),
                timeout=timeout + 10,
            )
        except Exception as e:
            return False, f"错误: {e}", True

        if len(audio_data) < 100:
            return False, "返回音频数据为空", True

        audio_path = os.path.abspath("tts_ja_output.mp3")
        with open(audio_path, "wb") as f:
            f.write(audio_data)
        await self.send_custom(message_type="voiceurl", content=audio_path)
        return True, f"日语语音已发送 ({VOICE_CN_NAMES.get(voice, voice)})", True


# ========== 插件注册 ==========
class JaTTSPlugin(BasePlugin):
    """豆包日语 TTS 插件"""

    plugin_name = "ja_tts_plugin"
    plugin_version = "1.0.0"
    plugin_description = "豆包日语 TTS 插件（基于 Seed-TTS 2.0），支持日语语音合成与发送"
    enable_plugin = True
    config_file_name = "config.toml"
    dependencies = []
    python_dependencies = []

    components = [
        ComponentInfo(JaTTSAction, "action", "ja_tts_action", "日语 TTS Action"),
        ComponentInfo(JaTTSTool, "tool", "ja_tts", "日语 TTS Tool"),
        ComponentInfo(YSVoiceCommand, "command", "ys", "切换音色: /ys"),
        ComponentInfo(JaTTSManualCommand, "command", "ja_tts", "日语语音命令: /ja_tts"),
    ]

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件包含的组件列表"""
        return [
            (JaTTSAction.get_action_info(), JaTTSAction),
            (JaTTSTool.get_tool_info(), JaTTSTool),
            (YSVoiceCommand.get_command_info(), YSVoiceCommand),
            (JaTTSManualCommand.get_command_info(), JaTTSManualCommand),
        ]

    config_schema = {
        "plugin": {
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
            "config_version": ConfigField(type=str, default="1.0.0", description="配置版本"),
        },
        "general": {
            "timeout": ConfigField(type=int, default=60, description="语音合成超时秒数"),
            "max_text_length": ConfigField(type=int, default=500, description="文本最大长度"),
        },
        "doubao": {
            "api_key": ConfigField(type=str, default="", description="API Key（也可用环境变量 DOUBAO_TTS_API_KEY）"),
            "speaker": ConfigField(type=str, default="zh_female_vv_uranus_bigtts", description="默认音色"),
        },
        "probability": {
            "enabled": ConfigField(type=bool, default=True, description="启用概率触发"),
            "base_probability": ConfigField(type=float, default=1.0, description="基础触发概率"),
            "force_keywords": ConfigField(type=list, default=["发语音", "说日语"], description="强制触发关键词列表"),
        },
    }


register_plugin(JaTTSPlugin)