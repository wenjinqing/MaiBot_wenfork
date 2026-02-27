"""MaiBot 异常模块

提供层次化的异常体系，用于更精确的错误处理。

异常层次结构：
    MaiBotException (基类)
    ├── NetworkException
    │   ├── NetworkConnectionError
    │   ├── NetworkTimeoutError
    │   └── NetworkSSLError
    ├── APIException
    │   ├── APIAuthError
    │   ├── APIRateLimitError
    │   ├── APIResponseError
    │   ├── APIParseError
    │   └── APIQuotaExceededError
    └── ModelException
        ├── ModelNotAvailableError
        ├── ModelAttemptFailed
        ├── ModelContextExceededError
        ├── ModelOutputError
        └── ModelConfigError

使用示例：
    from src.llm_models.exceptions import (
        APIAuthError,
        NetworkTimeoutError,
        ModelContextExceededError
    )

    try:
        # 调用 API
        response = await api_call()
    except APIAuthError as e:
        logger.error(f"认证失败: {e.message}")
        # 不重试
    except NetworkTimeoutError as e:
        logger.warning(f"网络超时: {e.message}")
        if e.recoverable and e.retry_after:
            await asyncio.sleep(e.retry_after)
            # 重试
    except ModelContextExceededError as e:
        logger.error(f"上下文超限: {e.details}")
        # 截断输入后重试
"""

# 基础异常
from .base_exceptions import MaiBotException

# 网络异常
from .network_exceptions import (
    NetworkException,
    NetworkConnectionError,
    NetworkTimeoutError,
    NetworkSSLError,
)

# API 异常
from .api_exceptions import (
    APIException,
    APIAuthError,
    APIRateLimitError,
    APIResponseError,
    APIParseError,
    APIQuotaExceededError,
)

# 模型异常
from .model_exceptions import (
    ModelException,
    ModelNotAvailableError,
    ModelAttemptFailed,
    ModelContextExceededError,
    ModelOutputError,
    ModelConfigError,
)

# 向后兼容：为旧代码提供包装类
class RespNotOkException(APIResponseError):
    """响应异常（向后兼容）"""
    def __init__(self, status_code: int, message: str = None):
        self.status_code = status_code
        super().__init__(
            message=message or f"HTTP {status_code}",
            status_code=status_code,
            recoverable=status_code in [429, 500, 503],
            retry_after=60 if status_code == 429 else None,
            error_code=f"HTTP_{status_code}"
        )

class RespParseException(APIParseError):
    """响应解析异常（向后兼容）"""
    def __init__(self, ext_info, message: str = None):
        self.ext_info = ext_info
        super().__init__(
            message=message or "响应解析失败",
            error_code="PARSE_ERROR",
            recoverable=False,
            details={"ext_info": ext_info}
        )

class ReqAbortException(NetworkException):
    """请求中止异常（向后兼容）"""
    def __init__(self, message: str = None):
        super().__init__(
            message=message or "请求因未知原因异常终止",
            error_code="REQUEST_ABORTED",
            recoverable=True,
            retry_after=5
        )

class EmptyResponseException(APIResponseError):
    """空响应异常（向后兼容）"""
    def __init__(self, message: str = "响应内容为空，这可能是一个临时性问题"):
        super().__init__(
            message=message,
            error_code="EMPTY_RESPONSE",
            recoverable=True,
            retry_after=5
        )

__all__ = [
    # 基础异常
    "MaiBotException",
    # 网络异常
    "NetworkException",
    "NetworkConnectionError",
    "NetworkTimeoutError",
    "NetworkSSLError",
    # API 异常
    "APIException",
    "APIAuthError",
    "APIRateLimitError",
    "APIResponseError",
    "APIParseError",
    "APIQuotaExceededError",
    # 模型异常
    "ModelException",
    "ModelNotAvailableError",
    "ModelAttemptFailed",
    "ModelContextExceededError",
    "ModelOutputError",
    "ModelConfigError",
    # 向后兼容别名
    "RespParseException",
    "RespNotOkException",
    "ReqAbortException",
    "EmptyResponseException",
]
