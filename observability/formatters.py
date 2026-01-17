"""Output formatters for different audiences.

Provides formatting utilities for human-readable and AI-parseable output.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ToolResult:
    """Standardized tool result for formatting.

    Attributes:
        tool_name: Name of the tool.
        success: Whether execution succeeded.
        result: Output result.
        duration: Execution duration in seconds.
        error: Error message if failed.
    """

    tool_name: str
    success: bool
    result: str
    duration: float
    error: str | None = None


class OutputFormatter:
    """Format output for different audiences (AI vs Human).

    Provides consistent formatting for:
    - Tool execution results
    - Metrics summaries
    - Diagnostic reports
    - Workflow progress

    Example:
        formatter = OutputFormatter()

        # Format tool result for human
        human_output = formatter.format_tool_result(
            "esp_build",
            "Build complete",
            5.2,
            True
        )

        # Format metrics summary
        metrics = {
            "esp_build": {
                "call_count": 10,
                "success_rate": 0.9,
                "avg_duration_ms": 5200
            }
        }
        summary = formatter.format_metrics_summary(metrics)
    """

    # ANSI color codes for terminal output
    COLORS = {
        "green": "\033[32m",
        "red": "\033[31m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }

    def format_tool_result(
        self, tool_name: str, result: str, duration: float, success: bool
    ) -> str:
        """Format tool result for human consumption.

        Args:
            tool_name: Name of the tool.
            result: Tool output/result.
            duration: Execution duration in seconds.
            success: Whether execution succeeded.

        Returns:
            Formatted result string.
        """
        status = (
            self._colorize("✓ SUCCESS", "green") if success else self._colorize("✗ FAILED", "red")
        )

        output = [
            f"{self._colorize('Tool:', 'bold')} {tool_name}",
            f"{self._colorize('Status:', 'bold')} {status}",
            f"{self._colorize('Duration:', 'bold')} {duration:.2f}s",
            "",
            f"{self._colorize('Output:', 'bold')}",
            result,
        ]

        return "\n".join(output)

    def format_metrics_summary(self, metrics: dict[str, dict]) -> str:
        """Format metrics summary for display.

        Args:
            metrics: Dictionary of tool_name -> stats mapping.

        Returns:
            Formatted metrics summary.
        """
        if not metrics:
            return "No metrics available."

        lines = [
            self._colorize("Performance Metrics Summary", "bold"),
            "=" * 60,
            "",
        ]

        for tool_name, stats in metrics.items():
            lines.append(f"{self._colorize(tool_name, 'blue')}")
            lines.append(f"  Calls: {stats.get('call_count', 0)}")
            lines.append(f"  Success Rate: {stats.get('success_rate', 0) * 100:.1f}%")
            lines.append(f"  Avg Duration: {stats.get('avg_duration_ms', 0):.1f}ms")
            if "last_called" in stats:
                lines.append(f"  Last Called: {stats['last_called']}")
            lines.append("")

        return "\n".join(lines)

    def format_diagnostic_report(
        self,
        matched_patterns: list[str],
        suggestions: list[str],
        severity: str = "error",
    ) -> str:
        """Format diagnostic report with suggestions.

        Args:
            matched_patterns: List of matched error pattern names.
            suggestions: List of diagnostic suggestions.
            severity: Error severity level.

        Returns:
            Formatted diagnostic report.
        """
        severity_color = "red" if severity == "error" else "yellow"

        lines = [
            f"{self._colorize('Diagnostic Report', 'bold')}",
            "=" * 60,
            "",
            f"{self._colorize('Severity:', 'bold')} {self._colorize(severity.upper(), severity_color)}",
            f"{self._colorize('Matched Patterns:', 'bold')}",
        ]

        for pattern in matched_patterns:
            lines.append(f"  - {pattern}")

        if suggestions:
            lines.append("")
            lines.append(f"{self._colorize('Suggestions:', 'bold')}")
            for i, suggestion in enumerate(suggestions, 1):
                lines.append(f"  {i}. {suggestion}")

        return "\n".join(lines)

    def format_workflow_progress(self, stages: list[dict], total_stages: int) -> str:
        """Format workflow progress with visual indicators.

        Args:
            stages: List of stage dicts with 'name', 'status', 'duration'.
            total_stages: Total number of stages.

        Returns:
            Formatted progress display.
        """
        completed = sum(1 for s in stages if s.get("status") == "completed")
        progress_percent = (completed / total_stages * 100) if total_stages > 0 else 0

        lines = [
            self._colorize("Workflow Progress", "bold"),
            "=" * 60,
            "",
            f"Completed: {completed}/{total_stages} ({progress_percent:.0f}%)",
            "",
        ]

        # Progress bar
        bar_width = 40
        filled = int(bar_width * progress_percent / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"[{bar}]")
        lines.append("")

        # Stage list with status indicators
        for stage in stages:
            name = stage.get("name", "unknown")
            status = stage.get("status", "pending")

            if status == "completed":
                indicator = self._colorize("✓", "green")
            elif status == "failed":
                indicator = self._colorize("✗", "red")
            elif status == "in_progress":
                indicator = self._colorize("⟳", "yellow")
            else:
                indicator = "○"

            duration = stage.get("duration", 0)
            duration_str = f" ({duration:.1f}s)" if duration > 0 else ""

            lines.append(f"  {indicator} {name}{duration_str}")

        return "\n".join(lines)

    def format_bottlenecks(self, bottlenecks: list[dict]) -> str:
        """Format performance bottleneck report.

        Args:
            bottlenecks: List of bottleneck dicts with 'tool_name', 'duration_ms'.

        Returns:
            Formatted bottleneck report.
        """
        if not bottlenecks:
            return "No bottlenecks identified."

        lines = [
            self._colorize("Performance Bottlenecks", "bold"),
            "=" * 60,
            "",
            "The following operations are taking the longest:",
            "",
        ]

        for i, bottleneck in enumerate(bottlenecks, 1):
            tool_name = bottleneck.get("tool_name", "unknown")
            duration = bottleneck.get("avg_duration_ms", 0)
            percentile = bottleneck.get("percentile", 0)

            lines.append(f"{i}. {self._colorize(tool_name, 'yellow')}")
            lines.append(f"   Avg: {duration:.1f}ms (P{percentile:.0f})")

        return "\n".join(lines)

    def _colorize(self, text: str, color: str) -> str:
        """Apply ANSI color to text.

        Args:
            text: Text to colorize.
            color: Color name or style.

        Returns:
            Colorized text with reset code.
        """
        color_code = self.COLORS.get(color, "")
        reset_code = self.COLORS["reset"]
        return f"{color_code}{text}{reset_code}"


class TableFormatter:
    """Format tabular data for terminal display.

    Provides ASCII table formatting for structured data display.

    Example:
        formatter = TableFormatter()

        stats = {
            "esp_build": {"calls": 10, "avg_ms": 5200},
            "esp_flash": {"calls": 5, "avg_ms": 15000}
        }
        table = formatter.format_tool_stats_table(stats)
    """

    def format_tool_stats_table(self, stats: dict[str, dict]) -> str:
        """Format tool statistics as table.

        Args:
            stats: Dictionary of tool_name -> stats mapping.

        Returns:
            ASCII table of tool statistics.
        """
        if not stats:
            return "No tool statistics available."

        # Define columns
        columns = ["Tool", "Calls", "Success Rate", "Avg Duration", "Last Called"]
        col_widths = [20, 8, 13, 13, 20]

        # Header
        lines = ["  ".join(col.ljust(w) for col, w in zip(columns, col_widths, strict=True))]
        lines.append("-" * sum(col_widths) + "-" * (len(col_widths) - 1) * 2)

        # Rows
        for tool_name, tool_stats in stats.items():
            cells = [
                tool_name[: col_widths[0]],
                str(tool_stats.get("call_count", 0)),
                f"{tool_stats.get('success_rate', 0) * 100:.1f}%",
                f"{tool_stats.get('avg_duration_ms', 0):.1f}ms",
                tool_stats.get("last_called", "N/A")[: col_widths[4]],
            ]

            row = "  ".join(cell.ljust(w) for cell, w in zip(cells, col_widths, strict=True))
            lines.append(row)

        return "\n".join(lines)

    def format_stage_progress_table(self, stages: list[dict]) -> str:
        """Format stage progress as table.

        Args:
            stages: List of stage dicts.

        Returns:
            ASCII table of stage progress.
        """
        if not stages:
            return "No stage information available."

        columns = ["Stage", "Status", "Duration", "Last Run"]
        col_widths = [15, 12, 12, 20]

        # Header
        lines = ["  ".join(col.ljust(w) for col, w in zip(columns, col_widths, strict=True))]
        lines.append("-" * sum(col_widths) + "-" * (len(col_widths) - 1) * 2)

        # Rows
        for stage in stages:
            cells = [
                stage.get("name", "unknown")[: col_widths[0]],
                stage.get("status", "unknown")[: col_widths[1]],
                f"{stage.get('duration', 0):.1f}s"[: col_widths[2]],
                stage.get("last_run", "N/A")[: col_widths[3]],
            ]

            row = "  ".join(cell.ljust(w) for cell, w in zip(cells, col_widths, strict=True))
            lines.append(row)

        return "\n".join(lines)

    def format_error_history_table(self, errors: list[dict]) -> str:
        """Format error history as table.

        Args:
            errors: List of error dicts.

        Returns:
            ASCII table of error history.
        """
        if not errors:
            return "No errors recorded."

        columns = ["Time", "Tool", "Pattern", "Severity"]
        col_widths = [20, 15, 25, 10]

        # Header
        lines = ["  ".join(col.ljust(w) for col, w in zip(columns, col_widths, strict=True))]
        lines.append("-" * sum(col_widths) + "-" * (len(col_widths) - 1) * 2)

        # Rows
        for error in errors:
            timestamp = error.get("timestamp", "")
            if timestamp:
                # Parse ISO timestamp and format nicely
                try:
                    dt = datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    timestamp = timestamp[: col_widths[0]]

            cells = [
                timestamp[: col_widths[0]],
                error.get("tool_name", "unknown")[: col_widths[1]],
                error.get("pattern", "unknown")[: col_widths[2]],
                error.get("severity", "unknown")[: col_widths[3]],
            ]

            row = "  ".join(cell.ljust(w) for cell, w in zip(cells, col_widths, strict=True))
            lines.append(row)

        return "\n".join(lines)
