"""ESP-IDF MCP Server Tools Module.

This package contains all tool implementations organized by domain.
Each tool module is responsible for a specific set of related functionality.
"""

from .base import BaseTool, ResourceError, ToolResult
from .build import BuildTools
from .config import ConfigTools
from .exceptions import (
    BuildError,
    ConfigurationError,
    EnvironmentError,
    ESPIDFError,
    FlashError,
    HardwareError,
    MonitorError,
    PermissionError,
    ValidationError,
    WorkflowError,
    get_error_description,
    get_error_suggestion,
)
from .exceptions import (
    ResourceError as ToolResourceError,
)
from .flash import FlashTools
from .monitor import MonitorTools

__all__ = [
    # Base classes
    "BaseTool",
    "ToolResult",
    # Tool modules
    "BuildTools",
    "FlashTools",
    "ConfigTools",
    "MonitorTools",
    # Exceptions (ResourceError from base, others from exceptions)
    "ResourceError",
    "ESPIDFError",
    "EnvironmentError",
    "BuildError",
    "ConfigurationError",
    "HardwareError",
    "FlashError",
    "MonitorError",
    "PermissionError",
    "ToolResourceError",
    "ValidationError",
    "WorkflowError",
    "get_error_description",
    "get_error_suggestion",
]
