"""豆包 Seed-TTS 2.0 WebSocket 双向流式合成客户端。

协议: wss://openspeech.bytedance.com/api/v3/tts/bidirection
自行实现协议帧,不依赖官方 protocols 包,减少外部文件依赖。

消息帧格式 (服务端->客户端):
  - FullServerResponse: JSON 文本,含 event/payload
  - AudioOnlyServer: 二进制,前 4 字节为事件类型(大端),其余为音频 payload
客户端->服务端: JSON 文本,含 event/session_id/req_params

用法:
    audio_bytes = await doubao_tts_synthesize(
        text="你好",
        api_key=os.environ["DOUBAO_TTS_API_KEY"],
        speaker="zh_female_jiaochuannv_uranus_bigtts",
    )
"""
import asyncio
import json
import os
import struct
import uuid
from typing import Optional

import websockets

from src.common.logger import get_logger

logger = get_logger("doubao_tts")

URL = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"

# 事件类型常量
EVT_START_CONNECTION = "StartConnection"
EVT_START_SESSION = "StartSession"
EVT_TASK_REQUEST = "TaskRequest"
EVT_FINISH_SESSION = "FinishSession"
EVT_FINISH_CONNECTION = "FinishConnection"

# 服务端响应事件
EVT_CONNECTION_STARTED = "ConnectionStarted"
EVT_SESSION_STARTED = "SessionStarted"
EVT_SESSION_FINISHED = "SessionFinished"
EVT_CONNECTION_FINISHED = "ConnectionFinished"
EVT_TTS_RESPONSE = "TTSResponse"

# 服务端消息类型标识 (二进制帧前 4 字节)
# 0x4 前缀表示 FullServerResponse (JSON), 0x3 表示 AudioOnlyServer (二进制)
MSG_FULL_SERVER = 0x1
MSG_AUDIO_ONLY = 0x2


def _make_request(event: str, session_id: Optional[str] = None, req_params: Optional[dict] = None) -> bytes:
    """构造客户端请求 JSON 帧。"""
    payload: dict = {"event": event}
    if session_id:
        payload["session_id"] = session_id
    if req_params is not None:
        payload["req_params"] = req_params
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


async def _send_json(ws, event: str, session_id: Optional[str] = None, req_params: Optional[dict] = None) -> None:
    await ws.send(_make_request(event, session_id, req_params))


async def _recv_event(ws) -> tuple:
    """接收一帧,返回 (msg_type, event_name_or_none, payload_bytes_or_json)。"""
    msg = await ws.recv()
    if isinstance(msg, (bytes, bytearray)):
        # 二进制帧: 前 4 字节大端 uint32 为消息类型, 后续为 payload
        if len(msg) < 4:
            return (MSG_AUDIO_ONLY, None, bytes(msg))
        msg_type = struct.unpack(">I", msg[:4])[0]
        body = bytes(msg[4:])
        # AudioOnlyServer (0x2) 的 payload 是原始音频字节, 事件类型固定 TTSResponse
        if msg_type == MSG_AUDIO_ONLY:
            return (MSG_AUDIO_ONLY, EVT_TTS_RESPONSE, body)
        # FullServerResponse (0x1) 的 body 是 JSON
        try:
            obj = json.loads(body.decode("utf-8"))
            event = obj.get("EventType") or obj.get("event")
            return (MSG_FULL_SERVER, event, obj)
        except Exception:
            return (MSG_FULL_SERVER, None, body)
    # 文本帧 (部分实现可能直接发 JSON 文本)
    try:
        obj = json.loads(msg)
        event = obj.get("EventType") or obj.get("event")
        return (MSG_FULL_SERVER, event, obj)
    except Exception:
        return (MSG_FULL_SERVER, None, None)


