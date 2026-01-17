"""Resource limits configuration for ESP-IDF MCP Server.

This module defines resource limits to prevent abuse and ensure safe operation
when called by external agents.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResourceLimits:
    """Resource limits for tool execution.

    These limits prevent excessive resource consumption by external agents.
    Limits are checked before and during tool execution.

    Attributes:
        max_memory_mb: Maximum memory usage in MB per tool execution
        max_execution_time: Maximum execution time in seconds
        max_disk_usage_mb: Maximum temporary disk usage in MB
        max_subprocesses: Maximum concurrent subprocesses
        enable_monitoring: Whether to enable resource monitoring
    """

    max_memory_mb: int = 1024
    max_execution_time: int = 600
    max_disk_usage_mb: int = 2048
    max_subprocesses: int = 5
    enable_monitoring: bool = True


@dataclass
class ToolTimeouts:
    """Timeout configuration for each tool.

    Different tools have different timeout requirements based on their
    typical execution duration.

    Attributes:
        build: Timeout for build operations (10 minutes)
        flash: Timeout for flash operations (10 minutes)
        monitor: Timeout for monitor operations (20 minutes)
        clean: Timeout for clean operations (1 minute)
        size: Timeout for size analysis (30 seconds)
        default: Default timeout for unspecified tools (1 minute)
    """

    build: int = 600
    flash: int = 600
    monitor: int = 1200
    clean: int = 60
    size: int = 30
    default: int = 60

    def get_timeout(self, tool_name: str) -> int:
        """Get timeout for a specific tool.

        Args:
            tool_name: Name of the tool (e.g., "esp_build")

        Returns:
            Timeout in seconds
        """
        # Remove "esp_" prefix if present
        name = tool_name.replace("esp_", "")

        # Return specific timeout or default
        return getattr(self, name, self.default)


@dataclass
class SecurityConfig:
    """Security configuration for MCP server.

    Combines resource limits and other security settings.

    Attributes:
        resource_limits: Resource consumption limits
        timeouts: Tool-specific timeouts
        strict_mode: Whether to enforce strict checking (fail fast)
    """

    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    timeouts: ToolTimeouts = field(default_factory=ToolTimeouts)
    strict_mode: bool = False


def load_config_from_file(config_path: Path) -> SecurityConfig:
    """Load security configuration from a file.

    Args:
        config_path: Path to configuration file (YAML or JSON)

    Returns:
        SecurityConfig instance

    Note:
        This is a placeholder for future implementation.
        Currently returns default configuration.
    """
    # TODO: Implement YAML/JSON config loading
    return SecurityConfig()


# Default singleton instance
_default_config: SecurityConfig | None = None


def get_default_config() -> SecurityConfig:
    """Get the default security configuration.

    Returns:
        Default SecurityConfig instance
    """
    global _default_config
    if _default_config is None:
        _default_config = SecurityConfig()
    return _default_config
