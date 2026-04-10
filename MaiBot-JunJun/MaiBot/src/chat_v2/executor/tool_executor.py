"""
工具执行器：按调用顺序依次执行多个工具（同会话出站发送由 UniversalMessageSender 串行，二者配合避免乱序）
"""

import asyncio
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from src.common.logger import get_logger
from src.chat_v2.models import ToolCall, ToolResult


def _normalize_tool_execute_result(raw: Any) -> Any:
    """将 BaseTool.execute 的返回值转为便于写入对话上下文的文本。"""
    if raw is None:
        return ""
    if isinstance(raw, dict) and "content" in raw:
        return raw["content"]
    if isinstance(raw, dict):
        return json.dumps(raw, ensure_ascii=False)
    return raw


class ToolExecutor:
    """按顺序执行工具（避免多工具同时侧效应发消息时顺序错乱）"""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.logger = get_logger("tool_executor_v2")

    async def execute_tools(
        self,
        tool_calls: List[ToolCall],
        timeout: float = 120.0,
    ) -> List[ToolResult]:
        """
        按列表顺序依次执行工具调用。

        Args:
            tool_calls: 工具调用列表
            timeout: 超时时间（秒）

        Returns:
            工具执行结果列表
        """
        if not tool_calls:
            return []

        self.logger.info(f"开始顺序执行 {len(tool_calls)} 个工具（保证同会话出站顺序与调用一致）")

        start_time = time.time()
        tool_results: List[ToolResult] = []
        for tool_call in tool_calls:
            tool_results.append(await self._execute_single_tool(tool_call, timeout))
        execution_time = time.time() - start_time

        self.logger.info(
            f"工具执行完成，总耗时 {execution_time:.2f}s，"
            f"成功 {sum(1 for r in tool_results if r.success)}/{len(tool_results)}"
        )

        return tool_results

    async def _execute_single_tool(
        self,
        tool_call: ToolCall,
        timeout: float
    ) -> ToolResult:
        """
        执行单个工具

        Args:
            tool_call: 工具调用信息
            timeout: 超时时间

        Returns:
            工具执行结果
        """
        start_time = time.time()

        try:
            # 获取工具函数
            tool_func = self._get_tool_function(tool_call.tool_name)

            if tool_func is None:
                raise ValueError(f"工具 {tool_call.tool_name} 不存在")

            # 执行工具（带超时）
            result = await asyncio.wait_for(
                self._call_tool_function(tool_func, tool_call.arguments),
                timeout=timeout
            )

            execution_time = time.time() - start_time

            self.logger.debug(
                f"工具 {tool_call.tool_name} 执行成功，"
                f"耗时 {execution_time:.2f}s"
            )

            return ToolResult(
                tool_name=tool_call.tool_name,
                success=True,
                content=_normalize_tool_execute_result(result),
                error=None,
                execution_time=execution_time
            )

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            error_msg = f"工具执行超时（{timeout}s）"
            self.logger.warning(f"工具 {tool_call.tool_name} {error_msg}")

            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                content=None,
                error=error_msg,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"工具 {tool_call.tool_name} 执行异常: {e}")

            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                content=None,
                error=str(e),
                execution_time=execution_time
            )

    def _get_tool_function(self, tool_name: str) -> Optional[callable]:
        """
        获取工具实例

        Args:
            tool_name: 工具名称

        Returns:
            工具实例，如果不存在返回 None
        """
        try:
            from src.plugin_system.apis.tool_api import get_tool_instance
            from src.chat.message_receive.chat_stream import get_chat_manager

            # 获取 chat_stream（与 HeartF/入站层使用同一 ChatManager）
            chat_stream = get_chat_manager().get_stream(self.chat_id)

            # 获取工具实例
            tool_instance = get_tool_instance(tool_name, chat_stream)

            if tool_instance is None:
                self.logger.warning(f"未找到工具: {tool_name}")
                return None

            return tool_instance

        except Exception as e:
            self.logger.error(f"获取工具实例失败: {e}")
            return None

    async def _call_tool_function(
        self,
        tool_instance: Any,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        调用工具实例的 execute 方法

        Args:
            tool_instance: 工具实例
            arguments: 参数

        Returns:
            工具执行结果
        """
        payload: Dict[str, Any] = {**(arguments or {}), "llm_called": True}
        return await tool_instance.execute(payload)

    def format_tool_results(self, tool_results: List[ToolResult]) -> str:
        """
        格式化工具结果为文本

        Args:
            tool_results: 工具结果列表

        Returns:
            格式化后的文本
        """
        if not tool_results:
            return ""

        formatted = "以下是你通过工具获取到的实时信息：\n\n"

        for result in tool_results:
            if result.success:
                formatted += f"【{result.tool_name}】\n"
                formatted += f"{result.content}\n\n"
            else:
                formatted += f"【{result.tool_name}】执行失败: {result.error}\n\n"

        formatted += "请基于以上信息回复用户。\n"

        return formatted
