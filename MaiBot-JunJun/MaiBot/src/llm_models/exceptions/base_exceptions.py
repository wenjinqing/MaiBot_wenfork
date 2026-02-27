"""MaiBot 异常基类"""
from typing import Optional, Dict, Any


class MaiBotException(Exception):
    """MaiBot 异常基类

    所有 MaiBot 自定义异常的基类，提供统一的错误处理接口。
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        recoverable: bool = False,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """初始化异常

        Args:
            message: 错误消息
            error_code: 错误代码（用于分类和识别）
            recoverable: 是否可恢复（是否应该重试）
            retry_after: 建议重试时间（秒）
            details: 额外的错误详情
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.recoverable = recoverable
        self.retry_after = retry_after
        self.details = details or {}

    def __str__(self):
        parts = [f"[{self.error_code}] {self.message}"]
        if self.retry_after:
            parts.append(f"(建议 {self.retry_after}秒后重试)")
        if self.details:
            parts.append(f"详情: {self.details}")
        return " ".join(parts)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"recoverable={self.recoverable}, "
            f"retry_after={self.retry_after})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "recoverable": self.recoverable,
            "retry_after": self.retry_after,
            "details": self.details,
        }
