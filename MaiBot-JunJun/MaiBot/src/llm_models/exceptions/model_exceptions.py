"""模型相关异常"""
from typing import Optional, Dict, Any
from .base_exceptions import MaiBotException


class ModelException(MaiBotException):
    """模型异常基类"""

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


class ModelNotAvailableError(ModelException):
    """模型不可用错误

    当请求的模型不可用时抛出。
    """

    def __init__(
        self,
        message: str = "模型不可用",
        model_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if model_name:
            details["model_name"] = model_name

        super().__init__(
            message=message,
            error_code="MODEL_NOT_AVAILABLE_ERROR",
            recoverable=False,
            retry_after=None,
            details=details,
            **kwargs
        )


class ModelAttemptFailed(ModelException):
    """模型调用失败

    当模型调用失败时抛出（可重试）。
    """

    def __init__(
        self,
        message: str = "模型调用失败",
        model_name: Optional[str] = None,
        attempt: Optional[int] = None,
        max_attempts: Optional[int] = None,
        original_exception: Optional[Exception] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if model_name:
            details["model_name"] = model_name
        if attempt:
            details["attempt"] = attempt
        if max_attempts:
            details["max_attempts"] = max_attempts

        # 保存原始异常
        self.original_exception = original_exception

        super().__init__(
            message=message,
            error_code="MODEL_ATTEMPT_FAILED",
            recoverable=True,
            retry_after=5,
            details=details,
            **kwargs
        )


class ModelContextExceededError(ModelException):
    """模型上下文长度超限错误

    当输入超过模型的最大上下文长度时抛出。
    """

    def __init__(
        self,
        message: str = "输入超过模型最大上下文长度",
        model_name: Optional[str] = None,
        token_count: Optional[int] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if model_name:
            details["model_name"] = model_name
        if token_count:
            details["token_count"] = token_count
        if max_tokens:
            details["max_tokens"] = max_tokens

        super().__init__(
            message=message,
            error_code="MODEL_CONTEXT_EXCEEDED_ERROR",
            recoverable=False,
            retry_after=None,
            details=details,
            **kwargs
        )


class ModelOutputError(ModelException):
    """模型输出错误

    当模型输出格式不符合预期时抛出。
    """

    def __init__(
        self,
        message: str = "模型输出格式错误",
        expected_format: Optional[str] = None,
        actual_output: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if expected_format:
            details["expected_format"] = expected_format
        if actual_output:
            details["actual_output"] = actual_output[:500]  # 限制长度

        super().__init__(
            message=message,
            error_code="MODEL_OUTPUT_ERROR",
            recoverable=False,
            retry_after=None,
            details=details,
            **kwargs
        )


class ModelConfigError(ModelException):
    """模型配置错误

    当模型配置无效时抛出。
    """

    def __init__(
        self,
        message: str = "模型配置错误",
        config_key: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if config_key:
            details["config_key"] = config_key

        super().__init__(
            message=message,
            error_code="MODEL_CONFIG_ERROR",
            recoverable=False,
            retry_after=None,
            details=details,
            **kwargs
        )
