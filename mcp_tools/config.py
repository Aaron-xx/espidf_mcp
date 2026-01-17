"""Config tools for ESP-IDF MCP Server.

Provides configuration-related functionality:
- Project information display
- Partition table operations
- Configuration validation
"""

from .base import BaseTool, ToolResult, format_subprocess_result


class ConfigTools(BaseTool):
    """Configuration-related tools for ESP-IDF development."""

    def register_tools(self) -> None:
        """Register all config tools with the MCP server."""

        @self.mcp.tool()
        @self._log_tool_call
        def esp_project_info() -> str:
            """Get current ESP-IDF project information.

            PURPOSE:
                Display current ESP-IDF project status and configuration information.

            DESCRIPTION:
                Detect and display detailed information about the current project,
                including project path, CMakeLists.txt and sdkconfig file status.
                Used to verify if the current directory is a valid ESP-IDF project.

            REQUIREMENTS:
                - Must be run in an ESP-IDF project directory.

            RETURNS:
                str: Formatted project information string containing:
                    - Project root directory path
                    - CMakeLists.txt file status
                    - sdkconfig file status
                    - Current working directory

            EXAMPLE:
                Call: esp_project_info()
                Returns: "Project directory: /path/to/project\nCMakeLists.txt: exists..."
            """
            if not self.project.is_valid:
                _, message = self.project.validate()
                return f"Error: Current directory is not a valid ESP-IDF project\n\n{message}"

            output = [
                f"Project directory: {self.project.root}",
                f"CMakeLists.txt: {'exists' if self.project.cmake_path.exists() else 'not found'}",
                f"sdkconfig: {'exists' if self.project.sdkconfig_path.exists() else 'not found'}",
                f"Current working directory: {self.project.root}",
            ]
            return "\n".join(output)

        @self.mcp.tool()
        @self._log_tool_call
        def esp_show_partition_table() -> str:
            """Show ESP-IDF project partition table.

            PURPOSE:
                Display the partition table configuration for the project.

            DESCRIPTION:
                The partition table defines how flash memory is divided into
                different regions (app, otadata, nvs, phy_init, etc.).

            RETURNS:
                str: Partition table information

            NOTES:
                - Partition table is defined in partitions.csv or sdkconfig
                - This is a read-only operation

            EXAMPLE:
                Call: esp_show_partition_table()
            """
            result = self._run_command(
                ["idf.py", "partition-table"],
                timeout=30,
            )
            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    message="Partition table",
                    details=result.stdout.strip(),
                ).to_response()
            else:
                return format_subprocess_result(result, "Show partition table")

        @self.mcp.tool()
        @self._log_tool_call
        def esp_validate_partition_table() -> str:
            """Validate ESP-IDF project partition table.

            PURPOSE:
                Validate the partition table configuration for correctness.

            DESCRIPTION:
                Checks if the partition table is valid and can be used for flashing.

            RETURNS:
                str: Validation result

            NOTES:
                - Useful after manually modifying partitions.csv
                - Ensures partition table meets ESP-IDF requirements

            EXAMPLE:
                Call: esp_validate_partition_table()
            """
            result = self._run_command(
                ["idf.py", "partition-table", "--validate"],
                timeout=30,
            )
            if result.returncode == 0:
                return "Partition table validation passed"
            else:
                return format_subprocess_result(result, "Partition table validation")
