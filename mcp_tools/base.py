"""Base tool class and result handling for ESP-IDF MCP tools.

Provides common functionality for all tools:
- Standardized result handling
- Subprocess execution wrappers
- Error handling and sanitization
- Tool call logging and metrics
- Resource monitoring and limits
"""

import functools
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP

# Import exception types
from .exceptions import ResourceError

# Optional dependencies for resource monitoring
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class ToolResult:
    """Standardized tool result for consistent error handling.

    Provides consistent formatting for tool responses across all ESP-IDF MCP tools.
    Sanitizes sensitive information and provides structured error reporting.

    Attributes:
        success: Whether the operation succeeded.
        message: Human-readable status message.
        details: Detailed output or error information.
        error_code: Error code for programmatic handling.
        duration_seconds: Operation duration in seconds.
    """

    success: bool
    message: str
    details: str = ""
    error_code: str | None = None
    duration_seconds: float = 0.0

    def to_response(self) -> str:
        """Format as MCP tool response string.

        Returns:
            Formatted response string.
        """
        if self.success:
            parts = [self.message]
            if self.duration_seconds > 0:
                parts.append(f" (duration: {self.duration_seconds:.2f}s)")
            if self.details:
                parts.append(f"\n\n{self._sanitize_details(self.details)}")
            return "".join(parts)
        else:
            parts = []
            if self.error_code:
                parts.append(f"[{self.error_code}] ")
            parts.append(f"Error: {self.message}")
            if self.details:
                parts.append(f"\n\n{self._sanitize_details(self.details)}")
            return "".join(parts)

    @staticmethod
    def _sanitize_details(details: str) -> str:
        """Sanitize details to prevent information disclosure.

        Removes or masks potentially sensitive paths and information.

        Args:
            details: Raw details string.

        Returns:
            Sanitized details string.
        """
        # Remove user-specific paths (e.g., /home/username/)
        # Replace with ~/ for clarity
        sanitized = re.sub(r"/home/[^/]+/", "~/", details)
        # Also handle Windows paths
        sanitized = re.sub(r"[A-Z]:\\\\Users\\\\[^\\\\]+\\\\", "~/", sanitized, flags=re.IGNORECASE)
        # Remove any remaining absolute paths to user home
        sanitized = re.sub(r"/home/\w+/", "~/", sanitized)

        return sanitized

    @classmethod
    def from_subprocess(
        cls,
        result: subprocess.CompletedProcess[str],
        operation: str,
        duration: float = 0.0,
    ) -> "ToolResult":
        """Create ToolResult from subprocess result.

        Args:
            result: Subprocess completed process result.
            operation: Operation name (e.g., "Build", "Flash").
            duration: Operation duration in seconds.

        Returns:
            ToolResult instance.
        """
        if result.returncode == 0:
            return cls(
                success=True,
                message=f"{operation} succeeded",
                details=result.stdout.strip(),
                duration_seconds=duration,
            )
        else:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()

            # Combine stderr and stdout for error context
            details = stderr
            if stdout and stdout != stderr:
                details = f"{stderr}\n\n{stdout}" if stderr else stdout

            return cls(
                success=False,
                message=f"{operation} failed",
                details=details,
                error_code=f"EXIT_{result.returncode}",
                duration_seconds=duration,
            )


def format_subprocess_result(
    result: subprocess.CompletedProcess[str],
    operation: str,
    duration: float = 0.0,
) -> str:
    """Format subprocess result consistently.

    Standardizes subprocess result formatting across all tools:
    - Consistent success/error message format
    - Sanitized output (removes sensitive paths)
    - Error codes for programmatic handling
    - Duration information when available

    Args:
        result: Subprocess completed process result.
        operation: Operation name (e.g., "Build", "Flash").
        duration: Operation duration in seconds.

    Returns:
        Formatted response string.
    """
    return ToolResult.from_subprocess(result, operation, duration).to_response()


class ResourceMonitor:
    """Monitor resource usage during tool execution.

    Provides resource monitoring capabilities when psutil is available.
    """

    def __init__(self, max_memory_mb: int = 1024, max_execution_time: int = 600):
        """Initialize resource monitor.

        Args:
            max_memory_mb: Maximum memory usage in MB
            max_execution_time: Maximum execution time in seconds
        """
        self.max_memory_mb = max_memory_mb
        self.max_execution_time = max_execution_time
        self.start_time: float | None = None
        self.start_memory: int | None = None

    def start(self) -> None:
        """Start monitoring resources."""
        self.start_time = time.time()
        if HAS_PSUTIL:
            try:
                process = psutil.Process()
                self.start_memory = process.memory_info().rss
            except Exception:
                self.start_memory = None

    def check_limits(self, tool_name: str) -> None:
        """Check if resource limits are exceeded.

        Args:
            tool_name: Name of the tool being executed

        Raises:
            ResourceError: If limits are exceeded
        """
        if not HAS_PSUTIL:
            # psutil not available, skip monitoring
            return

        try:
            process = psutil.Process()

            # Check execution time
            if self.start_time:
                elapsed = time.time() - self.start_time
                if elapsed > self.max_execution_time:
                    raise ResourceError(
                        f"Tool '{tool_name}' exceeded maximum execution time: "
                        f"{elapsed:.1f}s > {self.max_execution_time}s"
                    )

            # Check memory usage
            current_memory = process.memory_info().rss
            current_mb = current_memory / (1024 * 1024)

            if current_mb > self.max_memory_mb:
                raise ResourceError(
                    f"Tool '{tool_name}' exceeded maximum memory usage: "
                    f"{current_mb:.1f}MB > {self.max_memory_mb}MB"
                )

        except psutil.Error:
            # psutil error, log but don't fail
            pass

    def get_usage_summary(self) -> dict[str, Any]:
        """Get current resource usage summary.

        Returns:
            Dict with current usage statistics
        """
        summary = {
            "monitoring_enabled": HAS_PSUTIL,
        }

        if not HAS_PSUTIL or not self.start_time:
            return summary

        try:
            process = psutil.Process()
            elapsed = time.time() - self.start_time
            current_memory = process.memory_info().rss

            summary.update(
                {
                    "elapsed_seconds": elapsed,
                    "memory_mb": current_memory / (1024 * 1024),
                    "memory_delta_mb": (current_memory - self.start_memory) / (1024 * 1024)
                    if self.start_memory
                    else 0,
                }
            )
        except Exception:
            pass

        return summary


