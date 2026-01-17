"""ESPTool - Base class for ESP-IDF MCP tools.

Provides common functionality for all ESP-IDF tools including:
- Call timeout control
- Call statistics
- Error handling
- State management
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any


@dataclass
class ToolResult:
    """Standard result structure for tool execution.

    Attributes:
        success: Whether the tool execution succeeded.
        data: Result data payload.
        error: Error message if execution failed.
        meta: Additional metadata (timing, stats, etc.).
    """

    success: bool
    data: Any = None
    error: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class ToolState:
    """Runtime state tracking for tools.

    Attributes:
        call_count: Number of times tool has been called.
        last_call_time: Timestamp of last call.
        is_disabled: Whether tool is disabled.
        disable_reason: Reason for tool being disabled.
        is_busy: Whether tool is currently executing.
    """

    call_count: int = 0
    last_call_time: float = 0.0
    is_disabled: bool = False
    disable_reason: str = ""
    is_busy: bool = False


class ESPTool:
    """Base class for ESP-IDF MCP tools.

    Provides common functionality for all tools including timeout control,
    call statistics, error handling, and state management.

    Attributes:
        name: Tool name identifier.
        description: Human-readable tool description.
        timeout: Default timeout in seconds.
        state: Tool runtime state.
    """

    def __init__(
        self,
        name: str,
        description: str,
        timeout: int = 120,
    ):
        self.name = name
        self.description = description
        self.timeout = timeout
        self.state = ToolState()
        self._pre_callback: Callable | None = None
        self._post_callback: Callable | None = None

    def set_disabled(self, disabled: bool, reason: str = "") -> "ESPTool":
        """Set tool disabled state.

        Args:
            disabled: Whether to disable the tool.
            reason: Reason for disabling (optional).

        Returns:
            Self for chaining.
        """
        self.state.is_disabled = disabled
        self.state.disable_reason = reason
        return self

    def set_pre_callback(self, callback: Callable) -> "ESPTool":
        """Set pre-execution callback.

        Args:
            callback: Function to call before tool execution.

        Returns:
            Self for chaining.
        """
        self._pre_callback = callback
        return self

    def set_post_callback(self, callback: Callable) -> "ESPTool":
        """Set post-execution callback.

        Args:
            callback: Function to call after tool execution.

        Returns:
            Self for chaining.
        """
        self._post_callback = callback
        return self

    def is_hot(self) -> bool:
        """Check if tool is recently active or busy.

        Returns:
            True if tool was called within last second or is currently busy.
        """
        return (time.time() - self.state.last_call_time) < 1.0 or self.state.is_busy

    def get_stats(self) -> dict:
        """Get tool statistics.

        Returns:
            Dictionary with tool stats.
        """
        return {
            "name": self.name,
            "call_count": self.state.call_count,
            "last_call": self.state.last_call_time,
            "is_disabled": self.state.is_disabled,
            "is_busy": self.state.is_busy,
        }


def with_tool_state(func: Callable) -> Callable:
    """Decorator to add standard tool state management to a function.

    Args:
        func: The function to wrap.

    Returns:
        Wrapped function with state management.
    """

    @wraps(func)
    async def async_wrapper(self: ESPTool, *args, **kwargs):
        if self.state.is_disabled:
            return ToolResult(
                success=False,
                error=f"Tool '{self.name}' is disabled: {self.state.disable_reason}",
            )

        if self.state.is_busy:
            return ToolResult(
                success=False,
                error=f"Tool '{self.name}' is currently busy",
            )

        start_time = time.time()
        self.state.is_busy = True
        self.state.call_count += 1
        self.state.last_call_time = start_time

        if self._pre_callback:
            try:
                await self._pre_callback(self, *args, **kwargs)
            except Exception:
                pass  # Pre-callback failure shouldn't stop execution

        try:
            result = await asyncio.wait_for(
                func(self, *args, **kwargs),
                timeout=self.timeout,
            )
            if not isinstance(result, ToolResult):
                result = ToolResult(success=True, data=result)

        except asyncio.TimeoutError:
            result = ToolResult(
                success=False,
                error=f"Tool '{self.name}' timed out after {self.timeout}s",
            )
        except Exception as e:
            result = ToolResult(
                success=False,
                error=f"Tool '{self.name}' failed: {e}",
            )
        finally:
            self.state.is_busy = False
            elapsed = time.time() - start_time
            if result.meta is None:
                result.meta = {}
            result.meta["execution_time"] = elapsed

            if self._post_callback:
                try:
                    await self._post_callback(self, result, *args, **kwargs)
                except Exception:
                    pass

        return result

    @wraps(func)
    def sync_wrapper(self: ESPTool, *args, **kwargs):
        if self.state.is_disabled:
            return ToolResult(
                success=False,
                error=f"Tool '{self.name}' is disabled: {self.state.disable_reason}",
            )

        if self.state.is_busy:
            return ToolResult(
                success=False,
                error=f"Tool '{self.name}' is currently busy",
            )

        start_time = time.time()
        self.state.is_busy = True
        self.state.call_count += 1
        self.state.last_call_time = start_time

        if self._pre_callback:
            try:
                self._pre_callback(self, *args, **kwargs)
            except Exception:
                pass

        try:
            result = func(self, *args, **kwargs)
            if not isinstance(result, ToolResult):
                result = ToolResult(success=True, data=result)

        except Exception as e:
            result = ToolResult(
                success=False,
                error=f"Tool '{self.name}' failed: {e}",
            )
        finally:
            self.state.is_busy = False
            elapsed = time.time() - start_time
            if result.meta is None:
                result.meta = {}
            result.meta["execution_time"] = elapsed

            if self._post_callback:
                try:
                    self._post_callback(self, result, *args, **kwargs)
                except Exception:
                    pass

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


class ToolRegistry:
    """Registry for managing ESPTool instances.

    Provides centralized tool management with filtering,
    statistics, and lookup capabilities.
    """

    def __init__(self):
        self._tools: dict[str, ESPTool] = {}
        self._ignore_list: set[str] = set()
        self._allow_list: set[str] | None = None

    def register(self, tool: ESPTool) -> "ToolRegistry":
        """Register a tool.

        Args:
            tool: Tool instance to register.

        Returns:
            Self for chaining.
        """
        self._tools[tool.name] = tool
        return self

    def unregister(self, name: str) -> "ToolRegistry":
        """Unregister a tool by name.

        Args:
            name: Tool name to unregister.

        Returns:
            Self for chaining.
        """
        self._tools.pop(name, None)
        return self

    def get(self, name: str) -> ESPTool | None:
        """Get tool by name.

        Args:
            name: Tool name.

        Returns:
            Tool instance or None if not found.
        """
        if name in self._ignore_list:
            return None
        if self._allow_list is not None and name not in self._allow_list:
            return None
        return self._tools.get(name)

    def list_all(self) -> list[ESPTool]:
        """List all registered tools.

        Returns:
            List of all tool instances.
        """
        tools = list(self._tools.values())
        if self._allow_list is not None:
            tools = [t for t in tools if t.name in self._allow_list]
        tools = [t for t in tools if t.name not in self._ignore_list]
        return tools

    def ignore(self, *names: str) -> "ToolRegistry":
        """Add tools to ignore list.

        Args:
            *names: Tool names to ignore.

        Returns:
            Self for chaining.
        """
        self._ignore_list.update(names)
        return self

    def allow_only(self, *names: str) -> "ToolRegistry":
        """Set allow list (whitelist mode).

        Args:
            *names: Only these tools will be available.

        Returns:
            Self for chaining.
        """
        self._allow_list = set(names)
        return self

    def get_stats(self) -> dict:
        """Get statistics for all tools.

        Returns:
            Dictionary mapping tool names to their stats.
        """
        return {name: tool.get_stats() for name, tool in self._tools.items()}
