"""
错误处理工具
"""

from enum import Enum
from typing import Optional, Dict, Any
from src.common.logger import get_logger

logger = get_logger("error_handler")


class ErrorType(Enum):
    """错误类型枚举"""
    # LLM 相关错误
    LLM_API_ERROR = "llm_api_error"  # LLM API 调用失败
    LLM_TIMEOUT = "llm_timeout"  # LLM 超时
    LLM_RATE_LIMIT = "llm_rate_limit"  # LLM 速率限制
    LLM_INVALID_RESPONSE = "llm_invalid_response"  # LLM 返回无效响应

    # 工具相关错误
    TOOL_NOT_FOUND = "tool_not_found"  # 工具不存在
    TOOL_EXECUTION_ERROR = "tool_execution_error"  # 工具执行失败
    TOOL_TIMEOUT = "tool_timeout"  # 工具超时
    TOOL_INVALID_PARAMS = "tool_invalid_params"  # 工具参数无效

    # 数据库相关错误
    DB_CONNECTION_ERROR = "db_connection_error"  # 数据库连接失败
    DB_QUERY_ERROR = "db_query_error"  # 数据库查询失败
    DB_TIMEOUT = "db_timeout"  # 数据库超时

    # 网络相关错误
    NETWORK_ERROR = "network_error"  # 网络错误
    NETWORK_TIMEOUT = "network_timeout"  # 网络超时

    # 消息相关错误
    MESSAGE_SEND_ERROR = "message_send_error"  # 消息发送失败
    MESSAGE_PARSE_ERROR = "message_parse_error"  # 消息解析失败

    # 系统相关错误
    MEMORY_ERROR = "memory_error"  # 内存错误
    UNKNOWN_ERROR = "unknown_error"  # 未知错误


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"  # 低：可以忽略，不影响功能
    MEDIUM = "medium"  # 中：影响部分功能，但可以继续
    HIGH = "high"  # 高：严重影响功能，需要立即处理
    CRITICAL = "critical"  # 严重：系统级错误，需要停止


class ErrorAction(Enum):
    """错误处理动作"""
    RETRY = "retry"  # 重试
    FALLBACK = "fallback"  # 降级处理
    SKIP = "skip"  # 跳过
    ABORT = "abort"  # 中止
    IGNORE = "ignore"  # 忽略


class ErrorInfo:
    """错误信息"""

    def __init__(
        self,
        error_type: ErrorType,
        severity: ErrorSeverity,
        message: str,
        exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        suggested_action: Optional[ErrorAction] = None
    ):
        self.error_type = error_type
        self.severity = severity
        self.message = message
        self.exception = exception
        self.context = context or {}
        self.suggested_action = suggested_action

    def __str__(self):
        return f"[{self.error_type.value}] {self.severity.value}: {self.message}"


