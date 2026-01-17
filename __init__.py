"""
ESP-IDF MCP Server

MCP server for ESP-IDF development workflow.
Provides tools for building, flashing, monitoring, and workflow management.
"""

__version__ = "0.2.0"

# Re-export key classes and functions for easier access
from checkers import BaseChecker, CheckerRegistry, CheckerReport
from config import Config
from project import ProjectInfo
from server import create_server

# Core modules
from tools import ESPTool, ToolRegistry, ToolResult
from workflow import Stage, StageStatus, Workflow
from workflow_server import create_workflow_server

__all__ = [
    "__version__",
    # Core
    "ProjectInfo",
    "create_server",
    "create_workflow_server",
    # Tools
    "ESPTool",
    "ToolRegistry",
    "ToolResult",
    # Checkers
    "BaseChecker",
    "CheckerRegistry",
    "CheckerReport",
    # Workflow
    "Workflow",
    "Stage",
    "StageStatus",
    # Config
    "Config",
]