class BaseTool:
    """Base class for ESP-IDF MCP tools.

    Provides common functionality for tool implementations:
    - MCP server registration
    - Subprocess execution with timeout
    - Result formatting
    - Error handling
    - Tool call logging and metrics

    Subclasses should override the register_tools() method to register
    their specific tools with the MCP server.
    """

    def __init__(
        self,
        project: Any,
        mcp: FastMCP,
        workflow: Any = None,
        logger: Any = None,
        metrics: Any = None,
        security_config: Any = None,
    ):
        """Initialize tool with project, MCP server, and optional components.

        Args:
            project: ProjectInfo instance.
            mcp: FastMCP server instance.
            workflow: Optional Workflow instance for state management tools.
            logger: Optional MCPLogger instance for logging tool calls.
            metrics: Optional MetricsCollector instance for collecting metrics.
            security_config: Optional SecurityConfig for resource limits.
        """
        self.project = project
        self.mcp = mcp
        self.workflow = workflow
        self.logger = logger
        self.metrics = metrics
        self.security_config = security_config

        # Initialize resource monitor if security config is provided
        self.resource_monitor = None
        if security_config and security_config.resource_limits.enable_monitoring:
            limits = security_config.resource_limits
            self.resource_monitor = ResourceMonitor(
                max_memory_mb=limits.max_memory_mb,
                max_execution_time=limits.max_execution_time,
            )

    def get_timeout(self, tool_name: str) -> int:
        """Get timeout for a specific tool.

        Args:
            tool_name: Name of the tool (e.g., "esp_build")

        Returns:
            Timeout in seconds
        """
        if self.security_config and self.security_config.timeouts:
            return self.security_config.timeouts.get_timeout(tool_name)  # type: ignore[no-any-return]
        return 60  # Default timeout

    def _check_resources(self, tool_name: str) -> None:
        """Check if resource limits are respected.

        Args:
            tool_name: Name of the tool being executed

        Raises:
            ResourceError: If resource limits are exceeded
        """
        if self.resource_monitor:
            self.resource_monitor.check_limits(tool_name)

    def _log_tool_call(self, func):
        """Decorator to log tool calls and collect metrics.

        Args:
            func: The tool function to wrap.

        Returns:
            Wrapped function with logging and metrics collection.
        """

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tool_name = func.__name__
            start_time = time.time()

            try:
                # Start resource monitoring
                if self.resource_monitor:
                    self.resource_monitor.start()

                # Check resource limits before execution
                self._check_resources(tool_name)

                # Execute the tool function
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Final resource check after execution
                self._check_resources(tool_name)

                # Log successful tool call
                if self.logger:
                    self.logger.log_tool_call(
                        tool_name=tool_name,
                        args=kwargs,
                        result=str(result)[:500] if result else "",
                        duration=duration,
                        success=True,
                    )

                # Record metrics
                if self.metrics:
                    self.metrics.record_tool_execution(
                        tool_name=tool_name,
                        duration=duration,
                        success=True,
                        args=kwargs,
                    )

                return result

            except ResourceError as e:
                duration = time.time() - start_time

                # Log resource limit violation
                if self.logger:
                    self.logger.log_tool_call(
                        tool_name=tool_name,
                        args=kwargs,
                        result=str(e)[:500],
                        duration=duration,
                        success=False,
                    )

                # Record metrics for resource limit violation
                if self.metrics:
                    self.metrics.record_tool_execution(
                        tool_name=tool_name,
                        duration=duration,
                        success=False,
                        error=e,
                        error_type="ResourceError",
                        args=kwargs,
                    )

                raise

            except Exception as e:
                duration = time.time() - start_time

                # Log failed tool call
                if self.logger:
                    self.logger.log_tool_call(
                        tool_name=tool_name,
                        args=kwargs,
                        result=str(e)[:500],
                        duration=duration,
                        success=False,
                    )

                # Record metrics for failure
                if self.metrics:
                    self.metrics.record_tool_execution(
                        tool_name=tool_name,
                        duration=duration,
                        success=False,
                        error=e,
                        args=kwargs,
                    )

                raise

        return wrapper

    def register_tools(self) -> None:
        """Register all tools for this module with the MCP server.

        Subclasses should override this method to register their tools.
        """
        raise NotImplementedError("Subclasses must implement register_tools()")

    def _run_command(
        self,
        cmd: list[str],
        timeout: int = 60,
        capture_output: bool = True,
        tool_name: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run command with default settings.

        Args:
            cmd: Command and arguments to execute.
            timeout: Timeout in seconds. If tool_name is provided and
                security_config has timeouts configured, uses configured timeout.
            capture_output: Whether to capture stdout/stderr.
            tool_name: Name of the tool calling this function, for timeout lookup.

        Returns:
            Completed process result.
        """
        # Use configured timeout if tool_name is provided
        if tool_name and timeout == 60:  # Only if using default
            configured_timeout = self.get_timeout(tool_name)
            if configured_timeout != 60:
                timeout = configured_timeout

        return subprocess.run(
            cmd,
            cwd=self.project.root,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
        )
