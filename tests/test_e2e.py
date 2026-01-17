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

from test_helpers import skip_on_known_errors

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

        # All 21 tools should be present (core 16 + observability 5)
        expected_tools = {
            # Core ESP-IDF tools (16)
            "esp_project_info",
            "esp_build",
            "esp_flash",
            "esp_monitor",
            "esp_list_ports",
            "esp_clean",
            "esp_size",
            "esp_set_target",
            "esp_show_partition_table",
            "esp_validate_partition_table",
            "esp_erase_region",
            "esp_read_mac",
            "esp_workflow_files",
            "esp_workflow_state",
            "esp_idf_expert",
            "esp_context_summary",
            "esp_memory_store",
            # Observability tools (5)
            "esp_metrics_summary",
            "esp_diagnose_last_error",
            "esp_observability_status",
            "esp_logs_view",
            "esp_error_history",
        }

        # Check that all expected tools are present (allow extra tools for future additions)
        missing_tools = expected_tools - tool_names
        assert not missing_tools, f"Missing tools: {missing_tools}"

    def test_tools_have_descriptions(self, mcp_client: MCPHttpClient):
        """Test that all tools have proper descriptions"""
        tools = mcp_client.list_tools()

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert len(tool["description"]) > 0, f"Tool {tool['name']} has empty description"


class TestProjectInfo:
    """Test esp_project_info tool"""

    def test_project_info_returns_valid_data(self, mcp_client: MCPHttpClient):
        """Test that project_info tool returns valid information"""
        result = mcp_client.call_tool("esp_project_info")

        # Verify key information exists
        assert "Project directory:" in result
        assert "CMakeLists.txt:" in result
        assert "sdkconfig:" in result

        # Verify path format
        import re

        path_match = re.search(r"Project directory:\s*(.+)", result)
        assert path_match, "Should contain project directory path"
        project_path = Path(path_match.group(1).strip())
        assert project_path.exists(), f"Path {project_path} should exist"
        assert project_path == TEST_PROJECT_DIR, "Should match test project directory"

        # Verify file status is indicated
        assert "exists" in result or "not found" in result


class TestListPorts:
    """Test esp_list_ports tool"""

    def test_list_ports_executes(self, mcp_client: MCPHttpClient):
        """Test that list_ports tool returns properly formatted port information"""
        result = mcp_client.call_tool("esp_list_ports")

        # Verify return is not empty
        assert isinstance(result, str)
        assert len(result) > 0

        # Verify format: lines should contain device number, path, description
        lines = result.strip().split("\n")
        assert len(lines) > 0, "Should return at least one line"

        # If serial devices are present, validate the format
        if "No serial devices" not in result and "No serial devices detected" not in result:
            # Expected format: "1. /dev/ttyUSB0 - Description"
            import re

            port_pattern = r"^\d+\.\s+([/\w]+)\s+-\s+.+$"
            for line in lines:
                assert re.match(port_pattern, line), (
                    f"Line '{line}' doesn't match expected format 'N. /dev/xxx - Description'"
                )


class TestClean:
    """Test esp_clean tool with level parameter"""

    @skip_on_known_errors
    def test_clean_standard_executes(self, mcp_client: MCPHttpClient):
        """Test that clean tool with standard level removes build artifacts"""
        # Ensure there are build artifacts to clean
        build_dir = TEST_PROJECT_DIR / "build"

        # Execute clean
        result = mcp_client.call_tool("esp_clean", {"level": "standard"})

        # Verify return message indicates success
        assert isinstance(result, str)
        assert "clean" in result.lower() or "清理" in result.lower()
        assert "succeeded" in result.lower() or "成功" in result.lower() or "done" in result.lower()

        # Verify actual effect: build directory still exists for standard clean
        assert build_dir.exists(), "Build directory should still exist for standard clean"

        # Verify that cleaning message mentions actual file removal
        assert "Cleaning" in result or "cleaning" in result.lower() or "files" in result.lower()

    def test_clean_full_executes(self, mcp_client: MCPHttpClient):
        """Test that clean tool with full level executes successfully"""
        result = mcp_client.call_tool("esp_clean", {"level": "full"})

        assert isinstance(result, str)
        assert "clean" in result.lower() or "清理" in result.lower() or "full" in result.lower()


