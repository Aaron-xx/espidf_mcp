"""Performance metrics collection for ESP-IDF MCP tools.

Tracks tool execution times, success rates, and performance bottlenecks.
"""

import json
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np


@dataclass
class ToolExecution:
    """Record of a single tool execution.

    Attributes:
        tool_name: Name of the tool.
        timestamp: Execution timestamp (ISO format).
        duration_ms: Execution duration in milliseconds.
        success: Whether execution succeeded.
        error_type: Error type name if failed.
        args_hash: Hash of arguments for grouping similar calls.
    """

    tool_name: str
    timestamp: str
    duration_ms: float
    success: bool
    error_type: str | None = None
    args_hash: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_type": self.error_type,
        }


@dataclass
class StageMetrics:
    """Metrics for a workflow stage.

    Attributes:
        stage_name: Name of the stage.
        total_runs: Total number of runs.
        successful_runs: Number of successful runs.
        failed_runs: Number of failed runs.
        avg_duration_seconds: Average execution duration.
        min_duration_seconds: Minimum execution duration.
        max_duration_seconds: Maximum execution duration.
        last_execution: Last execution timestamp.
    """

    stage_name: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    avg_duration_seconds: float = 0.0
    min_duration_seconds: float = float("inf")
    max_duration_seconds: float = 0.0
    last_execution: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "stage_name": self.stage_name,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "avg_duration_seconds": self.avg_duration_seconds,
            "min_duration_seconds": self.min_duration_seconds,
            "max_duration_seconds": self.max_duration_seconds,
            "last_execution": self.last_execution,
        }


