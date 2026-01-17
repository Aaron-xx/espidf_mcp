"""
Pytest configuration for ESP-IDF MCP Server tests.

This file provides shared configuration and fixtures for all test modules.
"""

import re
from functools import wraps
from pathlib import Path
from typing import Any

import pytest

from mcp_tools.exceptions import PrerequisiteError

# ============================================================================
# Custom Test Decorators
# ============================================================================


def skip_on_known_errors(test_func):
    """捕获 PrerequisiteError 并跳过测试（显式，可控）。

    只有加了这个装饰器的测试，遇到 PrerequisiteError 时才会 SKIP。
    真正的 bug 仍然会 FAIL，保持测试发现问题能力。

    Args:
        test_func: The test function to decorate.

    Example:
        >>> @skip_on_known_errors
        ... def test_size_analyzes_firmware(mcp_client):
        ...     result = mcp_client.call_tool("esp_size")
    """

    @wraps(test_func)
    def wrapper(*args, **kwargs):
        try:
            return test_func(*args, **kwargs)
        except PrerequisiteError as e:
            fix_cmd = getattr(e, "fix_command", "N/A")
            pytest.skip(f"Known prerequisite error: {e.message}\n\nFix: {fix_cmd}")

    return wrapper


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """
    Configure custom pytest markers.

    This function is called by pytest at the start of the test session
    to register custom markers used in the test suite.
    """
    markers = [
        ("slow", "marks tests as slow (deselect with '-m \"not slow\"')"),
        ("integration", "marks tests as integration tests (require server)"),
        ("hardware", "marks tests that require real hardware"),
        ("flash", "marks tests that flash firmware (destructive)"),
        ("espidf", "marks tests that require ESP-IDF environment and idf.py"),
    ]
    for marker, description in markers:
        config.addinivalue_line("markers", f"{marker}: {description}")


__all__ = [
    "pytest_configure",
    "skip_on_known_errors",
    "parse_size_output",
    "verify_firmware_artifacts",
    "validate_project_info_output",
    "extract_tool_name",
]


# ============================================================================
# Test Helper Functions
# ============================================================================


def parse_size_output(output: str) -> dict[str, int]:
    """Parse size tool output and extract section sizes.

    Args:
        output: Raw output string from esp_size tool.

    Returns:
        Dict mapping section names to sizes in bytes.
        Example: {"text": 150000, "data": 5000, "bss": 10000}

    Example:
        >>> result = parse_size_output("text: 150000 bytes\\ndata: 5000 bytes")
        >>> assert result["text"] == 150000
    """
    sizes = {}
    for line in output.split("\n"):
        # Match patterns like:
        # - "text: 150000 bytes"
        # - "text   150000     5000"
        # - "Total sizes: 200000"
        match = re.match(r"\s*(\w+):\s+(\d+)", line)
        if match:
            section, size = match.groups()
            try:
                sizes[section] = int(size)
            except ValueError:
                continue

        # Also look for "XXXX bytes" pattern
        match2 = re.search(r"(\w+)\s+(\d+)\s+bytes", line)
        if match2:
            section, size = match2.groups()
            try:
                sizes[section] = int(size)
            except ValueError:
                continue

    return sizes


def verify_firmware_artifacts(
    build_dir: Path, required_patterns: list[tuple[str, str]] | None = None
) -> dict[str, list[str]]:
    """Verify that expected firmware artifacts exist in build directory.

    Args:
        build_dir: Path to build directory.
        required_patterns: List of (pattern, description) tuples.
            Defaults to standard ESP-IDF artifacts.

    Returns:
        Dict mapping descriptions to lists of found file paths.
        Example: {
            "Firmware binaries": ["build/app.bin"],
            "ELF executable": ["build/app.elf"]
        }

    Example:
        >>> artifacts = verify_firmware_artifacts(Path("/project/build"))
        >>> assert len(artifacts["Firmware binaries"]) > 0
    """
    if required_patterns is None:
        required_patterns = [
            ("*.bin", "Firmware binaries"),
            ("*.elf", "ELF executable"),
            ("build.ninja", "Ninja build file"),
        ]

    found_artifacts: dict[str, list[str]] = {}

    for pattern, description in required_patterns:
        files = [str(f.relative_to(build_dir)) for f in build_dir.glob(pattern)]
        found_artifacts[description] = files

    return found_artifacts


