"""
End-to-end tests for ESP-IDF MCP Server (HTTP Mode)

These tests verify the MCP server functionality by connecting to an
already running server and making actual HTTP POST requests with MCP
JSON-RPC messages.

Prerequisites:
- ESP-IDF MCP server must be running on http://127.0.0.1:8090
- Start with: espidf-mcp --http --port 8090 --host 127.0.0.1
"""

from pathlib import Path
from typing import Any

import httpx
import pytest

# ============================================================================
# Configuration
# ============================================================================

TEST_PROJECT_DIR = Path("/data/esp32_test/hello_world")
SERVER_URL = "http://127.0.0.1:8090"
REQUEST_TIMEOUT = 300.0

# ============================================================================
# MCP HTTP Client Helper
# ============================================================================


class MCPHttpClient:
    """
    HTTP client for MCP JSON-RPC protocol over HTTP.
    """

    def __init__(self, base_url: str = SERVER_URL, timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
        self._request_id = 0

    def _next_id(self) -> int:
        """Generate next JSON-RPC request ID"""
        self._request_id += 1
        return self._request_id

    def _make_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make MCP JSON-RPC request over HTTP"""
        request_id = self._next_id()

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params:
            payload["params"] = params

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        response = self.client.post(f"{self.base_url}/mcp", json=payload, headers=headers)
        response.raise_for_status()

        # Parse SSE (Server-Sent Events) format
        # Format: event: message\r\ndata: {...}\r\n\r\n
        content = response.text
        for line in content.split("\n"):
            if line.startswith("data: "):
                json_data = line[6:]  # Remove "data: " prefix
                import json

                return json.loads(json_data)

        raise ValueError(f"No data found in SSE response: {content[:200]}")

    def list_tools(self) -> list[dict[str, Any]]:
        """List available MCP tools"""
        response = self._make_request("tools/list")
        return response.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Call an MCP tool"""
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments

        response = self._make_request("tools/call", params=params)

        # Extract text content from response
        result = response.get("result", {})
        content = result.get("content", [])

        if content and isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    return item.get("text", "")

        return ""

    def close(self):
        """Close HTTP client"""
        self.client.close()


# ============================================================================
# Pytest Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def mcp_client():
    """Fixture that provides an MCP HTTP client connected to running server"""
    client = MCPHttpClient(
        base_url=SERVER_URL,
        timeout=REQUEST_TIMEOUT,
    )

    try:
        yield client
    finally:
        client.close()


# ============================================================================
# Test Cases
# ============================================================================


class TestMCPBasics:
    """Test basic MCP protocol functionality"""

    def test_server_starts_and_responds(self, mcp_client: MCPHttpClient):
        """Test that server responds to basic request"""
        response = mcp_client._make_request("tools/list")
        assert response.get("jsonrpc") == "2.0"
        assert "result" in response

    def test_list_tools(self, mcp_client: MCPHttpClient):
        """Test that server lists all available tools"""
        tools = mcp_client.list_tools()
        tool_names = {tool["name"] for tool in tools}

        expected_tools = {
            "esp_project_info",
            "esp_build",
            "esp_flash",
            "esp_monitor",
            "esp_list_ports",
            "esp_clean",
            "esp_fullclean",
            "esp_size",
            "esp_set_target",
        }

        assert expected_tools.issubset(tool_names)


class TestProjectInfo:
    """Test esp_project_info tool"""

    def test_project_info_returns_valid_data(self, mcp_client: MCPHttpClient):
        """Test that project_info tool returns valid information"""
        result = mcp_client.call_tool("esp_project_info")

        assert "hello_world" in result
        assert "CMakeLists.txt" in result


class TestListPorts:
    """Test esp_list_ports tool"""

    def test_list_ports_executes(self, mcp_client: MCPHttpClient):
        """Test that list_ports tool executes without error"""
        result = mcp_client.call_tool("esp_list_ports")

        assert isinstance(result, str)
        assert len(result) > 0


class TestClean:
    """Test esp_clean tool"""

    def test_clean_executes(self, mcp_client: MCPHttpClient):
        """Test that clean tool executes successfully"""
        result = mcp_client.call_tool("esp_clean")

        assert isinstance(result, str)
        assert "clean" in result.lower() or "清理" in result.lower()


class TestSize:
    """Test esp_size tool"""

    def test_size_analyzes_firmware(self, mcp_client: MCPHttpClient):
        """Test that size tool analyzes firmware"""
        result = mcp_client.call_tool("esp_size")

        assert isinstance(result, str)
        assert len(result) > 0


class TestBuild:
    """Test esp_build tool (long-running operation)"""

    @pytest.mark.slow
    def test_build_compiles_firmware(self, mcp_client: MCPHttpClient):
        """Test that build tool compiles firmware"""
        result = mcp_client.call_tool("esp_build")

        assert isinstance(result, str)
        assert len(result) > 0
        assert "构建" in result or "build" in result.lower()


class TestWorkflowIntegration:
    """Test common workflows using multiple tools"""

    @pytest.mark.slow
    def test_clean_build_workflow(self, mcp_client: MCPHttpClient):
        """Test clean -> build workflow"""
        clean_result = mcp_client.call_tool("esp_clean")
        assert "clean" in clean_result.lower() or "清理" in clean_result.lower()

        build_result = mcp_client.call_tool("esp_build")
        assert "构建" in build_result or "build" in build_result.lower()