class ErrorHandler:
    """错误处理器"""

    @staticmethod
    def classify_error(exception: Exception, context: Optional[Dict[str, Any]] = None) -> ErrorInfo:
        """
        分类错误

        Args:
            exception: 异常对象
            context: 上下文信息

        Returns:
            ErrorInfo: 错误信息
        """
        error_message = str(exception)
        error_type = ErrorType.UNKNOWN_ERROR
        severity = ErrorSeverity.MEDIUM
        suggested_action = ErrorAction.RETRY

        # LLM 相关错误
        if "rate limit" in error_message.lower() or "429" in error_message:
            error_type = ErrorType.LLM_RATE_LIMIT
            severity = ErrorSeverity.MEDIUM
            suggested_action = ErrorAction.RETRY

        elif "timeout" in error_message.lower() and "llm" in error_message.lower():
            error_type = ErrorType.LLM_TIMEOUT
            severity = ErrorSeverity.MEDIUM
            suggested_action = ErrorAction.RETRY

        elif "api" in error_message.lower() and ("llm" in error_message.lower() or "model" in error_message.lower()):
            error_type = ErrorType.LLM_API_ERROR
            severity = ErrorSeverity.HIGH
            suggested_action = ErrorAction.FALLBACK

        # 工具相关错误
        elif "tool not found" in error_message.lower():
            error_type = ErrorType.TOOL_NOT_FOUND
            severity = ErrorSeverity.LOW
            suggested_action = ErrorAction.SKIP

        elif "tool" in error_message.lower() and "timeout" in error_message.lower():
            error_type = ErrorType.TOOL_TIMEOUT
            severity = ErrorSeverity.MEDIUM
            suggested_action = ErrorAction.RETRY

        elif "tool" in error_message.lower():
            error_type = ErrorType.TOOL_EXECUTION_ERROR
            severity = ErrorSeverity.MEDIUM
            suggested_action = ErrorAction.FALLBACK

        # 数据库相关错误
        elif "database" in error_message.lower() or "db" in error_message.lower():
            if "timeout" in error_message.lower():
                error_type = ErrorType.DB_TIMEOUT
                severity = ErrorSeverity.HIGH
                suggested_action = ErrorAction.RETRY
            elif "connection" in error_message.lower():
                error_type = ErrorType.DB_CONNECTION_ERROR
                severity = ErrorSeverity.CRITICAL
                suggested_action = ErrorAction.ABORT
            else:
                error_type = ErrorType.DB_QUERY_ERROR
                severity = ErrorSeverity.HIGH
                suggested_action = ErrorAction.FALLBACK

        # 网络相关错误
        elif "network" in error_message.lower() or "connection" in error_message.lower():
            if "timeout" in error_message.lower():
                error_type = ErrorType.NETWORK_TIMEOUT
                severity = ErrorSeverity.MEDIUM
                suggested_action = ErrorAction.RETRY
            else:
                error_type = ErrorType.NETWORK_ERROR
                severity = ErrorSeverity.HIGH
                suggested_action = ErrorAction.RETRY

        # 消息相关错误
        elif "send" in error_message.lower() and "message" in error_message.lower():
            error_type = ErrorType.MESSAGE_SEND_ERROR
            severity = ErrorSeverity.HIGH
            suggested_action = ErrorAction.RETRY

        elif "parse" in error_message.lower() and "message" in error_message.lower():
            error_type = ErrorType.MESSAGE_PARSE_ERROR
            severity = ErrorSeverity.MEDIUM
            suggested_action = ErrorAction.SKIP

        # 内存错误
        elif "memory" in error_message.lower() or "out of memory" in error_message.lower():
            error_type = ErrorType.MEMORY_ERROR
            severity = ErrorSeverity.CRITICAL
            suggested_action = ErrorAction.ABORT

        return ErrorInfo(
            error_type=error_type,
            severity=severity,
            message=error_message,
            exception=exception,
            context=context,
            suggested_action=suggested_action
        )

    @staticmethod
    def handle_error(error_info: ErrorInfo) -> bool:
        """
        处理错误

        Args:
            error_info: 错误信息

        Returns:
            bool: 是否应该继续执行
        """
        # 记录错误
        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"严重错误: {error_info}")
        elif error_info.severity == ErrorSeverity.HIGH:
            logger.error(f"高级错误: {error_info}")
        elif error_info.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"中级错误: {error_info}")
        else:
            logger.info(f"低级错误: {error_info}")

        # 根据建议的动作决定是否继续
        if error_info.suggested_action == ErrorAction.ABORT:
            return False
        else:
            return True

    @staticmethod
    def should_retry(error_info: ErrorInfo, retry_count: int, max_retries: int = 3) -> bool:
        """
        判断是否应该重试

        Args:
            error_info: 错误信息
            retry_count: 当前重试次数
            max_retries: 最大重试次数

        Returns:
            bool: 是否应该重试
        """
        if retry_count >= max_retries:
            return False

        if error_info.suggested_action != ErrorAction.RETRY:
            return False

        # 某些错误类型不应该重试
        if error_info.error_type in [
            ErrorType.TOOL_NOT_FOUND,
            ErrorType.TOOL_INVALID_PARAMS,
            ErrorType.MESSAGE_PARSE_ERROR,
        ]:
            return False

        return True
