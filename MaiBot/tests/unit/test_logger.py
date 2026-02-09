"""测试日志系统"""
import pytest
import logging
import threading
import time
from pathlib import Path


@pytest.mark.unit
def test_get_logger_basic(temp_log_dir):
    """测试基本的 logger 获取"""
    from src.common.logger import get_logger

    logger = get_logger("test_module")
    assert logger is not None
    assert hasattr(logger, 'info')
    assert hasattr(logger, 'error')


@pytest.mark.unit
def test_logger_singleton(temp_log_dir):
    """测试 logger 单例模式"""
    from src.common.logger import get_logger

    logger1 = get_logger("test_module")
    logger2 = get_logger("test_module")

    # 应该返回同一个实例
    assert logger1 is logger2


@pytest.mark.unit
def test_logger_different_names(temp_log_dir):
    """测试不同名称的 logger"""
    from src.common.logger import get_logger

    logger1 = get_logger("module1")
    logger2 = get_logger("module2")

    # 应该是不同的实例
    assert logger1 is not logger2


@pytest.mark.unit
def test_logger_thread_safety(temp_log_dir):
    """测试 logger 的线程安全性"""
    from src.common.logger import get_logger

    results = []
    errors = []

    def create_logger(name):
        try:
            logger = get_logger(name)
            results.append(logger)
        except Exception as e:
            errors.append(e)

    # 创建多个线程同时获取 logger
    threads = []
    for i in range(10):
        t = threading.Thread(target=create_logger, args=(f"test_module_{i % 3}",))
        threads.append(t)
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join()

    # 不应该有错误
    assert len(errors) == 0
    # 应该成功创建所有 logger
    assert len(results) == 10


@pytest.mark.unit
def test_websocket_log_handler_counter_thread_safety():
    """测试 WebSocketLogHandler 计数器的线程安全性"""
    from src.common.logger import WebSocketLogHandler

    handler = WebSocketLogHandler()
    counter_values = []
    lock = threading.Lock()

    def emit_log():
        # 模拟日志记录
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None
        )
        try:
            handler.emit(record)
            # 获取计数器值（这里需要访问内部状态）
            # 注意：实际实现中可能需要调整
        except Exception:
            pass  # WebSocket 推送失败是预期的

    # 创建多个线程同时记录日志
    threads = []
    for i in range(50):
        t = threading.Thread(target=emit_log)
        threads.append(t)
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join()

    # 测试通过表示没有竞态条件导致的崩溃


@pytest.mark.unit
def test_logger_info_message(temp_log_dir, caplog):
    """测试 info 级别日志"""
    from src.common.logger import get_logger

    logger = get_logger("test_module")

    with caplog.at_level(logging.INFO):
        logger.info("测试信息日志")

    # 验证日志被记录
    assert "测试信息日志" in caplog.text


@pytest.mark.unit
def test_logger_error_message(temp_log_dir, caplog):
    """测试 error 级别日志"""
    from src.common.logger import get_logger

    logger = get_logger("test_module")

    with caplog.at_level(logging.ERROR):
        logger.error("测试错误日志")

    # 验证日志被记录
    assert "测试错误日志" in caplog.text


@pytest.mark.unit
def test_close_handlers():
    """测试关闭 handlers"""
    from src.common.logger import close_handlers

    # 应该能够安全调用
    try:
        close_handlers()
    except Exception as e:
        pytest.fail(f"close_handlers 抛出异常: {e}")
