"""Dual-format logging system for ESP-IDF MCP.

Provides colored console output for humans and JSON logs for AI consumption.
"""

import json
import logging
import re
from datetime import datetime
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class LogLevel(Enum):
    """Log level enumeration."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class ColoredFormatter(logging.Formatter):
    """Terminal formatter with ANSI colors.

    Color mapping:
    - DEBUG: Cyan
    - INFO: Green
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Magenta
    """

    # ANSI color codes
    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, fmt: str | None = None, datefmt: str | None = None, use_colors: bool = True):
        """Initialize colored formatter.

        Args:
            fmt: Log message format string.
            datefmt: Date format string.
            use_colors: Enable colored output.
        """
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with optional colors.

        Args:
            record: Log record to format.

        Returns:
            Formatted log string.
        """
        if self.use_colors:
            level_color = self.COLORS.get(record.levelno, "")
            record.levelname = f"{level_color}{record.levelname}{self.RESET}"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logs.

    Produces newline-delimited JSON (JSONL) for easy parsing.
    Each log entry includes:
    - timestamp: ISO 8601 timestamp
    - level: Log level name (plain text, no colors)
    - message: Log message (sanitized)
    - logger: Logger name
    - context: Additional metadata from log call
    """

    # Control characters to remove (all except \n, \r, \t)
    _CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

    @staticmethod
    def _sanitize_string(value: Any) -> Any:
        """Sanitize string values by removing dangerous control characters.

        Args:
            value: Value to sanitize (strings are processed, others returned as-is).

        Returns:
            Sanitized value safe for JSON encoding.
        """
        if isinstance(value, str):
            # Remove control characters except \n, \r, \t
            return JSONFormatter._CONTROL_CHARS_PATTERN.sub("", value)
        elif isinstance(value, (list, tuple)):
            return type(value)(JSONFormatter._sanitize_string(v) for v in value)
        elif isinstance(value, dict):
            return {k: JSONFormatter._sanitize_string(v) for k, v in value.items()}
        return value

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format.

        Returns:
            JSON string (single line, no pretty-printing).
        """
        # Get the original levelname without ANSI codes
        # Use levelno instead to get the clean level name
        level_map = {
            logging.DEBUG: "DEBUG",
            logging.INFO: "INFO",
            logging.WARNING: "WARNING",
            logging.ERROR: "ERROR",
            logging.CRITICAL: "CRITICAL",
        }
        clean_level = level_map.get(record.levelno, record.levelname)

        # Sanitize message to remove control characters
        message = record.getMessage()
        sanitized_message = self._sanitize_string(message)

        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": clean_level,
            "logger": record.name,
            "message": sanitized_message,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present (also sanitized)
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            log_entry["exception"] = self._sanitize_string(exc_text)

        # Add context from extra fields
        # Look for fields that aren't standard LogRecord attributes
        standard_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "getMessage",
            "exc_info",
            "exc_text",
            "stack_info",
            "asctime",
            "message",
        }
        context = {}
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                # Sanitize context values
                context[key] = self._sanitize_string(value)

        if context:
            log_entry["context"] = context

        # Use default=str to handle non-serializable objects
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class MCPLogger:
    """Dual-format logger with colored console and JSON file output.

    Features:
    - Colored console output for human readability
    - JSON structured logs for AI consumption
    - Automatic log rotation (10MB max, 5 backups)
    - Context metadata support

    Example:
        logger = get_logger("my_app", log_dir)

        # Basic logging
        logger.info("Build succeeded")
        logger.error("Build failed", error_code=1)

        # Tool execution logging
        logger.log_tool_call(
            tool_name="esp_build",
            args={"target": "esp32"},
            result="Build complete",
            duration=5.2,
            success=True
        )

        # Stage transition logging
        logger.log_stage_transition(
            stage="build",
            from_status="pending",
            to_status="completed",
            metadata={"duration": 5.2}
        )
    """

    def __init__(
        self,
        name: str,
        log_dir: Path,
        console_enabled: bool = True,
        json_enabled: bool = True,
        max_file_size: int = 10_000_000,  # 10MB
        backup_count: int = 5,
    ):
        """Initialize dual-format logger.

        Args:
            name: Logger name.
            log_dir: Directory for log files.
            console_enabled: Enable colored console output.
            json_enabled: Enable JSON file logging.
            max_file_size: Maximum size of each log file before rotation.
            backup_count: Number of backup files to keep.
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.console_enabled = console_enabled
        self.json_enabled = json_enabled

        # Create log directories
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir = self.log_dir / "structured"
        self.json_dir.mkdir(exist_ok=True)
        self.archive_dir = self.log_dir / "archive"
        self.archive_dir.mkdir(exist_ok=True)

        # Create logger
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()  # Clear any existing handlers

        # Console handler (colored)
        if console_enabled:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = ColoredFormatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                use_colors=True,
            )
            console_handler.setFormatter(console_formatter)
            self._logger.addHandler(console_handler)

        # File handlers
        if json_enabled:
            # JSONL structured log
            json_file = self.json_dir / f"{name}.jsonl"
            json_handler = RotatingFileHandler(
                json_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            json_handler.setLevel(logging.DEBUG)
            json_formatter = JSONFormatter()
            json_handler.setFormatter(json_formatter)
            self._logger.addHandler(json_handler)

            # Human-readable log
            text_file = self.log_dir / f"{name}.log"
            text_handler = RotatingFileHandler(
                text_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            text_handler.setLevel(logging.INFO)
            text_formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            text_handler.setFormatter(text_formatter)
            self._logger.addHandler(text_handler)

    def debug(self, message: str, **context) -> None:
        """Log DEBUG message with optional context.

        Args:
            message: Log message.
            **context: Additional metadata for JSON logs.
        """
        self._logger.debug(message, extra=context)

    def info(self, message: str, **context) -> None:
        """Log INFO message with optional context.

        Args:
            message: Log message.
            **context: Additional metadata for JSON logs.
        """
        self._logger.info(message, extra=context)

    def warning(self, message: str, **context) -> None:
        """Log WARNING message with optional context.

        Args:
            message: Log message.
            **context: Additional metadata for JSON logs.
        """
        self._logger.warning(message, extra=context)

    def error(self, message: str, exception: Exception | None = None, **context) -> None:
        """Log ERROR message with optional exception and context.

        Args:
            message: Log message.
            exception: Exception object (will include stack trace).
            **context: Additional metadata for JSON logs.
        """
        if exception:
            self._logger.error(
                message,
                exc_info=(type(exception), exception, exception.__traceback__),
                extra=context,
            )
        else:
            self._logger.error(message, extra=context)

    def critical(self, message: str, **context) -> None:
        """Log CRITICAL message with optional context.

        Args:
            message: Log message.
            **context: Additional metadata for JSON logs.
        """
        self._logger.critical(message, extra=context)

    def log_tool_call(
        self,
        tool_name: str,
        args: dict,
        result: str,
        duration: float,
        success: bool,
    ) -> None:
        """Structured logging for tool execution.

        Args:
            tool_name: Name of the tool that was called.
            args: Arguments passed to the tool.
            result: Result/output from the tool.
            duration: Execution duration in seconds.
            success: Whether the tool execution succeeded.
        """
        level = logging.INFO if success else logging.ERROR
        status = "SUCCESS" if success else "FAILED"

        self._logger.log(
            level,
            f"Tool {status}: {tool_name} ({duration:.2f}s)",
            extra={
                "tool_name": tool_name,
                "tool_args": args,
                "tool_result": result[:500] if result else "",  # Truncate long results
                "duration_seconds": duration,
                "success": success,
                "event_type": "tool_call",
            },
        )

    def log_stage_transition(
        self,
        stage: str,
        from_status: str,
        to_status: str,
        metadata: dict | None = None,
    ) -> None:
        """Structured logging for workflow stage transitions.

        Args:
            stage: Stage name.
            from_status: Previous status (e.g., "pending", "in_progress").
            to_status: New status (e.g., "in_progress", "completed", "failed").
            metadata: Optional additional metadata.
        """
        extra = {
            "stage": stage,
            "from_status": from_status,
            "to_status": to_status,
            "event_type": "stage_transition",
        }
        if metadata:
            extra.update(metadata)

        self._logger.info(
            f"Stage transition: {stage} {from_status} -> {to_status}",
            extra=extra,
        )

    def log_error_diagnosis(
        self,
        error_output: str,
        patterns_matched: list[str],
        suggestions: list[str],
        severity: str = "error",
    ) -> None:
        """Log error diagnosis results.

        Args:
            error_output: Original error output.
            patterns_matched: List of matched error pattern names.
            suggestions: List of diagnostic suggestions.
            severity: Error severity level.
        """
        self._logger.error(
            f"Error diagnosis: {len(patterns_matched)} patterns matched, {len(suggestions)} suggestions",
            extra={
                "error_output": error_output[:500],  # Truncate
                "patterns_matched": patterns_matched,
                "suggestions": suggestions,
                "severity": severity,
                "event_type": "error_diagnosis",
            },
        )

    @property
    def logger(self) -> logging.Logger:
        """Get the underlying Python logger."""
        return self._logger
