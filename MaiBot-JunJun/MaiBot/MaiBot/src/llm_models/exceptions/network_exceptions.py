"""网络相关异常"""
from typing import Optional, Dict, Any
from .base_exceptions import MaiBotException


class NetworkException(MaiBotException):
    """网络异常基类"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        recoverable: bool = True,
        retry_after: Optional[int] = 5,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            retry_after=retry_after,
            details=details,
        )


class NetworkConnectionError(NetworkException):
    """网络连接错误

    当无法建立网络连接时抛出。
    """

    def __init__(
        self,
        message: str = "无法连接到服务器",
        host: Optional[str] = None,
        port: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if host:
            details["host"] = host
        if port:
            details["port"] = port

        super().__init__(
            message=message,
            error_code="NETWORK_CONNECTION_ERROR",
            recoverable=True,
            retry_after=10,
            details=details,
            **kwargs
        )


class NetworkTimeoutError(NetworkException):
    """网络超时错误

    当网络请求超时时抛出。
    """

    def __init__(
        self,
        message: str = "网络请求超时",
        timeout: Optional[float] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if timeout:
            details["timeout"] = timeout

        super().__init__(
            message=message,
            error_code="NETWORK_TIMEOUT_ERROR",
            recoverable=True,
            retry_after=5,
            details=details,
            **kwargs
        )


class NetworkSSLError(NetworkException):
    """SSL/TLS 错误

    当 SSL/TLS 验证失败时抛出。
    """

    def __init__(
        self,
        message: str = "SSL/TLS 验证失败",
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code="NETWORK_SSL_ERROR",
            recoverable=False,
            retry_after=None,
            **kwargs
        )
