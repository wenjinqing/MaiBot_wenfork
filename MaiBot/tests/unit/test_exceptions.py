"""测试异常体系"""
import pytest
from src.llm_models.exceptions import (
    MaiBotException,
    NetworkConnectionError,
    NetworkTimeoutError,
    APIAuthError,
    APIRateLimitError,
    ModelNotAvailableError,
    ModelContextExceededError,
)


@pytest.mark.unit
def test_base_exception():
    """测试基础异常"""
    exc = MaiBotException(
        message="测试错误",
        error_code="TEST_ERROR",
        recoverable=True,
        retry_after=10,
        details={"key": "value"}
    )

    assert exc.message == "测试错误"
    assert exc.error_code == "TEST_ERROR"
    assert exc.recoverable is True
    assert exc.retry_after == 10
    assert exc.details == {"key": "value"}


@pytest.mark.unit
def test_network_connection_error():
    """测试网络连接错误"""
    exc = NetworkConnectionError(
        message="无法连接到服务器",
        host="api.example.com",
        port=443
    )

    assert exc.message == "无法连接到服务器"
    assert exc.error_code == "NETWORK_CONNECTION_ERROR"
    assert exc.recoverable is True
    assert exc.retry_after == 10
    assert exc.details["host"] == "api.example.com"
    assert exc.details["port"] == 443


@pytest.mark.unit
def test_network_timeout_error():
    """测试网络超时错误"""
    exc = NetworkTimeoutError(timeout=30.0)

    assert "超时" in exc.message
    assert exc.error_code == "NETWORK_TIMEOUT_ERROR"
    assert exc.recoverable is True
    assert exc.retry_after == 5
    assert exc.details["timeout"] == 30.0


@pytest.mark.unit
def test_api_auth_error():
    """测试 API 认证错误"""
    exc = APIAuthError(api_provider="OpenAI")

    assert "认证" in exc.message
    assert exc.error_code == "API_AUTH_ERROR"
    assert exc.recoverable is False
    assert exc.retry_after is None
    assert exc.details["api_provider"] == "OpenAI"


@pytest.mark.unit
def test_api_rate_limit_error():
    """测试 API 速率限制错误"""
    exc = APIRateLimitError(retry_after=120, limit=100)

    assert "速率" in exc.message
    assert exc.error_code == "API_RATE_LIMIT_ERROR"
    assert exc.recoverable is True
    assert exc.retry_after == 120
    assert exc.details["limit"] == 100


@pytest.mark.unit
def test_model_not_available_error():
    """测试模型不可用错误"""
    exc = ModelNotAvailableError(model_name="gpt-4")

    assert "不可用" in exc.message
    assert exc.error_code == "MODEL_NOT_AVAILABLE_ERROR"
    assert exc.recoverable is False
    assert exc.details["model_name"] == "gpt-4"


@pytest.mark.unit
def test_model_context_exceeded_error():
    """测试模型上下文超限错误"""
    exc = ModelContextExceededError(
        model_name="gpt-3.5-turbo",
        token_count=5000,
        max_tokens=4096
    )

    assert "上下文" in exc.message
    assert exc.error_code == "MODEL_CONTEXT_EXCEEDED_ERROR"
    assert exc.recoverable is False
    assert exc.details["token_count"] == 5000
    assert exc.details["max_tokens"] == 4096


@pytest.mark.unit
def test_exception_to_dict():
    """测试异常转换为字典"""
    exc = NetworkConnectionError(host="api.example.com")
    exc_dict = exc.to_dict()

    assert exc_dict["error_type"] == "NetworkConnectionError"
    assert exc_dict["error_code"] == "NETWORK_CONNECTION_ERROR"
    assert exc_dict["recoverable"] is True
    assert "host" in exc_dict["details"]


@pytest.mark.unit
def test_exception_str_representation():
    """测试异常的字符串表示"""
    exc = APIRateLimitError(retry_after=60)
    exc_str = str(exc)

    assert "API_RATE_LIMIT_ERROR" in exc_str
    assert "60秒后重试" in exc_str


@pytest.mark.unit
def test_exception_inheritance():
    """测试异常继承关系"""
    exc = NetworkConnectionError()

    assert isinstance(exc, NetworkConnectionError)
    assert isinstance(exc, MaiBotException)
    assert isinstance(exc, Exception)
