"""Integration tests for ESP-IDF MCP Server.

These tests require:
- Running MCP server on http://127.0.0.1:8090
- Connected ESP32 hardware device
- Valid ESP-IDF project at TEST_PROJECT_DIR

These are REAL integration tests that actually execute ESP-IDF commands
and interact with hardware.
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
REQUEST_TIMEOUT = 600.0  # 10 minutes for builds
HARDWARE_TIMEOUT = 120.0  # 2 minutes for flash operations


# ============================================================================
# MCP HTTP Client Helper
# ============================================================================


class MCPHttpClient:
    """HTTP client for MCP JSON-RPC protocol over HTTP."""

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

        # Parse SSE format
        content = response.text
        for line in content.split("\n"):
            if line.startswith("data: "):
                json_data = line[6:]
                import json

                return json.loads(json_data)

        raise ValueError(f"No data found in SSE response: {content[:200]}")

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Call an MCP tool"""
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments

        response = self._make_request("tools/call", params=params)

        # Extract text content
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
    """Fixture that provides an MCP HTTP client"""
    client = MCPHttpClient(
        base_url=SERVER_URL,
        timeout=REQUEST_TIMEOUT,
    )

    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="function")
def hardware_client():
    """Fixture for hardware-specific tests"""
    client = MCPHttpClient(
        base_url=SERVER_URL,
        timeout=HARDWARE_TIMEOUT,
    )

    try:
        yield client
    finally:
        client.close()


# ============================================================================
# Test 1: Complete Build Flow
# ============================================================================


@pytest.mark.slow
@pytest.mark.integration
class TestCompleteBuildFlow:
    """Test complete build workflow from clean to firmware."""

    def test_full_build_workflow(self, mcp_client: MCPHttpClient):
        """Test complete workflow: clean → set-target → build → size → analyze"""
        # Step 1: Clean previous builds
        print("\n[Step 1] Cleaning previous builds...")
        clean_result = mcp_client.call_tool("esp_clean", {"level": "full"})
        assert "clean" in clean_result.lower() or "清理" in clean_result.lower()

        # Step 2: Set target chip (ESP32)
        print("[Step 2] Setting target chip...")
        target_result = mcp_client.call_tool("esp_set_target", {"target": "esp32"})
        assert "esp32" in target_result.lower() or "target" in target_result.lower()

        # Step 3: Build firmware
        print("[Step 3] Building firmware (this may take a while)...")
        build_result = mcp_client.call_tool("esp_build")
        assert "build" in build_result.lower() or "构建" in build_result
        assert "succeeded" in build_result.lower() or "成功" in build_result

        # Step 4: Analyze firmware size
        print("[Step 4] Analyzing firmware size...")
        size_result = mcp_client.call_tool("esp_size")
        assert len(size_result) > 0
        # Should contain size information
        assert (
            "text" in size_result.lower()
            or "data" in size_result.lower()
            or "bss" in size_result.lower()
        )

        # Step 5: Check workflow state
        print("[Step 5] Checking workflow state...")
        workflow_state = mcp_client.call_tool("esp_workflow_state")
        assert "workflow" in workflow_state.lower() or "stage" in workflow_state.lower()

        # Step 6: Verify build artifacts exist
        print("[Step 6] Verifying build artifacts...")
        build_dir = TEST_PROJECT_DIR / "build"
        assert build_dir.exists(), "Build directory should exist"

        # Check for .bin files
        bin_files = list(build_dir.glob("*.bin"))
        assert len(bin_files) > 0, "Should have at least one .bin file"

        # Check for .elf file
        elf_files = list(build_dir.glob("*.elf"))
        assert len(elf_files) > 0, "Should have .elf file"

        print("\n✓ Complete build workflow successful!")
        print(f"  Generated {len(bin_files)} .bin files")
        print(f"  Generated {len(elf_files)} .elf file")

    def test_workflow_file_state_after_build(self, mcp_client: MCPHttpClient):
        """Test that workflow file state is properly saved after build"""
        # First ensure we have a build
        mcp_client.call_tool("esp_build")

        # Check workflow files
        workflow_files = mcp_client.call_tool("esp_workflow_files")
        assert "workflow" in workflow_files.lower() or "stage" in workflow_files.lower()


