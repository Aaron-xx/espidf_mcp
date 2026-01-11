"""
Pytest configuration for ESP-IDF MCP Server tests.

This file provides shared configuration and fixtures for all test modules.
"""


def pytest_configure(config):
    """
    Configure custom pytest markers.

    This function is called by pytest at the start of the test session
    to register custom markers used in the test suite.
    """
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )


__all__ = ["pytest_configure"]
