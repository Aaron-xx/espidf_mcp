"""ESP-IDF MCP Observability System.

Provides logging, metrics, and diagnostics for ESP-IDF development.

This module offers:
- Dual-format logging (colored console + JSON files)
- Performance metrics collection
- Error pattern recognition and suggestions

Example:
    from observability import get_logger, get_metrics, get_diagnostics

    logger = get_logger("my_app", log_dir)
    metrics = get_metrics(project_root)
    diagnostics = get_diagnostics()

    logger.info("Application started", version="1.0")
    metrics.record_tool_execution("build", 5.2, True)
"""

from functools import cache
from pathlib import Path


@cache
def get_logger(
    name: str,
    log_dir: Path | None = None,
    console_enabled: bool = True,
    json_enabled: bool = True,
) -> "MCPLogger":
    """Get or create logger instance (thread-safe, Python 3.9+).

    Uses functools.lru_cache for thread-safe singleton pattern.
    The same parameters will always return the same instance.

    Args:
        name: Logger name (e.g., "espidf_mcp", "workflow").
        log_dir: Directory for log files. Defaults to .espidf-mcp/logs/.
        console_enabled: Enable colored console output.
        json_enabled: Enable JSON structured logging.

    Returns:
        MCPLogger instance.

    Note:
        In Python 3.9+, lru_cache is thread-safe and provides
        better performance than manual double-checked locking.
    """
    from .logger import MCPLogger

    if log_dir is None:
        log_dir = Path.cwd() / ".espidf-mcp" / "logs"

    return MCPLogger(
        name=name,
        log_dir=log_dir,
        console_enabled=console_enabled,
        json_enabled=json_enabled,
    )


@cache
def get_metrics(project_root: Path | None = None) -> "MetricsCollector":
    """Get or create metrics collector instance (thread-safe).

    Args:
        project_root: Project root directory. Defaults to cwd.

    Returns:
        MetricsCollector instance.
    """
    from .metrics import MetricsCollector

    if project_root is None:
        project_root = Path.cwd()

    return MetricsCollector(project_root)


@cache
def get_diagnostics() -> "DiagnosticEngine":
    """Get or create diagnostic engine instance (thread-safe).

    Returns:
        DiagnosticEngine instance with built-in error patterns.
    """
    from .diagnostics import DiagnosticEngine

    return DiagnosticEngine()


def reset() -> None:
    """Reset all singleton instances.

    Used primarily for testing to ensure clean state.
    Clears the lru_cache for all singleton functions.
    """
    get_logger.cache_clear()
    get_metrics.cache_clear()
    get_diagnostics.cache_clear()


__all__ = [
    "get_logger",
    "get_metrics",
    "get_diagnostics",
    "reset",
]