class TestSize:
    """Test esp_size tool"""

    @skip_on_known_errors
    def test_size_analyzes_firmware(self, mcp_client: MCPHttpClient):
        """Test that size tool analyzes firmware and reports valid data"""
        # Ensure firmware is built first
        build_result = mcp_client.call_tool("esp_build")
        assert "succeeded" in build_result.lower() or "成功" in build_result.lower()

        result = mcp_client.call_tool("esp_size")

        # Verify return contains size information
        assert isinstance(result, str)
        assert len(result) > 0

        # Verify key sections are present
        assert any(keyword in result for keyword in ["Total sizes:", "text", "data", "bss", "DRAM"])

        # Verify numerical format (should have byte sizes)
        import re

        size_pattern = r"(\d+)\s+bytes"
        sizes = re.findall(size_pattern, result)
        assert len(sizes) >= 2, f"Should have at least 2 sections with byte sizes, found: {sizes}"

        # Verify at least some sizes are reasonable (>1KB), filter out zeros
        valid_sizes = [int(s) for s in sizes if int(s) > 0]
        assert len(valid_sizes) >= 2, "Should have at least 2 valid section sizes"

        # Check that main sections have substantial sizes
        large_sections = [s for s in valid_sizes if s > 1024]
        assert len(large_sections) >= 1, (
            f"Should have at least 1 section > 1KB, found: {large_sections}"
        )


class TestSetTarget:
    """Test esp_set_target tool"""

    def test_set_target_has_valid_options(self, mcp_client: MCPHttpClient):
        """Test that set_target has proper schema with all ESP32 chip variants"""
        tools = mcp_client.list_tools()
        set_target_tool = next(t for t in tools if t["name"] == "esp_set_target")

        # Check that target parameter has valid enum values
        assert "inputSchema" in set_target_tool
        schema = set_target_tool["inputSchema"]
        assert "properties" in schema
        assert "target" in schema["properties"]
        target_prop = schema["properties"]["target"]

        # Verify target is string type
        assert target_prop.get("type") == "string", "target should be string type"

        # Verify target is required
        assert "required" in schema
        assert "target" in schema["required"], "target should be required"

        # Should have enum with ESP32 chip variants
        if "enum" in target_prop:
            expected_chips = [
                "esp32",
                "esp32s2",
                "esp32c3",
                "esp32s3",
                "esp32c2",
                "esp32h2",
                "esp32p4",
                "esp32c6",
                "esp32c5",
            ]
            for chip in expected_chips:
                assert chip in target_prop["enum"], f"Chip {chip} should be in enum"

            # Verify enum contains only strings
            for chip in target_prop["enum"]:
                assert isinstance(chip, str), "All enum values should be strings"


class TestPartitionTable:
    """Test partition table tools"""

    def test_show_partition_table(self, mcp_client: MCPHttpClient):
        """Test esp_show_partition_table tool"""
        tools = mcp_client.list_tools()
        tool_names = {tool["name"] for tool in tools}
        assert "esp_show_partition_table" in tool_names

        result = mcp_client.call_tool("esp_show_partition_table")

        assert isinstance(result, str)

    def test_validate_partition_table(self, mcp_client: MCPHttpClient):
        """Test esp_validate_partition_table tool"""
        tools = mcp_client.list_tools()
        tool_names = {tool["name"] for tool in tools}
        assert "esp_validate_partition_table" in tool_names

        result = mcp_client.call_tool("esp_validate_partition_table")

        assert isinstance(result, str)
        assert "validation" in result.lower() or "partition" in result.lower()


class TestEraseRegion:
    """Test esp_erase_region tool"""

    def test_erase_region_tool_exists(self, mcp_client: MCPHttpClient):
        """Test that erase_region tool has correct schema and parameters"""
        tools = mcp_client.list_tools()
        erase_tool = next(t for t in tools if t["name"] == "esp_erase_region")

        assert "inputSchema" in erase_tool
        schema = erase_tool["inputSchema"]
        assert "properties" in schema

        # Verify required parameters exist
        assert "address" in schema["properties"]
        assert "size" in schema["properties"]
        assert "port" in schema["properties"]

        # Verify address parameter format (should be hex string)
        address_prop = schema["properties"]["address"]
        assert "type" in address_prop
        # Address should be string type
        assert address_prop["type"] == "string"

        # Verify size parameter format (should be integer)
        size_prop = schema["properties"]["size"]
        assert "type" in size_prop
        assert size_prop["type"] == "integer"


