"""
ESP-IDF MCP Server

MCP server for ESP-IDF development workflow.
Provides tools for building, flashing, and monitoring ESP32 projects.
"""

__version__ = "0.1.0"

# Re-export key classes and functions for easier access
from project import ProjectInfo
from server import create_server

__all__ = [
    "__version__",
    "ProjectInfo",
    "create_server",
]
