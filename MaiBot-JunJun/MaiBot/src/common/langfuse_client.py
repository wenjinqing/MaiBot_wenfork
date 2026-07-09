"""Langfuse 可观测客户端单例。

埋点原则:
- 未配置 LANGFUSE_ENABLED=true 时,所有方法静默空操作,不影响机器人运行。
- 调用方用 `from src.common.langfuse_client import lf` 取实例,
  用 `lf.start_span(...)` / `lf.start_trace(...)` 包裹关键环节。
- Langfuse 服务不可达时,SDK 内部会静默失败,不会抛异常阻塞业务。
"""
import os
import time as time_module
from typing import Any, Optional

try:
    from langfuse import Langfuse
    _LANGFUSE_AVAILABLE = True
except ImportError:
    _LANGFUSE_AVAILABLE = False
    Langfuse = None  # type: ignore


class _NoopSpan:
    """未启用或 SDK 不可用时的占位 span,链式调用全部空操作。"""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def span(self, *args, **kwargs):
        return self

    def generation(self, *args, **kwargs):
        return self

    def update(self, *args, **kwargs):
        return self

    def end(self, *args, **kwargs):
        return self

    def attribute(self, *args, **kwargs):
        return self


class LangfuseClient:
    """统一封装,屏蔽未启用场景。"""

    def __init__(self) -> None:
        self._enabled = False
        self._client: Optional[Any] = None
        self._init()

    def _init(self) -> None:
        if not _LANGFUSE_AVAILABLE:
            return
        if os.environ.get("LANGFUSE_ENABLED", "false").lower() != "true":
            return
        host = os.environ.get("LANGFUSE_HOST")
        pk = os.environ.get("LANGFUSE_PUBLIC_KEY")
        sk = os.environ.get("LANGFUSE_SECRET_KEY")
        if not (host and pk and sk):
            return
        try:
            self._client = Langfuse(host=host, public_key=pk, secret_key=sk)
            self._enabled = True
        except Exception:
            self._client = None
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start_trace(self, name: str, **kwargs: Any):
        if not self._enabled:
            return _NoopSpan()
        try:
            return self._client.start_trace(name=name, **kwargs)  # type: ignore
        except Exception:
            return _NoopSpan()

    def start_span(self, name: str, **kwargs: Any):
        if not self._enabled:
            return _NoopSpan()
        try:
            return self._client.start_span(name=name, **kwargs)  # type: ignore
        except Exception:
            return _NoopSpan()

    def start_generation(self, name: str, **kwargs: Any):
        if not self._enabled:
            return _NoopSpan()
        try:
            return self._client.start_generation(name=name, **kwargs)  # type: ignore
        except Exception:
            return _NoopSpan()

    def flush(self) -> None:
        if not self._enabled:
            return
        try:
            self._client.flush()  # type: ignore
        except Exception:
            pass


lf = LangfuseClient()

import functools
import asyncio
from typing import Callable


def lf_trace(name: str):
    """异步函数装饰器:以 trace 根节点包裹被装饰函数。

    未启用 Langfuse 时退化为直接调用,零开销。
    用法:
        @lf_trace("reply.generate")
        async def generate_reply_with_context(self, ...): ...
    """

    def decorator(func: Callable):
        if not lf.enabled:
            return func

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            span = lf.start_trace(name=name)
            t0 = time_module.time()
            try:
                result = await func(*args, **kwargs)
                try:
                    span.update(metadata={"duration_ms": int((time_module.time() - t0) * 1000), "status": "ok"})
                except Exception:
                    pass
                return result
            except Exception as e:
                try:
                    span.update(level="ERROR", metadata={"duration_ms": int((time_module.time() - t0) * 1000), "error": str(e)})
                except Exception:
                    pass
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            span = lf.start_trace(name=name)
            t0 = time_module.time()
            try:
                result = func(*args, **kwargs)
                try:
                    span.update(metadata={"duration_ms": int((time_module.time() - t0) * 1000), "status": "ok"})
                except Exception:
                    pass
                return result
            except Exception as e:
                try:
                    span.update(level="ERROR", metadata={"duration_ms": int((time_module.time() - t0) * 1000), "error": str(e)})
                except Exception:
                    pass
                raise

        import inspect as _inspect
        if _inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator