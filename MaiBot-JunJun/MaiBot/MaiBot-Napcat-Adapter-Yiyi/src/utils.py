import websockets as Server
import json
import base64
import uuid
import urllib3
import ssl
import io
import warnings

from src.database import BanUser, db_manager
from .logger import logger
from .response_pool import get_response

from PIL import Image
from typing import Union, List, Tuple, Optional

# 增加PIL图片大小限制，防止DecompressionBombWarning
# 设置为500MP（500,000,000像素），足够处理大部分图片
Image.MAX_IMAGE_PIXELS = 500000000

# 可选：禁用DecompressionBombWarning警告（如果图片已经过压缩处理）
warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)


class SSLAdapter(urllib3.PoolManager):
    def __init__(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers("DEFAULT@SECLEVEL=1")
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = context
        super().__init__(*args, **kwargs)


async def get_group_info(websocket: Server.ServerConnection, group_id: int) -> dict | None:
    """
    获取群相关信息

    返回值需要处理可能为空的情况
    """
    logger.debug("获取群聊信息中")
    request_uuid = str(uuid.uuid4())
    payload = json.dumps({"action": "get_group_info", "params": {"group_id": group_id}, "echo": request_uuid})
    try:
        await websocket.send(payload)
        socket_response: dict = await get_response(request_uuid)
    except TimeoutError:
        logger.error(f"获取群信息超时，群号: {group_id}")
        return None
    except Exception as e:
        logger.error(f"获取群信息失败: {e}")
        return None
    logger.debug(socket_response)
    return socket_response.get("data")


async def get_group_detail_info(websocket: Server.ServerConnection, group_id: int) -> dict | None:
    """
    获取群详细信息

    返回值需要处理可能为空的情况
    """
    logger.debug("获取群详细信息中")
    request_uuid = str(uuid.uuid4())
    payload = json.dumps({"action": "get_group_detail_info", "params": {"group_id": group_id}, "echo": request_uuid})
    try:
        await websocket.send(payload)
        socket_response: dict = await get_response(request_uuid)
    except TimeoutError:
        logger.error(f"获取群详细信息超时，群号: {group_id}")
        return None
    except Exception as e:
        logger.error(f"获取群详细信息失败: {e}")
        return None
    logger.debug(socket_response)
    return socket_response.get("data")


async def get_member_info(websocket: Server.ServerConnection, group_id: int, user_id: int) -> dict | None:
    """
    获取群成员信息

    返回值需要处理可能为空的情况
    """
    logger.debug("获取群成员信息中")
    request_uuid = str(uuid.uuid4())
    payload = json.dumps(
        {
            "action": "get_group_member_info",
            "params": {"group_id": group_id, "user_id": user_id, "no_cache": True},
            "echo": request_uuid,
        }
    )
    try:
        await websocket.send(payload)
        socket_response: dict = await get_response(request_uuid)
    except TimeoutError:
        logger.error(f"获取成员信息超时，群号: {group_id}, 用户ID: {user_id}")
        return None
    except Exception as e:
        logger.error(f"获取成员信息失败: {e}")
        return None
    logger.debug(socket_response)
    return socket_response.get("data")


def compress_image(image_bytes: bytes, max_size_mb: float = 5.0, max_dimension: int = 2000) -> bytes:
    """
    压缩图片，确保不超过指定大小和尺寸
    Parameters:
        image_bytes: 原始图片字节数据
        max_size_mb: 最大文件大小（MB），默认5MB
        max_dimension: 最大尺寸（宽或高），默认2000像素
    Returns:
        bytes: 压缩后的图片字节数据
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        original_format = image.format or "JPEG"
        
        # 检查并调整尺寸
        width, height = image.size
        if width > max_dimension or height > max_dimension:
            ratio = min(max_dimension / width, max_dimension / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            logger.debug(f"调整图片尺寸: {width}x{height} -> {new_width}x{new_height}")
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 转换为RGB模式（如果不是RGBA或RGB）
        if image.mode in ("RGBA", "LA", "P"):
            # 创建白色背景
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
        
        # 压缩图片，逐步降低质量直到满足大小要求
        max_size_bytes = int(max_size_mb * 1024 * 1024)
        output_buffer = io.BytesIO()
        quality = 95
        
        while quality >= 20:
            output_buffer.seek(0)
            output_buffer.truncate(0)
            image.save(output_buffer, format="JPEG", quality=quality, optimize=True)
            if len(output_buffer.getvalue()) <= max_size_bytes:
                break
            quality -= 10
        
        compressed_bytes = output_buffer.getvalue()
        logger.debug(f"图片压缩完成: 原始大小={len(image_bytes)/1024/1024:.2f}MB, 压缩后={len(compressed_bytes)/1024/1024:.2f}MB, 质量={quality}")
        return compressed_bytes
    except Exception as e:
        logger.warning(f"图片压缩失败，使用原始图片: {str(e)}")
        return image_bytes


async def get_image_base64(url: str, compress: bool = True) -> str:
    # sourcery skip: raise-specific-error
    """获取图片/表情包的Base64
    
    Args:
        url: 图片URL（可能是直接图片URL或返回JSON的API URL）
        compress: 是否压缩图片（默认True）
    """
    logger.debug(f"下载图片: {url}")
    http = SSLAdapter()
    try:
        response = http.request("GET", url, timeout=10)
        if response.status != 200:
            raise Exception(f"HTTP Error: {response.status}")
        
        response_data = response.data
        content_type = response.headers.get("Content-Type", "").lower()
        
        # 检查是否是JSON响应（API可能返回JSON格式的图片URL）
        if "application/json" in content_type or response_data.startswith(b"{") or response_data.startswith(b"["):
            try:
                json_data = json.loads(response_data.decode("utf-8"))
                logger.debug(f"API返回JSON格式: {json_data}")
                
                # 检查是否是错误响应
                if isinstance(json_data, dict):
                    # 检查错误码
                    if "code" in json_data and json_data.get("code") != 200:
                        error_msg = json_data.get("msg", json_data.get("message", "未知错误"))
                        raise Exception(f"API返回错误 (code={json_data.get('code')}): {error_msg}")
                
                # 尝试从JSON中提取图片URL
                image_url = None
                if isinstance(json_data, dict):
                    # 常见的JSON格式：{"code": 200, "data": {"url": "..."}}
                    if "data" in json_data:
                        data = json_data["data"]
                        if isinstance(data, dict) and "url" in data:
                            image_url = data["url"]
                        elif isinstance(data, str):
                            image_url = data
                    # 或者直接包含url字段
                    elif "url" in json_data:
                        image_url = json_data["url"]
                    # 或者包含pic字段
                    elif "pic" in json_data:
                        image_url = json_data["pic"]
                elif isinstance(json_data, str):
                    image_url = json_data
                
                if image_url:
                    logger.info(f"从JSON中提取图片URL: {image_url}")
                    # 递归调用，下载实际的图片
                    return await get_image_base64(image_url, compress)
                else:
                    raise Exception(f"无法从JSON响应中提取图片URL: {json_data}")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"响应不是有效的JSON，尝试作为图片处理: {str(e)}")
                # 如果不是JSON，继续作为图片处理
        
        # 验证是否是有效的图片
        try:
            # 尝试打开图片以验证格式（不调用verify，因为会消耗数据）
            test_image = Image.open(io.BytesIO(response_data))
            image_format = test_image.format
            logger.debug(f"验证图片格式成功: {image_format}")
            if not image_format:
                raise Exception("无法识别图片格式")
        except Exception as img_error:
            logger.error(f"响应不是有效的图片格式: {str(img_error)}")
            logger.error(f"响应内容前100字节: {response_data[:100]}")
            raise Exception(f"URL返回的不是有效图片: {str(img_error)}")
        
        image_bytes = response_data
        
        # 如果启用压缩，压缩图片
        if compress:
            image_bytes = compress_image(image_bytes)
        
        return base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:
        logger.error(f"图片下载失败: {str(e)}")
        raise


def convert_image_to_gif(image_base64: str) -> str:
    # sourcery skip: extract-method
    """
    将Base64编码的图片转换为GIF格式
    Parameters:
        image_base64: str: Base64编码的图片数据
    Returns:
        str: Base64编码的GIF图片数据
    """
    logger.debug("转换图片为GIF格式")
    try:
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes))
        output_buffer = io.BytesIO()
        image.save(output_buffer, format="GIF")
        output_buffer.seek(0)
        return base64.b64encode(output_buffer.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"图片转换为GIF失败: {str(e)}")
        return image_base64


async def get_self_info(websocket: Server.ServerConnection) -> dict | None:
    """
    获取自身信息
    Parameters:
        websocket: WebSocket连接对象
    Returns:
        data: dict: 返回的自身信息
    """
    logger.debug("获取自身信息中")
    request_uuid = str(uuid.uuid4())
    payload = json.dumps({"action": "get_login_info", "params": {}, "echo": request_uuid})
    try:
        await websocket.send(payload)
        response: dict = await get_response(request_uuid)
    except TimeoutError:
        logger.error("获取自身信息超时")
        return None
    except Exception as e:
        logger.error(f"获取自身信息失败: {e}")
        return None
    logger.debug(response)
    return response.get("data")


def get_image_format(raw_data: str) -> str:
    """
    从Base64编码的数据中确定图片的格式。
    Parameters:
        raw_data: str: Base64编码的图片数据。
    Returns:
        format: str: 图片的格式（例如 'jpeg', 'png', 'gif'）。
    """
    image_bytes = base64.b64decode(raw_data)
    return Image.open(io.BytesIO(image_bytes)).format.lower()


async def get_stranger_info(websocket: Server.ServerConnection, user_id: int) -> dict | None:
    """
    获取陌生人信息
    Parameters:
        websocket: WebSocket连接对象
        user_id: 用户ID
    Returns:
        dict: 返回的陌生人信息
    """
    logger.debug("获取陌生人信息中")
    request_uuid = str(uuid.uuid4())
    payload = json.dumps({"action": "get_stranger_info", "params": {"user_id": user_id}, "echo": request_uuid})
    try:
        await websocket.send(payload)
        response: dict = await get_response(request_uuid)
    except TimeoutError:
        logger.error(f"获取陌生人信息超时，用户ID: {user_id}")
        return None
    except Exception as e:
        logger.error(f"获取陌生人信息失败: {e}")
        return None
    logger.debug(response)
    return response.get("data")


async def get_message_detail(websocket: Server.ServerConnection, message_id: Union[str, int]) -> dict | None:
    """
    获取消息详情，可能为空
    Parameters:
        websocket: WebSocket连接对象
        message_id: 消息ID
    Returns:
        dict: 返回的消息详情
    """
    logger.debug("获取消息详情中")
    request_uuid = str(uuid.uuid4())
    payload = json.dumps({"action": "get_msg", "params": {"message_id": message_id}, "echo": request_uuid})
    try:
        await websocket.send(payload)
        response: dict = await get_response(request_uuid, 30)  # 增加超时时间到30秒
    except TimeoutError:
        logger.error(f"获取消息详情超时，消息ID: {message_id}")
        return None
    except Exception as e:
        logger.error(f"获取消息详情失败: {e}")
        return None
    logger.debug(response)
    return response.get("data")


async def get_record_detail(
    websocket: Server.ServerConnection, file: str, file_id: Optional[str] = None
) -> dict | None:
    """
    获取语音消息内容
    Parameters:
        websocket: WebSocket连接对象
        file: 文件名
        file_id: 文件ID
    Returns:
        dict: 返回的语音消息详情
    """
    logger.debug("获取语音消息详情中")
    request_uuid = str(uuid.uuid4())
    payload = json.dumps(
        {
            "action": "get_record",
            "params": {"file": file, "file_id": file_id, "out_format": "wav"},
            "echo": request_uuid,
        }
    )
    try:
        await websocket.send(payload)
        response: dict = await get_response(request_uuid, 30)  # 增加超时时间到30秒
    except TimeoutError:
        logger.error(f"获取语音消息详情超时，文件: {file}, 文件ID: {file_id}")
        return None
    except Exception as e:
        logger.error(f"获取语音消息详情失败: {e}")
        return None
    logger.debug(f"{str(response)[:200]}...")  # 防止语音的超长base64编码导致日志过长
    return response.get("data")


async def read_ban_list(
    websocket: Server.ServerConnection,
) -> Tuple[List[BanUser], List[BanUser]]:
    """
    从根目录下的data文件夹中的文件读取禁言列表。
    同时自动更新已经失效禁言
    Returns:
        Tuple[
            一个仍在禁言中的用户的BanUser列表,
            一个已经自然解除禁言的用户的BanUser列表,
            一个仍在全体禁言中的群的BanUser列表,
            一个已经自然解除全体禁言的群的BanUser列表,
        ]
    """
    try:
        ban_list = db_manager.get_ban_records()
        lifted_list: List[BanUser] = []
        logger.info("已经读取禁言列表")
        for ban_record in ban_list:
            if ban_record.user_id == 0:
                fetched_group_info = await get_group_info(websocket, ban_record.group_id)
                if fetched_group_info is None:
                    logger.warning(f"无法获取群信息，群号: {ban_record.group_id}，默认禁言解除")
                    lifted_list.append(ban_record)
                    ban_list.remove(ban_record)
                    continue
                group_all_shut: int = fetched_group_info.get("group_all_shut")
                if group_all_shut == 0:
                    lifted_list.append(ban_record)
                    ban_list.remove(ban_record)
                    continue
            else:
                fetched_member_info = await get_member_info(websocket, ban_record.group_id, ban_record.user_id)
                if fetched_member_info is None:
                    logger.warning(
                        f"无法获取群成员信息，用户ID: {ban_record.user_id}, 群号: {ban_record.group_id}，默认禁言解除"
                    )
                    lifted_list.append(ban_record)
                    ban_list.remove(ban_record)
                    continue
                lift_ban_time: int = fetched_member_info.get("shut_up_timestamp")
                if lift_ban_time == 0:
                    lifted_list.append(ban_record)
                    ban_list.remove(ban_record)
                else:
                    ban_record.lift_time = lift_ban_time
        db_manager.update_ban_record(ban_list)
        return ban_list, lifted_list
    except Exception as e:
        logger.error(f"读取禁言列表失败: {e}")
        return [], []


def save_ban_record(list: List[BanUser]):
    return db_manager.update_ban_record(list)