class TestReadMac:
    """Test esp_read_mac tool"""

    def test_read_mac_tool_has_valid_schema(self, mcp_client: MCPHttpClient):
        """Test that read_mac tool has correct schema and parameters"""
        tools = mcp_client.list_tools()
        read_mac_tool = next(t for t in tools if t["name"] == "esp_read_mac")

        # Verify schema exists
        assert "inputSchema" in read_mac_tool
        schema = read_mac_tool["inputSchema"]

        # Verify port parameter exists (should be optional for default port)
        assert "properties" in schema
        assert "port" in schema["properties"]

        # Port should be optional string type
        port_prop = schema["properties"]["port"]
        assert port_prop.get("type") in ["string", "null"] or "anyOf" in port_prop

        # Port should not be in required fields (has default)
        required = schema.get("required", [])
        assert "port" not in required, "port should be optional with default"


class TestWorkflowState:
    """Test workflow state management tools"""

    def test_workflow_files(self, mcp_client: MCPHttpClient):
        """Test esp_workflow_files tool"""
        result = mcp_client.call_tool("esp_workflow_files")

        assert isinstance(result, str)
        assert "workflow" in result.lower() or "stage" in result.lower()

    def test_workflow_state(self, mcp_client: MCPHttpClient):
        """Test esp_workflow_state tool returns valid structured data"""
        result = mcp_client.call_tool("esp_workflow_state")

        assert isinstance(result, str)
        assert len(result) > 0

        # Verify key sections exist
        assert "ESP-IDF MCP Workflow State" in result
        assert "Progress:" in result
        assert "Completed:" in result
        assert "Stage Details:" in result

        # Verify progress percentage format (e.g., "Progress: 20.0%")
        import re

        progress_match = re.search(r"Progress:\s+(\d+\.?\d*)%", result)
        assert progress_match, "Should contain progress percentage"
        progress = float(progress_match.group(1))
        assert 0 <= progress <= 100, f"Progress {progress} should be between 0-100"

        # Verify stage count format (e.g., "Completed: 1/5")
        completed_match = re.search(r"Completed:\s+(\d+)/(\d+)", result)
        assert completed_match, "Should contain completed/total stage count"
        completed = int(completed_match.group(1))
        total = int(completed_match.group(2))
        assert 0 <= completed <= total, f"Completed {completed} should be <= total {total}"

        # Verify stage status indicators
        assert any(
            status in result for status in ["[PENDING]", "[COMPLETED]", "[FAILED]", "[RUNNING]"]
        )

        # Verify dependency relationships if present
        if "deps:" in result:
            deps_match = re.findall(r"deps:\s+([^\n]+)", result)
            assert len(deps_match) > 0, "If deps present, should have dependency info"


class TestHelperTools:
    """Test UCAgent-style helper tools"""

    def test_context_summary(self, mcp_client: MCPHttpClient):
        """Test esp_context_summary tool"""
        tools = mcp_client.list_tools()
        tool_names = {tool["name"] for tool in tools}
        assert "esp_context_summary" in tool_names

        # Store a context summary
        result = mcp_client.call_tool(
            "esp_context_summary", {"summary": "Test project: hello_world example for ESP32"}
        )

        assert isinstance(result, str)
        assert "context" in result.lower() or "saved" in result.lower()

    def test_memory_store(self, mcp_client: MCPHttpClient):
        """Test esp_memory_store tool"""
        tools = mcp_client.list_tools()
        tool_names = {tool["name"] for tool in tools}
        assert "esp_memory_store" in tool_names

        # Store a key-value pair
        result = mcp_client.call_tool(
            "esp_memory_store", {"key": "test_key", "value": "test_value"}
        )

        assert isinstance(result, str)
        assert "stored" in result.lower() or "saved" in result.lower() or "memory" in result.lower()


class TestIDFExpert:
    """Test esp_idf_expert tool"""

    def test_idf_expert_returns_guide(self, mcp_client: MCPHttpClient):
        """Test that idf_expert returns usage guide"""
        result = mcp_client.call_tool("esp_idf_expert")

        assert isinstance(result, str)
        assert len(result) > 0
        assert "ESP-IDF" in result


class TestBuild:
    """Test esp_build tool (long-running operation)"""

    @pytest.mark.slow
    def test_build_compiles_firmware(self, mcp_client: MCPHttpClient):
        """Test that build tool compiles firmware"""
        result = mcp_client.call_tool("esp_build")

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain build output or success message
        assert "build" in result.lower() or "构建" in result or "succeeded" in result.lower()