async def doubao_tts_synthesize(
    text: str,
    api_key: str,
    speaker: str,
    resource_id: str = "seed-tts-2.0",
    audio_format: str = "mp3",
    sample_rate: int = 24000,
    speech_rate: int = 0,
    loudness_rate: int = 0,
    model: Optional[str] = None,
    context_texts: Optional[list] = None,
    timeout: float = 30.0,
) -> bytes:
    """合成语音,返回音频字节。

    Args:
        text: 待合成文本。
        api_key: 豆包 API Key。
        speaker: 音色 ID。
        resource_id: 资源 ID, seed-tts-2.0 或 seed-icl-2.0。
        audio_format: mp3 / pcm / ogg_opus / wav (流式推荐 mp3)。
        sample_rate: 采样率。
        speech_rate: 语速 [-50, 100]。
        loudness_rate: 音量 [-50, 100]。
        model: 复刻音色时指定, 如 seed-tts-2.0-standard。
        context_texts: 语音指令(仅 2.0 音色支持)。
        timeout: 总超时秒数。

    Returns:
        音频字节流。
    """
    if not api_key:
        raise ValueError("doubao api_key 未配置")
    if not speaker:
        raise ValueError("doubao speaker 未配置")

    headers = {
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Connect-Id": str(uuid.uuid4()),
        "X-Control-Require-Usage-Tokens-Return": "*",
    }

    connect_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    base_req_params: dict = {
        "speaker": speaker,
        "audio_params": {
            "format": audio_format,
            "sample_rate": sample_rate,
            "speech_rate": speech_rate,
            "loudness_rate": loudness_rate,
        },
    }
    if model:
        base_req_params["model"] = model
    if context_texts:
        base_req_params["context_texts"] = context_texts

    async with websockets.connect(
        URL, additional_headers=headers, max_size=16 * 1024 * 1024
    ) as ws:
        # 1) 建连
        await _send_json(ws, EVT_START_CONNECTION)
        await _wait(ws, EVT_CONNECTION_STARTED)

        # 2) 建会话
        start_session_req = {"req_params": base_req_params, "event": EVT_START_SESSION}
        await ws.send(json.dumps(start_session_req, ensure_ascii=False).encode("utf-8"))
        # session_id 需随请求带上; 上面已用独立 _send_json 路径, 这里补充
        await _wait(ws, EVT_SESSION_STARTED)

        # 3) 发送文本 (按句切分, 降低单帧延迟; 兼容短文本整段发送)
        chunks = _split_text(text) or [text]

        async def send_chunks():
            try:
                for chunk in chunks:
                    req = {"event": EVT_TASK_REQUEST, "session_id": session_id, "req_params": {**base_req_params, "text": chunk}}
                    await ws.send(json.dumps(req, ensure_ascii=False).encode("utf-8"))
                    await asyncio.sleep(0.01)
            finally:
                await _send_json(ws, EVT_FINISH_SESSION, session_id=session_id)

        send_task = asyncio.create_task(send_chunks())

        # 4) 接收音频
        audio_data = bytearray()
        try:
            while True:
                msg_type, event, payload = await asyncio.wait_for(_recv_event(ws), timeout=timeout)
                if msg_type == MSG_AUDIO_ONLY and event == EVT_TTS_RESPONSE:
                    audio_data.extend(payload)
                elif msg_type == MSG_FULL_SERVER:
                    if event == EVT_SESSION_FINISHED:
                        break
                    if event in ("SessionFailed", "ConnectionFailed"):
                        raise RuntimeError(f"豆包 TTS 失败: {payload}")
        except asyncio.TimeoutError:
            raise RuntimeError("豆包 TTS 接收超时")

        await send_task

        # 5) 结束连接
        await _send_json(ws, EVT_FINISH_CONNECTION)
        try:
            await asyncio.wait_for(_wait(ws, EVT_CONNECTION_FINISHED), timeout=5)
        except (asyncio.TimeoutError, Exception):
            pass

    if not audio_data:
        raise RuntimeError("豆包 TTS 未返回音频数据")
    return bytes(audio_data)


async def _wait(ws, expected_event: str) -> Optional[dict]:
    """循环接收直到拿到期望事件。"""
    while True:
        msg_type, event, payload = await _recv_event(ws)
        if msg_type == MSG_FULL_SERVER and event == expected_event:
            return payload if isinstance(payload, dict) else None
        if msg_type == MSG_FULL_SERVER and event in ("SessionFailed", "ConnectionFailed"):
            raise RuntimeError(f"豆包 TTS 失败: {payload}")


def _split_text(text: str, max_len: int = 60) -> list:
    """按标点切分文本,单段不超过 max_len。"""
    if not text:
        return []
    import re as _re
    parts = _re.split(r"([。！？!?；;\n]+)", text)
    chunks = []
    buf = ""
    for p in parts:
        buf += p
        if p and _re.search(r"[。！？!?；;\n]", p):
            if buf.strip():
                chunks.append(buf.strip())
            buf = ""
    if buf.strip():
        chunks.append(buf.strip())
    # 合并过短片段
    merged = []
    for c in chunks:
        if merged and len(merged[-1]) + len(c) <= max_len:
            merged[-1] += c
        else:
            merged.append(c)
    return merged