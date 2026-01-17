"""Configuration module for ESP-IDF MCP Server.

This module provides security and resource limit configurations.
"""

from .limits import (
    ResourceLimits,
    SecurityConfig,
    ToolTimeouts,
    get_default_config,
    load_config_from_file,
)
from .permissions import (
    Operation,
    OperationWhitelist,
    PathRule,
    get_whitelist,
    set_whitelist,
)

# Backwards compatibility: Config was the old name for SecurityConfig
Config = SecurityConfig

__all__ = [
    # Limits
    "ResourceLimits",
    "ToolTimeouts",
    "SecurityConfig",
    "get_default_config",
    "load_config_from_file",
    # Permissions
    "Operation",
    "OperationWhitelist",
    "PathRule",
    "get_whitelist",
    "set_whitelist",
    # Backwards compatibility
    "Config",
]