def validate_project_info_output(output: str, expected_dir: Path) -> list[str]:
    """Validate project_info tool output and return any errors.

    Args:
        output: Raw output string from esp_project_info tool.
        expected_dir: Expected project directory path.

    Returns:
        List of validation error messages. Empty list means valid output.

    Example:
        >>> errors = validate_project_info_output(result, Path("/project"))
        >>> if errors:
        ...     print(f"Validation failed: {errors}")
    """
    errors = []

    # Check for required sections
    if "Project directory:" not in output:
        errors.append("Missing project directory")

    if "CMakeLists.txt:" not in output:
        errors.append("Missing CMakeLists.txt status")

    if "sdkconfig:" not in output:
        errors.append("Missing sdkconfig status")

    # Validate project directory path
    path_match = re.search(r"Project directory:\s*(.+)", output)
    if not path_match:
        errors.append("Cannot parse project directory path")
    else:
        path_str = path_match.group(1).strip()
        try:
            actual_path = Path(path_str)
            if actual_path != expected_dir:
                errors.append(f"Path mismatch: expected {expected_dir}, got {actual_path}")
            if not actual_path.exists():
                errors.append(f"Project path does not exist: {actual_path}")
        except Exception as e:
            errors.append(f"Invalid path format: {e}")

    return errors


def extract_tool_name(result: str) -> str | None:
    """Extract tool name from result string or log message.

    Args:
        result: Result string from tool call or log message.

    Returns:
        Tool name if found, None otherwise.

    Example:
        >>> log = "Tool SUCCESS: esp_build (0.98s)"
        >>> name = extract_tool_name(log)
        >>> assert name == "esp_build"
    """
    # Match patterns like:
    # - "Tool SUCCESS: esp_build (0.98s)"
    # - "Tool FAILED: esp_flash"
    # - "Executing esp_size..."
    patterns = [
        r"Tool (?:SUCCESS|FAILED): (\w+)",
        r"Executing (\w+)\.\.\.",
        r"Calling (\w+) with",
    ]

    for pattern in patterns:
        match = re.search(pattern, result)
        if match:
            return match.group(1)

    return None


def parse_workflow_state(output: str) -> dict[str, Any]:
    """Parse workflow state output into structured data.

    Args:
        output: Raw output string from esp_workflow_state tool.

    Returns:
        Dict with parsed workflow state information.
        Example: {
            "progress_percent": 20.0,
            "completed": 1,
            "total": 5,
            "current": None,
            "stages": [...]
        }

    Example:
        >>> state = parse_workflow_state(output)
        >>> assert 0 <= state["progress_percent"] <= 100
    """
    state: dict[str, Any] = {
        "progress_percent": 0.0,
        "completed": 0,
        "total": 0,
        "current": None,
        "stages": [],
    }

    # Parse progress percentage
    progress_match = re.search(r"Progress:\s+(\d+\.?\d*)%", output)
    if progress_match:
        state["progress_percent"] = float(progress_match.group(1))

    # Parse completed/total counts
    completed_match = re.search(r"Completed:\s+(\d+)/(\d+)", output)
    if completed_match:
        state["completed"] = int(completed_match.group(1))
        state["total"] = int(completed_match.group(2))

    # Parse current stage
    current_match = re.search(r"Current:\s+(\w+)", output)
    if current_match:
        state["current"] = current_match.group(1)

    # Parse stage details
    stage_pattern = r"\[(\w+)\]\s+(\w+)"
    for match in re.finditer(stage_pattern, output):
        status, stage_name = match.groups()
        state["stages"].append(
            {
                "name": stage_name,
                "status": status,
            }
        )

    return state
