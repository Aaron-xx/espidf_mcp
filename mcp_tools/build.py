"""Build tools for ESP-IDF MCP Server.

Provides build-related functionality:
- Building firmware
- Cleaning build artifacts
- Analyzing firmware size
- Setting target chip
"""

import time
from typing import Literal

from .base import BaseTool, format_subprocess_result


class BuildTools(BaseTool):
    """Build-related tools for ESP-IDF development."""

    def register_tools(self) -> None:
        """Register all build tools with the MCP server."""

        @self.mcp.tool()
        @self._log_tool_call
        def esp_build() -> str:
            """Build ESP-IDF project firmware.

            PURPOSE:
                Compile the current ESP-IDF project to generate flashable firmware.

            DESCRIPTION:
                Execute idf.py build command to compile the entire project,
                including application, bootloader, and partition table.
                Generated .bin files are located in the build/ directory.

            REQUIREMENTS:
                - ESP-IDF environment must be properly configured (IDF_PATH set)
                - Project must have target chip set via esp_set_target
                - All dependencies must be installed

            RETURNS:
                str: Build result information containing:
                    - Build success/failure status
                    - Build output summary (file size, component count, etc.)
                    - Generated firmware file paths

            NOTES:
                - Build time depends on project size and system performance
                - First build downloads and compiles all components
                - Incremental builds only recompile modified files

            EXAMPLE:
                Call: esp_build()
                Returns: "Build succeeded (duration: 5.20s)..."
            """
            start_time = time.time()
            result = self._run_command(
                ["idf.py", "build"],
                timeout=600,  # 10 minutes for build
            )
            duration = time.time() - start_time

            # Save output to workflow state if available
            if self.workflow is not None:
                # Collect artifacts
                artifacts = []
                build_dir = self.project.root / "build"
                if build_dir.exists():
                    artifacts = [str(f) for f in build_dir.glob("*.bin")]

                self.workflow.save_stage_output(
                    stage_name="build",
                    command="idf.py build",
                    result=result,
                    duration=duration,
                    artifacts=artifacts,
                )

            return format_subprocess_result(result, "Build", duration)

        @self.mcp.tool()
        @self._log_tool_call
        def esp_clean(level: Literal["standard", "full"] = "standard") -> str:
            """Clean ESP-IDF project build files.

            PURPOSE:
                Delete generated build files to free disk space or force rebuild.

            DESCRIPTION:
                Execute idf.py clean or fullclean command based on level.
                Standard: deletes build artifacts but preserves configuration.
                Full: deletes entire build directory including configuration.

            PARAMETERS:
                level (str): Clean level
                    - "standard": Clean build artifacts only (idf.py clean)
                    - "full": Clean everything including config (idf.py fullclean)
                    - Default: "standard"

            RETURNS:
                str: Clean result with status

            NOTES:
                - Standard: Preserves sdkconfig, faster rebuild
                - Full: Deletes all, requires full reconfiguration
                - Use full after changing target chip or if build is corrupted

            EXAMPLE:
                Call: esp_clean(level="standard")
                Call: esp_clean(level="full")
            """
            if level == "full":
                cmd = ["idf.py", "fullclean"]
                name = "Full clean"
            else:
                cmd = ["idf.py", "clean"]
                name = "Clean"

            result = self._run_command(cmd, timeout=120)  # 2 minutes
            return format_subprocess_result(result, name)

        @self.mcp.tool()
        @self._log_tool_call
        def esp_size() -> str:
            """Analyze ESP-IDF firmware size and memory usage.

            PURPOSE:
                Display firmware component flash and RAM usage.

            DESCRIPTION:
                Analyze compiled firmware to display memory usage for each component
                and section, helping optimize code size and memory usage.
                Includes total size, component sizes, and memory usage statistics.

            REQUIREMENTS:
                - Firmware must be built successfully

            RETURNS:
                str: Firmware size analysis report containing:
                    - Total firmware size
                    - Component size statistics
                    - Flash partition usage
                    - RAM usage

            EXAMPLE:
                Call: esp_size()
                Returns: "Firmware size analysis\n\nTotal sizes:\nText: 180816 bytes..."
            """
            from .exceptions import BuildRequiredError

            build_dir = self.project.root / "build"

            # Verify prerequisites
            if not build_dir.exists():
                raise BuildRequiredError(
                    build_dir=str(build_dir), details="esp_size requires firmware to be built first"
                )

            result = self._run_command(
                ["idf.py", "size"],
                timeout=60,  # 1 minute for size analysis
            )
            # For size analysis, we want to show the output even on success
            if result.returncode == 0:
                from .base import ToolResult

                return ToolResult(
                    success=True,
                    message="Firmware size analysis",
                    details=result.stdout.strip(),
                ).to_response()
            else:
                return format_subprocess_result(result, "Firmware size analysis")

        @self.mcp.tool()
        @self._log_tool_call
        def esp_set_target(
            target: Literal[
                "esp32",
                "esp32s2",
                "esp32c3",
                "esp32s3",
                "esp32c2",
                "esp32h2",
                "esp32p4",
                "esp32c6",
                "esp32c5",
            ],
        ) -> str:
            """Set ESP-IDF project target chip.

            PURPOSE:
                Configure project to build for specified ESP32 chip model.

            DESCRIPTION:
                Set project target chip, configuring compiler, linker, and SDK
                for the specified chip. Must call when first configuring project
                or changing chips.

            PARAMETERS:
                target (str): Target chip model
                    - Options: esp32, esp32s2, esp32c3, esp32s3, esp32c2, esp32h2,
                      esp32p4, esp32c6, esp32c5
                    - Required: Yes

            SUPPORTED CHIPS:
                - esp32: ESP32 (original, Xtensa)
                - esp32s2: ESP32-S2 (Xtensa, USB OTG)
                - esp32c3: ESP32-C3 (RISC-V, WiFi + BLE)
                - esp32s3: ESP32-S3 (Xtensa, WiFi + BLE, AI accelerator)
                - esp32c2: ESP32-C2 (RISC-V, WiFi only)
                - esp32h2: ESP32-H2 (RISC-V, WiFi 6 + BLE 5.0)
                - esp32p4: ESP32-P4 (Xtensa, high performance)
                - esp32c6: ESP32-C6 (RISC-V, WiFi 6 + BLE 5.0)
                - esp32c5: ESP32-C5 (RISC-V)

            RETURNS:
                str: Configuration result containing:
                    - Configuration success status
                    - Generated sdkconfig file information
                    - Chip feature summary

            NOTES:
                - Generates or updates sdkconfig file
                - Recommended to run esp_clean(level="full") after changing target

            EXAMPLE:
                Call: esp_set_target(target="esp32s3")
            """
            from .base import ToolResult

            # Runtime validation for defense in depth
            valid_targets = {
                "esp32",
                "esp32s2",
                "esp32c3",
                "esp32s3",
                "esp32c2",
                "esp32h2",
                "esp32p4",
                "esp32c6",
                "esp32c5",
            }
            if target not in valid_targets:
                return ToolResult(
                    success=False,
                    message="Invalid target",
                    details=f"'{target}' is not a valid target chip.",
                    error_code="INVALID_TARGET",
                ).to_response()

            # Ensure target only contains safe characters (alphanumeric and underscore)
            if not target.replace("_", "").isalnum():
                return ToolResult(
                    success=False,
                    message="Invalid target format",
                    details=f"Target '{target}' contains invalid characters. Target must be alphanumeric.",
                    error_code="INVALID_FORMAT",
                ).to_response()

            result = self._run_command(
                ["idf.py", "set-target", target],
                timeout=60,
            )

            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    message=f"Set target to {target} succeeded",
                    details=result.stdout.strip(),
                ).to_response()
            else:
                return format_subprocess_result(result, "Set target")
