"""ESP-IDF MCP Server Core.

Provides MCP server with factory function for flexible project configuration.
"""

import asyncio
import subprocess
from dataclasses import dataclass
from typing import Literal

import serial
import serial.tools.list_ports
from mcp.server.fastmcp import FastMCP


@dataclass
class CommandResult:
    """Result of command execution.

    Attributes:
        success: Whether the command succeeded.
        output: Standard output from the command.
        error: Standard error from the command, if any.
    """

    success: bool
    output: str
    error: str | None = None


def create_server(
    project,
    host: str = "127.0.0.1",
    port: int = 8090,
) -> FastMCP:
    """Create an ESP-IDF MCP server instance.

    Args:
        project: ProjectInfo instance containing project path and validation info.
        host: HTTP mode listening address.
        port: HTTP mode listening port.

    Returns:
        Configured FastMCP server instance.
    """
    mcp = FastMCP("ESP-IDF MCP Server", host=host, port=port, stateless_http=True)

    @mcp.tool()
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
        if not project.is_valid:
            _, message = project.validate()
            return f"Error: Current directory is not a valid ESP-IDF project\n\n{message}"

        output = [
            f"Project directory: {project.root}",
            f"CMakeLists.txt: {'exists' if project.cmake_path.exists() else 'not found'}",
            f"sdkconfig: {'exists' if project.sdkconfig_path.exists() else 'not found'}",
            f"Current working directory: {project.root}",
        ]
        return "\n".join(output)

    @mcp.tool()
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
            - Project must have target chip set via set-target
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
            Returns: "Build succeeded\n\nhello_world.bin binary size 0x2c250 bytes..."
        """
        result = subprocess.run(
            ["idf.py", "build"], cwd=project.root, capture_output=True, text=True
        )
        if result.returncode == 0:
            return f"Build succeeded\n\n{result.stdout}"
        else:
            return f"Build failed\n\n{result.stderr}"

    @mcp.tool()
    def esp_flash(port: str | None = None, baud: int = 460800) -> str:
        """Flash firmware to ESP32 chip.

        PURPOSE:
            Flash compiled firmware to the connected ESP32 device.

        DESCRIPTION:
            Use esptool to write firmware (including bootloader, application,
            and partition table) to the ESP32 chip's flash memory.
            Device automatically restarts after flashing.

        PARAMETERS:
            port (str | None): Serial device path
                - Examples: "/dev/ttyUSB0", "/dev/ttyACM0", "COM3"
                - Default: None (auto-detect)
                - Required: No
            baud (int): Flash baud rate
                - Default: 460800
                - Range: 115200 - 921600
                - Required: No

        REQUIREMENTS:
            - ESP32 device must be connected via USB
            - Device must have proper serial permissions (user in dialout group)
            - Firmware must be built via esp_build
            - If port is None, system auto-detects available port

        RETURNS:
            str: Flash result containing:
                - Flash success/failure status
                - Chip information (model, MAC address, flash size)
                - Partition flash progress and verification results

        NOTES:
            - Device automatically resets during flashing
            - Flash speed affected by baud rate, 460800 is recommended
            - If flash fails, try reducing baud rate to 115200

        EXAMPLE:
            Call: esp_flash(port="/dev/ttyUSB0")
            Call: esp_flash(port="/dev/ttyUSB0", baud=921600)
        """
        cmd = ["idf.py", "flash"]
        if port:
            cmd.extend(["-p", port])
        cmd.extend(["-b", str(baud)])

        result = subprocess.run(cmd, cwd=project.root, capture_output=True, text=True)
        if result.returncode == 0:
            return f"Flash succeeded\n\n{result.stdout}"
        else:
            return f"Flash failed\n\n{result.stderr}"

    @mcp.tool()
    async def esp_monitor(port: str, baud: int = 115200, seconds: int = 60) -> str:
        """Monitor ESP32 serial output in real-time.

        PURPOSE:
            Capture and display ESP32 device serial log output.

        DESCRIPTION:
            Open specified serial port and read device log output in real-time.
            Used for debugging, viewing program runtime status and error messages.
            Supports long-running monitoring with periodic progress updates.

        PARAMETERS:
            port (str): Serial device path
                - Examples: "/dev/ttyUSB0", "/dev/ttyACM0"
                - Required: Yes
            baud (int): Serial baud rate
                - Default: 115200 (ESP-IDF standard baud rate)
                - Common values: 115200, 921600
                - Required: No
            seconds (int): Monitoring duration in seconds
                - Default: 60
                - Range: 1 - 600
                - Required: No

        REQUIREMENTS:
            - ESP32 device must be connected
            - Serial port must have read permissions
            - Device must be running and outputting logs

        RETURNS:
            str: Serial output content containing:
                - All received log lines
                - Progress reminder every 20 seconds
                - Total runtime and received line count statistics

        NOTES:
            - Log format is ESP-IDF standard (tag + level + message)
            - If device produces no output, shows timeout
            - Automatically ends after specified time

        EXAMPLE:
            Call: esp_monitor(port="/dev/ttyUSB0", seconds=30)
            Returns: "Starting monitor on /dev/ttyUSB0...\nI (37) boot: ESP-IDF v5.5.1..."
        """
        ser = None
        try:
            ser = serial.Serial(port, baudrate=baud, timeout=1)
            ser.reset_input_buffer()

            output = []
            start_time = asyncio.get_event_loop().time()
            line_count = 0
            last_reminder = 0

            output.append(f"Starting monitor on {port} (baud: {baud})")
            output.append("=" * 50)

            while asyncio.get_event_loop().time() - start_time < seconds:
                elapsed = int(asyncio.get_event_loop().time() - start_time)

                # Remind every 20 seconds
                if elapsed - last_reminder >= 20:
                    remaining = seconds - elapsed
                    output.append(f"\nRunning for {elapsed}s, {remaining}s remaining")
                    output.append("=" * 50)
                    last_reminder = elapsed

                if ser.in_waiting > 0:
                    try:
                        data = ser.readline()
                        if data:
                            decoded = data.decode("utf-8", errors="ignore").strip()
                            if decoded:
                                output.append(decoded)
                                line_count += 1
                    except (serial.SerialException, UnicodeDecodeError):
                        pass
                await asyncio.sleep(0.05)  # 50ms poll interval

            elapsed = int(asyncio.get_event_loop().time() - start_time)
            output.append(f"\nMonitoring ended (ran {elapsed}s, {line_count} lines)")
            return "\n".join(output)

        except serial.SerialException as e:
            return f"Serial error: {e}"
        except Exception as e:
            return f"Monitor failed: {e}"
        finally:
            if ser and ser.is_open:
                ser.close()

    @mcp.tool()
    def esp_clean() -> str:
        """Clean ESP-IDF project build files.

        PURPOSE:
            Delete generated intermediate and target files, preserve configuration.

        DESCRIPTION:
            Execute idf.py clean command to delete build artifacts in build/
            directory, but preserve sdkconfig configuration file.
            Used for rebuilding or freeing disk space.

        REQUIREMENTS:
            - Project must have been built before

        RETURNS:
            str: Clean result with number of files removed and status

        NOTES:
            - Only deletes build artifacts, not source code
            - Preserves sdkconfig configuration
            - Next build will recompile all files

        EXAMPLE:
            Call: esp_clean()
            Returns: "Clean succeeded\n\nCleaning... 521 files."
        """
        result = subprocess.run(
            ["idf.py", "clean"], cwd=project.root, capture_output=True, text=True
        )
        if result.returncode == 0:
            return f"Clean succeeded\n\n{result.stdout}"
        else:
            return f"Clean failed\n\n{result.stderr}"

    @mcp.tool()
    def esp_fullclean() -> str:
        """Fully clean ESP-IDF project build files.

        PURPOSE:
            Delete all generated files including configuration and cache.

        DESCRIPTION:
            Execute idf.py fullclean command to delete entire build/ directory,
            including configuration files, dependency cache, and all build artifacts.
            Used for thoroughly cleaning the project.

        REQUIREMENTS:
            - Project directory must be writable

        RETURNS:
            str: Clean result with deletion status

        NOTES:
            - Deletes entire build/ directory
            - Next build requires full reconfiguration and recompilation
            - More thorough than esp_clean
            - Can fix corrupted configuration or cache issues

        EXAMPLE:
            Call: esp_fullclean()
            Returns: "Full clean succeeded\n\nProject fully cleaned."
        """
        result = subprocess.run(
            ["idf.py", "fullclean"], cwd=project.root, capture_output=True, text=True
        )
        if result.returncode == 0:
            return f"Full clean succeeded\n\n{result.stdout}"
        else:
            return f"Full clean failed\n\n{result.stderr}"

    @mcp.tool()
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
                - Comparison with flash capacity

        NOTES:
            - Used for optimizing and debugging memory issues
            - Displays detailed information for text, data, BSS sections
            - Helps identify components occupying large space

        EXAMPLE:
            Call: esp_size()
            Returns: "Firmware size analysis\n\nTotal sizes:\nText: 180816 bytes..."
        """
        result = subprocess.run(
            ["idf.py", "size"], cwd=project.root, capture_output=True, text=True
        )
        if result.returncode == 0:
            return f"Firmware size analysis\n\n{result.stdout}"
        else:
            return f"Analysis failed\n\n{result.stderr}"

    @mcp.tool()
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

        REQUIREMENTS:
            - ESP-IDF must support target chip
            - Some chips may require specific ESP-IDF versions

        RETURNS:
            str: Configuration result containing:
                - Configuration success status
                - Generated sdkconfig file information
                - Chip feature summary

        NOTES:
            - Generates or updates sdkconfig file
            - Recommended to run esp_fullclean after changing target
            - Different chips have different peripherals and features

        EXAMPLE:
            Call: esp_set_target(target="esp32s3")
            Returns: "Set target to esp32s3 succeeded\n\nConfiguration done..."
        """
        result = subprocess.run(
            ["idf.py", "set-target", target], cwd=project.root, capture_output=True, text=True
        )
        if result.returncode == 0:
            return f"Set target to {target} succeeded\n\n{result.stdout}"
        else:
            return f"Set target failed\n\n{result.stderr}"

    @mcp.tool()
    def esp_list_ports() -> str:
        """List all available serial port devices.

        PURPOSE:
            Scan and display all available serial port devices in the system.

        DESCRIPTION:
            Use pyserial to scan system for all serial ports, returning device
            paths and description information. Used to identify connected ESP32
            devices or other serial devices.

        REQUIREMENTS:
            - No special requirements

        RETURNS:
            str: List of serial ports, each line containing:
                - Device number
                - Device path (e.g., /dev/ttyUSB0)
                - Device description (e.g., CP2102N USB to UART Bridge)

        NOTES:
            - Includes both virtual and physical serial ports
            - ESP32 boards typically show as USB-Serial or CP210x
            - Returns warning message if no devices detected

        EXAMPLE:
            Call: esp_list_ports()
            Returns: "1. /dev/ttyUSB0 - CP2102N USB to UART Bridge Controller\n2. ..."
        """
        ports = serial.tools.list_ports.comports()
        if not ports:
            return "No serial devices detected"
        output = []
        for i, port in enumerate(ports, 1):
            output.append(f"{i}. {port.device} - {port.description}")
        return "\n".join(output)

    @mcp.tool()
    def esp_idf_expert() -> str:
        """Get ESP-IDF expert role guidance.

        Returns:
            Usage guide for ESP-IDF MCP tools with common workflows
            and best practices.
        """
        return """ESP-IDF MCP Expert Assistant

Connected to ESP-IDF MCP server for ESP32 development tasks.

Common Workflows:

1. Project Check
   Call: esp_project_info()
   Confirm current project configuration

2. Set Target Chip
   Call: esp_set_target(target="esp32s3")
   Supported: esp32, esp32s2, esp32s3, esp32c3, esp32c6

3. Build Firmware
   Call: esp_build()
   Compile current project

4. Flash Firmware
   Call: esp_flash(port="/dev/ttyUSB0")
   Check available ports with esp_list_ports()

5. Monitor Serial
   Call: esp_monitor(port="/dev/ttyUSB0")
   View device runtime logs

Best Practices:
- Call esp_project_info() before starting new tasks to verify environment
- Use esp_fullclean() to clean and retry if build fails
- Use esp_size() to check firmware size distribution"""

    return mcp
