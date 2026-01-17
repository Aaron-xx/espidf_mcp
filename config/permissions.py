"""Operation whitelist for ESP-IDF MCP Server.

This module defines which file system operations are allowed to prevent
unauthorized access when called by external agents.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class Operation:
    """Defines a file system operation.

    Attributes:
        name: Operation name (read, write, delete, execute)
        description: Human-readable description
    """

    name: Literal["read", "write", "delete", "execute"]
    description: str


@dataclass
class PathRule:
    """Defines a path rule for operations.

    Attributes:
        path_pattern: Path pattern (supports {project_root} variable)
        allowed_operations: List of allowed operations
        description: Description of this path rule
    """

    path_pattern: str
    allowed_operations: list[Literal["read", "write", "delete", "execute"]]
    description: str


class OperationWhitelist:
    """Manages allowed file system operations.

    This class implements a whitelist-based permission system where only
    explicitly allowed paths and operations are permitted.

    Attributes:
        project_root: Root directory of the ESP-IDF project
        path_rules: List of path rules
        strict_mode: Whether to enforce strict checking (fail on unknown paths)

    Example:
        >>> whitelist = OperationWhitelist(project_root=Path("/project"))
        >>> whitelist.check_operation("read", Path("/project/main/main.c"))
        True
        >>> whitelist.check_operation("write", Path("/etc/passwd"))
        False
    """

    # Default allowed paths for ESP-IDF projects
    DEFAULT_PATH_RULES = [
        PathRule(
            path_pattern="{project_root}/build",
            allowed_operations=["read", "write", "delete"],
            description="Build output directory",
        ),
        PathRule(
            path_pattern="{project_root}/main",
            allowed_operations=["read", "write"],
            description="Main application code",
        ),
        PathRule(
            path_pattern="{project_root}/components",
            allowed_operations=["read", "write"],
            description="Custom components",
        ),
        PathRule(
            path_pattern="{project_root}/CMakeLists.txt",
            allowed_operations=["read"],
            description="Project CMake configuration",
        ),
        PathRule(
            path_pattern="{project_root}/sdkconfig",
            allowed_operations=["read", "write"],
            description="Project configuration",
        ),
        PathRule(
            path_pattern="{project_root}/.espidf-mcp",
            allowed_operations=["read", "write", "delete"],
            description="MCP server state directory",
        ),
    ]

    def __init__(
        self, project_root: Path, path_rules: list[PathRule] | None = None, strict_mode: bool = True
    ):
        """Initialize operation whitelist.

        Args:
            project_root: Root directory of the ESP-IDF project
            path_rules: Custom path rules (uses DEFAULT if None)
            strict_mode: Whether to enforce strict checking
        """
        self.project_root = Path(project_root).resolve()
        self.path_rules = path_rules or self.DEFAULT_PATH_RULES.copy()
        self.strict_mode = strict_mode

    def check_operation(
        self, operation: Literal["read", "write", "delete", "execute"], path: Path
    ) -> bool:
        """Check if an operation is allowed on a path.

        Args:
            operation: Type of operation to check
            path: Path to check

        Returns:
            True if operation is allowed, False otherwise
        """
        try:
            resolved_path = path.resolve()

            # Check if path is within allowed paths
            for rule in self.path_rules:
                # Expand variables in pattern
                expanded_pattern = rule.path_pattern.format(project_root=str(self.project_root))
                rule_path = Path(expanded_pattern).resolve()

                # Check if path is within rule path
                try:
                    resolved_path.relative_to(rule_path)
                    # Path is within this rule, check operation
                    return operation in rule.allowed_operations
                except ValueError:
                    # Path is not within this rule
                    continue

            # If not in any allowed path, check strict mode
            if self.strict_mode:
                return False

            # In non-strict mode, allow paths within project root
            try:
                resolved_path.relative_to(self.project_root)
                return True
            except ValueError:
                return False

        except (OSError, ValueError):
            # Invalid path, deny by default
            return False

    def get_allowed_paths_summary(self) -> str:
        """Get a summary of allowed paths.

        Returns:
            Formatted string describing allowed paths
        """
        lines = ["Operation Whitelist - Allowed Paths:"]
        for rule in self.path_rules:
            expanded = rule.path_pattern.format(project_root=str(self.project_root))
            ops = ", ".join(rule.allowed_operations)
            lines.append(f"  {expanded}")
            lines.append(f"    Operations: {ops}")
            lines.append(f"    Description: {rule.description}")
        return "\n".join(lines)


# Global whitelist instance (initialized when project is loaded)
_whitelist: OperationWhitelist | None = None


def get_whitelist() -> OperationWhitelist | None:
    """Get the global operation whitelist instance.

    Returns:
        OperationWhitelist instance or None if not initialized
    """
    return _whitelist


def set_whitelist(whitelist: OperationWhitelist) -> None:
    """Set the global operation whitelist instance.

    Args:
        whitelist: OperationWhitelist instance to set
    """
    global _whitelist
    _whitelist = whitelist
