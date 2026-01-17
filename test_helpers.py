"""Test helper functions and decorators for ESP-IDF MCP Server tests."""

from functools import wraps

import pytest

from mcp_tools.exceptions import PrerequisiteError


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


__all__ = ["skip_on_known_errors"]
