"""API 相关异常"""
from typing import Optional, Dict, Any
from .base_exceptions import MaiBotException


class APIException(MaiBotException):
    """API 异常基类"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        recoverable: bool = False,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            retry_after=retry_after,
            details=details,
        )


class APIAuthError(APIException):
    """API 认证错误

    当 API 密钥无效或认证失败时抛出。
    """

    def __init__(
        self,
        message: str = "API 认证失败",
        api_provider: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if api_provider:
            details["api_provider"] = api_provider

        super().__init__(
            message=message,
            error_code="API_AUTH_ERROR",
            recoverable=False,
            retry_after=None,
            details=details,
            **kwargs
        )


class APIRateLimitError(APIException):
    """API 速率限制错误

    当超过 API 调用速率限制时抛出。
    """

    def __init__(
        self,
        message: str = "API 调用速率超限",
        retry_after: Optional[int] = 60,
        limit: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if limit:
            details["limit"] = limit

        super().__init__(
            message=message,
            error_code="API_RATE_LIMIT_ERROR",
            recoverable=True,
            retry_after=retry_after,
            details=details,
            **kwargs
        )


class APIResponseError(APIException):
    """API 响应错误

    当 API 返回错误响应时抛出。
    """

    def __init__(
        self,
        message: str = "API 返回错误响应",
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        error_code: Optional[str] = None,
        recoverable: bool = False,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if status_code:
            details["status_code"] = status_code
        if response_body:
            details["response_body"] = response_body[:500]  # 限制长度

        super().__init__(
            message=message,
            error_code=error_code or "API_RESPONSE_ERROR",
            recoverable=recoverable,
            retry_after=retry_after,
            details=details,
            **kwargs
        )


class APIParseError(APIException):
    """API 响应解析错误

    当无法解析 API 响应时抛出。
    """

    def __init__(
        self,
        message: str = "无法解析 API 响应",
        response_text: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if response_text:
            details["response_text"] = response_text[:500]  # 限制长度

        super().__init__(
            message=message,
            error_code="API_PARSE_ERROR",
            recoverable=False,
            retry_after=None,
            details=details,
            **kwargs
        )


class APIQuotaExceededError(APIException):
    """API 配额超限错误

    当超过 API 配额限制时抛出。
    """

    def __init__(
        self,
        message: str = "API 配额已用尽",
        quota_type: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if quota_type:
            details["quota_type"] = quota_type

        super().__init__(
            message=message,
            error_code="API_QUOTA_EXCEEDED_ERROR",
            recoverable=False,
            retry_after=None,
            details=details,
            **kwargs
        )
