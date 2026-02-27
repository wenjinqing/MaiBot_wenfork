"""插件系统工具函数"""
from typing import Optional
import re
from src.common.logger import get_logger

logger = get_logger("webui.plugin_utils")


def get_token_from_cookie_or_header(
    maibot_session: Optional[str] = None,
    authorization: Optional[str] = None,
) -> Optional[str]:
    """从 Cookie 或 Header 获取 token"""
    # 优先从 Cookie 获取
    if maibot_session:
        return maibot_session
    # 其次从 Header 获取
    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "")
    return None


def parse_version(version_str: str) -> tuple[int, int, int]:
    """
    解析版本号字符串

    支持格式:
    - 0.11.2 -> (0, 11, 2)
    - 0.11.2.snapshot.2 -> (0, 11, 2)

    Returns:
        (major, minor, patch) 三元组
    """
    # 移除 snapshot、dev、alpha、beta 等后缀（支持 - 和 . 分隔符）
    # 匹配 -snapshot.X, .snapshot, -dev, .dev, -alpha, .alpha, -beta, .beta 等后缀
    base_version = re.split(r"[-.](?:snapshot|dev|alpha|beta|rc)", version_str, flags=re.IGNORECASE)[0]

    parts = base_version.split(".")
    if len(parts) < 3:
        # 补齐到 3 位
        parts.extend(["0"] * (3 - len(parts)))

    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2])
        return (major, minor, patch)
    except (ValueError, IndexError):
        logger.warning(f"无法解析版本号: {version_str}，返回默认值 (0, 0, 0)")
        return (0, 0, 0)