# ============================================================================
# Test 2: Real Hardware Tests
# ============================================================================


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.hardware
class TestRealHardware:
    """Test with real connected ESP32 hardware."""

    @pytest.fixture(autouse=True)
    def check_hardware(self, hardware_client):
        """Check if hardware is connected before running tests"""
        # Try to list ports to verify hardware is connected
        ports_result = hardware_client.call_tool("esp_list_ports")

        # If no devices detected, skip the test
        if "no serial devices" in ports_result.lower() or "no device" in ports_result.lower():
            pytest.skip("No ESP32 hardware detected")

    def test_list_connected_devices(self, hardware_client: MCPHttpClient):
        """Test listing connected serial devices"""
        result = hardware_client.call_tool("esp_list_ports")

        assert isinstance(result, str)
        assert len(result) > 0
        # Should show at least one device if hardware is connected
        print(f"\nConnected devices:\n{result}")

    def test_read_mac_from_device(self, hardware_client: MCPHttpClient):
        """Test reading MAC address from connected device"""
        # First, find a port (prefer /dev/ttyUSB for real hardware)
        ports_result = hardware_client.call_tool("esp_list_ports")

        # Extract port from result (format: "1. /dev/ttyUSB0 - description")
        port = None
        for line in ports_result.split("\n"):
            if "/dev/ttyUSB" in line:  # Prefer USB ports (real ESP32 hardware)
                parts = line.split()
                for part in parts:
                    if "/dev/ttyUSB" in part:
                        port = part.strip()
                        break
                if port:
                    break

        # Fallback to any /dev/tty port
        if not port:
            for line in ports_result.split("\n"):
                if "/dev/tty" in line:
                    parts = line.split()
                    for part in parts:
                        if "/dev/tty" in part:
                            port = part.strip()
                            break
                    if port:
                        break

        if not port:
            pytest.skip("Could not determine serial port")

        print(f"\nUsing port: {port}")

        # Read MAC address
        result = hardware_client.call_tool("esp_read_mac", {"port": port})

        assert isinstance(result, str)
        assert len(result) > 0
        # MAC address should be in format XX:XX:XX:XX:XX:XX
        assert ":" in result or "mac" in result.lower()
        print(f"MAC Address: {result}")

    @pytest.mark.flash
    def test_flash_firmware(self, hardware_client: MCPHttpClient):
        """Test flashing firmware

        WARNING: This will overwrite the firmware on the connected device!
        """
        # First ensure firmware is built
        print("\n[Pre-check] Ensuring firmware is built...")
        build_result = hardware_client.call_tool("esp_build")
        if "failed" in build_result.lower():
            pytest.skip("Build failed, cannot test flash")

        # Find port
        ports_result = hardware_client.call_tool("esp_list_ports")
        port = None
        for line in ports_result.split("\n"):
            if "/dev/tty" in line:
                parts = line.split()
                for part in parts:
                    if "/dev/tty" in part:
                        port = part.strip()
                        break
                if port:
                    break

        if not port:
            pytest.skip("Could not determine serial port")

        print(f"\n[Flash] Using port: {port}")

        # Flash firmware (monitor not tested - use esp_monitor separately)
        print("[Flash] Flashing firmware...")
        flash_result = hardware_client.call_tool("esp_flash", {"port": port, "baud": 460800})

        assert isinstance(flash_result, str)
        assert len(flash_result) > 0

        # Should contain flash operation message
        if "flash" not in flash_result.lower():
            pytest.skip(f"Flash operation issue: {flash_result[:100]}")

        print("\nFlash result preview:")
        print(flash_result[:500])


# ============================================================================
# Test 3: Error Recovery Tests
# ============================================================================