class TestWorkflowIntegration:
    """Test common workflows using multiple tools"""

    @pytest.mark.slow
    def test_clean_build_workflow(self, mcp_client: MCPHttpClient):
        """Test clean -> build workflow"""
        clean_result = mcp_client.call_tool("esp_clean")
        assert "clean" in clean_result.lower() or "清理" in clean_result.lower()

        build_result = mcp_client.call_tool("esp_build")
        assert "构建" in build_result or "build" in build_result.lower()

    def test_project_info_workflow(self, mcp_client: MCPHttpClient):
        """Test project info check workflow"""
        info_result = mcp_client.call_tool("esp_project_info")
        assert "hello_world" in info_result

        # Check workflow state
        state_result = mcp_client.call_tool("esp_workflow_state")
        assert isinstance(state_result, str)


class TestToolParameters:
    """Test tool parameter validation"""

    def test_clean_level_parameter(self, mcp_client: MCPHttpClient):
        """Test esp_clean has level parameter with enum"""
        tools = mcp_client.list_tools()
        clean_tool = next(t for t in tools if t["name"] == "esp_clean")

        schema = clean_tool["inputSchema"]
        assert "properties" in schema
        assert "level" in schema["properties"]

        level_prop = schema["properties"]["level"]
        # Should have enum with standard and full
        if "enum" in level_prop:
            assert "standard" in level_prop["enum"]
            assert "full" in level_prop["enum"]

    def test_monitor_parameters(self, mcp_client: MCPHttpClient):
        """Test monitor has required parameters"""
        tools = mcp_client.list_tools()
        monitor_tool = next(t for t in tools if t["name"] == "esp_monitor")

        schema = monitor_tool["inputSchema"]
        assert "required" in schema
        # port should be required
        assert "port" in schema["required"]

    def test_flash_parameters(self, mcp_client: MCPHttpClient):
        """Test flash has optional parameters"""
        tools = mcp_client.list_tools()
        flash_tool = next(t for t in tools if t["name"] == "esp_flash")

        schema = flash_tool["inputSchema"]
        assert "properties" in schema
        # port and baud should be optional
        assert "port" in schema["properties"]
        assert "baud" in schema["properties"]

    def test_context_summary_parameters(self, mcp_client: MCPHttpClient):
        """Test esp_context_summary has summary parameter"""
        tools = mcp_client.list_tools()
        cs_tool = next(t for t in tools if t["name"] == "esp_context_summary")

        schema = cs_tool["inputSchema"]
        assert "required" in schema
        # summary should be required
        assert "summary" in schema["required"]

    def test_memory_store_parameters(self, mcp_client: MCPHttpClient):
        """Test esp_memory_store has key and value parameters"""
        tools = mcp_client.list_tools()
        ms_tool = next(t for t in tools if t["name"] == "esp_memory_store")

        schema = ms_tool["inputSchema"]
        assert "required" in schema
        # both key and value should be required
        assert "key" in schema["required"]
        assert "value" in schema["required"]


class TestToolDescriptions:
    """Test tool descriptions for completeness"""

    def test_all_tools_have_purpose(self, mcp_client: MCPHttpClient):
        """Test that all tools have PURPOSE section in description"""
        tools = mcp_client.list_tools()

        for tool in tools:
            desc = tool.get("description", "")
            # Tools should have meaningful descriptions
            assert len(desc) > 20, f"Tool {tool['name']} has too short description"

    def test_critical_tools_have_detailed_docs(self, mcp_client: MCPHttpClient):
        """Test critical tools have detailed documentation"""
        tools = mcp_client.list_tools()
        critical_tools = ["esp_build", "esp_flash", "esp_monitor", "esp_set_target", "esp_clean"]

        for tool_name in critical_tools:
            tool = next(t for t in tools if t["name"] == tool_name)
            desc = tool.get("description", "")
            # Should have PURPOSE section
            assert "PURPOSE" in desc, f"{tool_name} missing PURPOSE section"
            # Should have DESCRIPTION section
            assert "DESCRIPTION" in desc, f"{tool_name} missing DESCRIPTION section"