class MetricsCollector:
    """Collect and aggregate performance metrics.

    Tracks:
    - Tool execution times
    - Success/failure rates
    - Performance bottlenecks
    - Stage durations

    Metrics are persisted to .espidf-mcp/metrics.json

    Example:
        metrics = get_metrics(project_root)

        # Record tool execution
        metrics.record_tool_execution("esp_build", 5.2, True)

        # Get statistics
        stats = metrics.get_tool_stats("esp_build")
        print(f"Success rate: {stats['success_rate']:.1%}")

        # Use context manager for automatic timing
        with PerformanceTimer(metrics, "esp_flash"):
            # ... tool execution ...
    """

    def __init__(self, project_root: Path, retention_days: int = 30):
        """Initialize metrics collector.

        Args:
            project_root: Project root directory.
            retention_days: Number of days to retain metrics.
        """
        self.project_root = Path(project_root)
        self.retention_days = retention_days

        # Metrics storage (protected by lock for thread safety)
        self._tool_executions: list[ToolExecution] = []
        self._stage_metrics: dict[str, StageMetrics] = {}
        self._lock = threading.RLock()  # Reentrant lock for nested calls

        # File paths
        self.mcp_dir = self.project_root / ".espidf-mcp"
        self.metrics_file = self.mcp_dir / "metrics.json"

        # Load existing metrics
        self._load_metrics()

    def record_tool_execution(
        self,
        tool_name: str,
        duration: float,
        success: bool,
        error: Exception | None = None,
        args: dict | None = None,
    ) -> None:
        """Record a tool execution event.

        Thread-safe: Uses internal lock to protect shared state.

        Args:
            tool_name: Name of the tool.
            duration: Execution duration in seconds.
            success: Whether execution succeeded.
            error: Exception if failed.
            args: Tool arguments (for grouping).
        """
        with self._lock:
            # Create execution record
            execution = ToolExecution(
                tool_name=tool_name,
                timestamp=datetime.now().isoformat(),
                duration_ms=duration * 1000,
                success=success,
                error_type=type(error).__name__ if error else None,
                args_hash=self._hash_args(args) if args else None,
            )

            self._tool_executions.append(execution)

            # Prune old executions based on retention
            self._prune_old_metrics()

            # Save to file
            self._save_metrics()

    def record_stage_duration(self, stage_name: str, duration: float, success: bool) -> None:
        """Record stage execution duration.

        Thread-safe: Uses internal lock to protect shared state.

        Args:
            stage_name: Name of the stage.
            duration: Execution duration in seconds.
            success: Whether stage succeeded.
        """
        with self._lock:
            if stage_name not in self._stage_metrics:
                self._stage_metrics[stage_name] = StageMetrics(stage_name=stage_name)

            metrics = self._stage_metrics[stage_name]
            metrics.total_runs += 1
            metrics.last_execution = datetime.now().isoformat()

            if success:
                metrics.successful_runs += 1
            else:
                metrics.failed_runs += 1

            # Update duration stats
            if metrics.total_runs == 1:
                metrics.avg_duration_seconds = duration
                metrics.min_duration_seconds = duration
                metrics.max_duration_seconds = duration
            else:
                # Update average
                n = metrics.total_runs
                metrics.avg_duration_seconds = (
                    metrics.avg_duration_seconds * (n - 1) + duration
                ) / n
                # Update min/max
                metrics.min_duration_seconds = min(metrics.min_duration_seconds, duration)
                metrics.max_duration_seconds = max(metrics.max_duration_seconds, duration)

            # Save to file
            self._save_metrics()

    def get_tool_stats(self, tool_name: str) -> dict:
        """Get statistics for a specific tool.

        Thread-safe: Uses internal lock to ensure consistent snapshot.

        Args:
            tool_name: Name of the tool.

        Returns:
            Dictionary with tool statistics:
            - call_count: Total number of calls
            - success_count: Number of successful calls
            - failure_count: Number of failed calls
            - success_rate: Success rate (0-1)
            - avg_duration_ms: Average duration in milliseconds
            - min_duration_ms: Minimum duration in milliseconds
            - max_duration_ms: Maximum duration in milliseconds
            - last_called: Timestamp of last call
            - last_status: Status of last call ("success" or "failure")
        """
        with self._lock:
            # Filter executions for this tool
            tool_executions = [e for e in self._tool_executions if e.tool_name == tool_name]

            if not tool_executions:
                return {
                    "call_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 0.0,
                    "avg_duration_ms": 0.0,
                    "min_duration_ms": 0.0,
                    "max_duration_ms": 0.0,
                    "last_called": "N/A",
                    "last_status": "unknown",
                }

            # Calculate statistics
            call_count = len(tool_executions)
            success_count = sum(1 for e in tool_executions if e.success)
            failure_count = call_count - success_count

            durations = [e.duration_ms for e in tool_executions]
            avg_duration = sum(durations) / len(durations)

            # Sort by timestamp to get most recent
            sorted_execs = sorted(tool_executions, key=lambda e: e.timestamp, reverse=True)
            last_exec = sorted_execs[0]

            return {
                "call_count": call_count,
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_count / call_count if call_count > 0 else 0.0,
                "avg_duration_ms": avg_duration,
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "last_called": last_exec.timestamp,
                "last_status": "success" if last_exec.success else "failure",
            }

    def get_all_tool_stats(self) -> dict[str, dict]:
        """Get statistics for all tools.

        Thread-safe: Uses internal lock to ensure consistent snapshot.

        Returns:
            Dictionary mapping tool_name -> stats dict.
        """
        with self._lock:
            # Get all unique tool names
            tool_names = set(e.tool_name for e in self._tool_executions)

            return {tool_name: self.get_tool_stats(tool_name) for tool_name in tool_names}

    def get_bottlenecks(self, percentile: float = 90.0) -> list[dict]:
        """Identify performance bottlenecks (slowest operations).

        Thread-safe: Uses internal lock to ensure consistent snapshot.

        Args:
            percentile: Percentile threshold (e.g., 90.0 for P90).

        Returns:
            List of bottleneck dicts:
            - tool_name: Tool name
            - avg_duration_ms: Average duration
            - p{percentile}_duration_ms: Actual percentile value (e.g., p90_duration_ms)
            - call_count: Number of calls
        """
        with self._lock:
            bottlenecks = []

            # Get all tool names
            tool_names = set(e.tool_name for e in self._tool_executions)

            for tool_name in tool_names:
                # Get all executions for this tool
                executions = [
                    e.duration_ms for e in self._tool_executions if e.tool_name == tool_name
                ]

                # Only include tools with sufficient data
                if len(executions) < 3:
                    continue

                # Calculate actual percentile value using numpy
                percentile_value = float(np.percentile(executions, percentile))
                avg_duration = sum(executions) / len(executions)

                bottlenecks.append(
                    {
                        "tool_name": tool_name,
                        "avg_duration_ms": avg_duration,
                        f"p{int(percentile)}_duration_ms": percentile_value,  # e.g., p90_duration_ms
                        "call_count": len(executions),
                    }
                )

            # Sort by actual percentile value (descending), not average
            # This correctly identifies tools with slow outlier operations
            percentile_key = f"p{int(percentile)}_duration_ms"
            bottlenecks.sort(key=lambda x: x[percentile_key], reverse=True)

            return bottlenecks

    def get_failure_summary(self) -> dict[str, dict]:
        """Get failure patterns by tool.

        Thread-safe: Uses internal lock to ensure consistent snapshot.

        Returns:
            Dictionary mapping tool_name -> failure info:
            - total_failures: Number of failures
            - common_errors: List of common error types
            - failure_rate: Failure rate (0-1)
        """
        with self._lock:
            summary = {}

            for tool_name in set(e.tool_name for e in self._tool_executions):
                tool_executions = [e for e in self._tool_executions if e.tool_name == tool_name]

                failures = [e for e in tool_executions if not e.success]

                if not failures:
                    continue

                # Count error types
                error_counts: dict[str, int] = defaultdict(int)
                for e in failures:
                    if e.error_type:
                        error_counts[e.error_type] += 1

                # Get most common errors
                common_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]

                summary[tool_name] = {
                    "total_failures": len(failures),
                    "common_errors": [
                        {"error_type": err, "count": count} for err, count in common_errors
                    ],
                    "failure_rate": len(failures) / len(tool_executions),
                }

            return summary

    def get_stage_metrics(self, stage_name: str) -> StageMetrics | None:
        """Get metrics for a specific stage.

        Thread-safe: Uses internal lock to ensure consistent read.

        Args:
            stage_name: Name of the stage.

        Returns:
            StageMetrics or None if not found.
        """
        with self._lock:
            return self._stage_metrics.get(stage_name)

    def _save_metrics(self) -> None:
        """Persist metrics to file.

        Note: Must be called when holding self._lock.
        """
        # Create directory if needed
        self.mcp_dir.mkdir(exist_ok=True)

        # Prepare data
        data = {
            "tool_executions": [e.to_dict() for e in self._tool_executions],
            "stage_metrics": {name: m.to_dict() for name, m in self._stage_metrics.items()},
            "last_updated": datetime.now().isoformat(),
        }

        # Write to file
        self.metrics_file.write_text(json.dumps(data, indent=2))

    def _load_metrics(self) -> None:
        """Load metrics from file.

        Note: Only called from __init__ (single-threaded construction).
        Does not acquire lock as no other threads can access instance yet.
        """
        if not self.metrics_file.exists():
            return

        try:
            data = json.loads(self.metrics_file.read_text())

            # Load tool executions
            if "tool_executions" in data:
                self._tool_executions = [ToolExecution(**e) for e in data["tool_executions"]]

            # Load stage metrics
            if "stage_metrics" in data:
                for name, m_data in data["stage_metrics"].items():
                    stage_metrics = StageMetrics(
                        stage_name=name,
                        total_runs=m_data.get("total_runs", 0),
                        successful_runs=m_data.get("successful_runs", 0),
                        failed_runs=m_data.get("failed_runs", 0),
                        avg_duration_seconds=m_data.get("avg_duration_seconds", 0.0),
                        min_duration_seconds=m_data.get("min_duration_seconds", 0.0),
                        max_duration_seconds=m_data.get("max_duration_seconds", 0.0),
                        last_execution=m_data.get("last_execution", ""),
                    )
                    self._stage_metrics[name] = stage_metrics

            # Prune old metrics
            self._prune_old_metrics()

        except Exception:
            # If loading fails, start fresh
            self._tool_executions = []
            self._stage_metrics = {}

    def _prune_old_metrics(self) -> None:
        """Remove metrics older than retention period.

        Note: Must be called when holding self._lock.
        """
        if self.retention_days <= 0:
            return

        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=self.retention_days)

        # Prune tool executions
        self._tool_executions = [
            e for e in self._tool_executions if datetime.fromisoformat(e.timestamp) > cutoff
        ]

    @staticmethod
    def _hash_args(args: dict) -> str:
        """Create hash of arguments for grouping.

        Args:
            args: Arguments dictionary.

        Returns:
            Hash string.
        """
        import hashlib

        # Convert to sorted JSON and hash
        args_json = json.dumps(args, sort_keys=True)
        return hashlib.md5(args_json.encode()).hexdigest()[:8]


@contextmanager
def PerformanceTimer(metrics: MetricsCollector, operation: str, record_on_success: bool = True):
    """Context manager for timing code blocks.

    Automatically records execution time to metrics collector.

    Args:
        metrics: MetricsCollector instance.
        operation: Name of the operation being timed.
        record_on_success: Only record if no exception occurs.

    Example:
        with PerformanceTimer(metrics, "esp_build"):
            result = subprocess.run(["idf.py", "build"])
        # Execution time automatically recorded

    Yields:
        PerformanceTimer instance with `duration` attribute.
    """
    start_time = time.time()
    exception_occurred = False

    class TimerResult:
        """Timer result holder."""

        def __init__(self):
            self.duration: float = 0.0

    result = TimerResult()

    try:
        yield result
    except Exception:
        exception_occurred = True
        raise
    finally:
        result.duration = time.time() - start_time

        # Record if enabled
        if not record_on_success or not exception_occurred:
            metrics.record_tool_execution(
                tool_name=operation,
                duration=result.duration,
                success=not exception_occurred,
                error=None if not exception_occurred else Exception("Operation failed"),
            )