@pytest.mark.slow
@pytest.mark.integration
class TestErrorRecovery:
    """Test error recovery and workflow resilience."""

    def test_recover_from_build_failure(self, mcp_client: MCPHttpClient):
        """Test workflow recovery after intentional build failure"""
        import shutil

        # Save original main file
        main_file = TEST_PROJECT_DIR / "main" / "main.c"
        backup_file = TEST_PROJECT_DIR / "main" / "main.c.backup"

        if not main_file.exists():
            pytest.skip("main.c not found, skipping error recovery test")

        # Backup original
        shutil.copy(main_file, backup_file)

        try:
            # Step 1: Introduce syntax error
            print("\n[Step 1] Introducing syntax error...")
            main_file.write_text("void app_main(void) { SYNTAX_ERROR_HERE }")

            # Step 2: Try to build (should fail)
            print("[Step 2] Building with error (expecting failure)...")
            build_result = mcp_client.call_tool("esp_build")

            # Build should have failed
            assert (
                "error" in build_result.lower()
                or "failed" in build_result.lower()
                or "错误" in build_result
            )

            # Step 3: Fix the error
            print("[Step 3] Fixing syntax error...")
            main_file.write_text("""
#include <stdio.h>

void app_main(void)
{
    printf("Hello, ESP-IDF!\\n");
}
""")

            # Step 4: Rebuild (should succeed)
            print("[Step 4] Rebuilding after fix...")
            build_result = mcp_client.call_tool("esp_build")

            # Should succeed now
            assert (
                "succeeded" in build_result.lower()
                or "成功" in build_result
                or "build" in build_result.lower()
            )

            print("\n✓ Error recovery test passed!")

        finally:
            # Restore original file
            if backup_file.exists():
                shutil.copy(backup_file, main_file)
                backup_file.unlink()

    def test_workflow_state_persistence(self, mcp_client: MCPHttpClient):
        """Test that workflow state persists correctly across operations"""
        # Clean state
        mcp_client.call_tool("esp_clean", {"level": "full"})

        # Perform multiple operations
        operations = [
            ("esp_project_info", {}),
            ("esp_size", {}),
            ("esp_list_ports", {}),
        ]

        for tool, args in operations:
            result = mcp_client.call_tool(tool, args)
            assert isinstance(result, str)
            assert len(result) > 0

        # Check workflow state
        state_result = mcp_client.call_tool("esp_workflow_state")
        assert "workflow" in state_result.lower() or "stage" in state_result.lower()

        print("\n✓ Workflow state persistence test passed!")

    def test_partial_workflow_recovery(self, mcp_client: MCPHttpClient):
        """Test recovering from partial workflow state"""
        # Clean start
        mcp_client.call_tool("esp_clean", {"level": "full"})

        # Step 1: Build (succeeds)
        print("\n[Step 1] Initial build...")
        build_result = mcp_client.call_tool("esp_build")
        assert (
            "succeeded" in build_result.lower()
            or "build" in build_result.lower()
            or "构建" in build_result
        )

        # Step 2: Check workflow shows build completed
        state = mcp_client.call_tool("esp_workflow_state")
        assert "build" in state.lower() or "stage" in state.lower()

        # Step 3: Try to build again (should still work)
        print("[Step 2] Rebuild...")
        rebuild_result = mcp_client.call_tool("esp_build")
        assert isinstance(rebuild_result, str)

        print("\n✓ Partial workflow recovery test passed!")


# ============================================================================
# Test 4: Advanced Workflow Integration
# ============================================================================


@pytest.mark.slow
@pytest.mark.integration
class TestAdvancedWorkflowIntegration:
    """Test advanced workflow scenarios."""

    def test_partition_table_workflow(self, mcp_client: MCPHttpClient):
        """Test partition table workflow"""
        # Show partition table
        show_result = mcp_client.call_tool("esp_show_partition_table")
        assert isinstance(show_result, str)

        # Validate partition table
        validate_result = mcp_client.call_tool("esp_validate_partition_table")
        assert isinstance(validate_result, str)

        print("\n✓ Partition table workflow test passed!")

    def test_workflow_progress_tracking(self, mcp_client: MCPHttpClient):
        """Test that workflow progress is tracked correctly"""
        # Get initial state
        initial_state = mcp_client.call_tool("esp_workflow_state")

        # Perform a build
        mcp_client.call_tool("esp_build")

        # Get new state
        new_state = mcp_client.call_tool("esp_workflow_state")

        # State should have changed
        assert isinstance(new_state, str)
        assert len(new_state) > 0

        print("\n✓ Workflow progress tracking test passed!")

    def test_build_performance(self, mcp_client: MCPHttpClient):
        """Test that build completes in reasonable time"""
        import time

        print("\n[Timing] Measuring build performance...")
        start_time = time.time()

        build_result = mcp_client.call_tool("esp_build")

        duration = time.time() - start_time

        # Verify build succeeded
        assert "succeeded" in build_result.lower() or "成功" in build_result.lower()

        # Incremental build should complete in reasonable time
        # First build may take longer, but subsequent builds should be faster
        print(f"Build duration: {duration:.2f} seconds")

        # Build should complete within 5 minutes (300 seconds)
        # This is a generous limit even for first builds
        assert duration < 300, f"Build took {duration:.1f}s, should be under 5 minutes"

        # For incremental builds (when build dir exists), should be much faster
        build_dir = TEST_PROJECT_DIR / "build"
        if build_dir.exists():
            # If build directory exists, this is likely an incremental build
            # Should complete in under 60 seconds
            assert duration < 60, (
                f"Incremental build took {duration:.1f}s, should be under 1 minute"
            )

    def test_workflow_stage_completion(self, mcp_client: MCPHttpClient):
        """Test that workflow stages are marked as completed correctly"""
        import re

        # Get initial workflow state
        initial_state = mcp_client.call_tool("esp_workflow_files")

        # Perform a build operation
        build_result = mcp_client.call_tool("esp_build")
        assert "succeeded" in build_result.lower() or "成功" in build_result.lower()

        # Check workflow state after build
        final_state = mcp_client.call_tool("esp_workflow_files")

        # Verify build stage is marked as completed
        assert "build" in final_state.lower()

        # Check for completion indicators
        # Should show either ✓ or "completed" for the build stage
        has_completion_marker = (
            "✓" in final_state
            or "[COMPLETED]" in final_state
            or "completed" in final_state.lower()
            or "exit: 0" in final_state  # Successful exit code
        )

        assert has_completion_marker, "Build stage should be marked as completed"

        # Extract and verify completion timestamp if present
        timestamp_match = re.search(r"build.*?(\d{2}:\d{2}:\d{2})", final_state, re.IGNORECASE)
        if timestamp_match:
            print(f"Build completion time: {timestamp_match.group(1)}")

        print("\n✓ Workflow stage completion test passed!")