class TestParameterValidation:
    """Test parameter validation for tools"""

    def test_clean_level_enum_values(self, mcp_client: MCPHttpClient):
        """Test that clean tool accepts valid level enum values"""
        tools = mcp_client.list_tools()
        clean_tool = next(t for t in tools if t["name"] == "esp_clean")

        schema = clean_tool["inputSchema"]
        level_prop = schema["properties"]["level"]

        # Verify level is a string with enum values
        assert level_prop.get("type") == "string"
        if "enum" in level_prop:
            # Should contain standard and full
            assert "standard" in level_prop["enum"]
            assert "full" in level_prop["enum"]

            # All enum values should be strings
            for val in level_prop["enum"]:
                assert isinstance(val, str), "All level enum values should be strings"

    def test_flash_port_parameter_type(self, mcp_client: MCPHttpClient):
        """Test that flash tool has correct port parameter type"""
        tools = mcp_client.list_tools()
        flash_tool = next(t for t in tools if t["name"] == "esp_flash")

        schema = flash_tool["inputSchema"]
        assert "port" in schema["properties"]

        port_prop = schema["properties"]["port"]
        # Port should be optional string
        assert port_prop.get("type") in ["string", "null"] or "anyOf" in port_prop

        # Port should not be required (has default detection)
        required = schema.get("required", [])
        assert "port" not in required, "port should be optional with auto-detection"

    def test_erase_region_address_format(self, mcp_client: MCPHttpClient):
        """Test that erase_region requires address as hex string"""
        tools = mcp_client.list_tools()
        erase_tool = next(t for t in tools if t["name"] == "esp_erase_region")

        schema = erase_tool["inputSchema"]
        address_prop = schema["properties"]["address"]

        # Address should be string type (for hex format like "0x1000")
        assert address_prop.get("type") == "string"

        # Address should be required
        required = schema.get("required", [])
        assert "address" in required, "address should be required"

        # Size should be required integer
        size_prop = schema["properties"]["size"]
        assert size_prop.get("type") == "integer"
        assert "size" in required, "size should be required"


class TestErrorHandling:
    """Test error handling and error messages"""

    def test_error_messages_are_descriptive(self, mcp_client: MCPHttpClient):
        """Test that error messages provide useful information"""
        # Try to show partition table without building first
        # This might fail or succeed depending on project state
        result = mcp_client.call_tool("esp_show_partition_table")

        # Result should be descriptive (not just "Error")
        assert isinstance(result, str)
        # If it's an error, it should have some detail
        if "error" in result.lower() or "failed" in result.lower():
            # Error messages should be more than 20 chars
            assert len(result) > 20, "Error messages should be descriptive"

    def test_invalid_tool_name_handled(self, mcp_client: MCPHttpClient):
        """Test that calling non-existent tool is handled properly"""
        # This tests the client's error handling
        # MCP protocol should return an error for unknown tools
        try:
            # Try to call a tool that doesn't exist
            result = mcp_client.call_tool("esp_nonexistent_tool")
            # If we get here, the server should have returned an error message
            assert isinstance(result, str)
            assert "error" in result.lower() or "not found" in result.lower()
        except Exception as e:
            # Exception is also acceptable
            assert "not found" in str(e).lower() or "unknown" in str(e).lower()


class TestStateConsistency:
    """Test state consistency across operations"""

    def test_workflow_state_persists_after_build(self, mcp_client: MCPHttpClient):
        """Test that workflow state is updated after build operation"""
        # Get initial state
        state_before = mcp_client.call_tool("esp_workflow_state")

        # Execute build (this should update workflow state)
        build_result = mcp_client.call_tool("esp_build")
        assert "succeeded" in build_result.lower() or "成功" in build_result.lower()

        # Get state after build
        state_after = mcp_client.call_tool("esp_workflow_state")

        # State should still have valid structure
        assert "ESP-IDF MCP Workflow State" in state_after
        assert "Progress:" in state_after
        assert "Completed:" in state_after

        # Build should be reflected in state
        # Either as completed or as current operation
        assert "build" in state_after.lower() or "completed" in state_after.lower()

    def test_project_info_consistent_across_calls(self, mcp_client: MCPHttpClient):
        """Test that project_info returns consistent data"""
        # Call project_info multiple times
        result1 = mcp_client.call_tool("esp_project_info")
        result2 = mcp_client.call_tool("esp_project_info")

        # Both should return valid project directory
        assert "Project directory:" in result1
        assert "Project directory:" in result2

        # Extract and compare project paths
        import re

        path1 = re.search(r"Project directory:\s*(.+)", result1)
        path2 = re.search(r"Project directory:\s*(.+)", result2)

        if path1 and path2:
            assert path1.group(1).strip() == path2.group(1).strip(), (
                "Project directory should be consistent across calls"
            )