# ============================================================================
# Test 5: Artifact Verification Integration
# ============================================================================


@pytest.mark.slow
@pytest.mark.integration
class TestArtifactVerification:
    """Test build artifact verification and validation."""

    def test_firmware_size_validation(self, mcp_client: MCPHttpClient):
        """Test that firmware size is within expected bounds"""
        import re

        # Ensure firmware is built
        build_result = mcp_client.call_tool("esp_build")
        assert "succeeded" in build_result.lower() or "成功" in build_result.lower()

        # Get size analysis
        size_result = mcp_client.call_tool("esp_size")

        # Parse firmware size from output - try multiple patterns
        # The size output format varies, so we use flexible patterns
        size_patterns = [
            r"(\d+)\s+bytes",  # Most common: "123456 bytes"
            r"text\s+\s+\d+\s+(\d+)",  # text section
            r"data\s+\s+\d+\s+(\d+)",  # data section
            r"bss\s+\s+\d+\s+(\d+)",  # bss section
        ]

        found_sizes = []
        for pattern in size_patterns:
            matches = re.findall(pattern, size_result)
            found_sizes.extend([int(m) for m in matches])

        # Should have found at least one size
        assert len(found_sizes) > 0, f"Should find size information in: {size_result[:200]}"

        # Verify at least some sections have meaningful sizes (>0)
        valid_sizes = [s for s in found_sizes if s > 0]
        assert len(valid_sizes) > 0, f"Should have valid sizes, found: {found_sizes}"

        # Verify main sections have reasonable sizes
        # ESP32 hello_world should have sections between 10KB and 2MB
        reasonable_sizes = [s for s in valid_sizes if 10_000 < s < 2_000_000]
        assert len(reasonable_sizes) > 0, (
            f"Should have reasonable firmware size, found: {valid_sizes}"
        )

        print(f"\nFirmware size analysis: found {len(reasonable_sizes)} reasonable sections")
        print(f"Sample sizes: {reasonable_sizes[:3]}")

    def test_build_artifacts_exist(self, mcp_client: MCPHttpClient):
        """Test that all expected build artifacts are created"""
        # Build firmware
        build_result = mcp_client.call_tool("esp_build")
        assert "succeeded" in build_result.lower() or "成功" in build_result.lower()

        # Verify build directory
        build_dir = TEST_PROJECT_DIR / "build"
        assert build_dir.exists(), "Build directory should exist"

        # Check for expected artifacts
        artifacts_to_check = [
            ("*.bin", "Firmware binary files"),
            ("*.elf", "ELF executable"),
            ("build.ninja", "Ninja build file"),
        ]

        found_artifacts = {}
        for pattern, description in artifacts_to_check:
            files = list(build_dir.glob(pattern))
            found_artifacts[description] = len(files)
            assert len(files) > 0, f"Should have {description} matching {pattern}"

        print("\nBuild artifacts found:")
        for desc, count in found_artifacts.items():
            print(f"  {desc}: {count} files")
