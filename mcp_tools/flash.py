"""Flash tools for ESP-IDF MCP Server.

Provides flash-related functionality:
- Flashing firmware to ESP32
- Monitoring serial output
- Reading MAC address
- Erasing flash regions
"""

import asyncio

import serial
import serial.tools.list_ports

from .base import BaseTool, ToolResult, format_subprocess_result


class FlashTools(BaseTool):
    """Flash-related tools for ESP-IDF development."""

    def register_tools(self) -> None:
        """Register all flash tools with the MCP server."""

        @self.mcp.tool()
        @self._log_tool_call
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
                    - Examples: "/dev/ttyUSB0", "/dev/ttyACM0"
                    - Default: None (auto-detect)
                    - Required: No
                baud (int): Flash baud rate
                    - Default: 460800
                    - Range: 115200 - 921600
                    - Required: No

            REQUIREMENTS:
                - ESP32 device must be connected via USB
                - Device must have proper serial permissions
                - Firmware must be built via esp_build

            RETURNS:
                str: Flash result containing chip information and status

            NOTES:
                - Device automatically resets during flashing
                - If flash fails, try reducing baud rate to 115200

            EXAMPLE:
                Call: esp_flash(port="/dev/ttyUSB0")
            """
            from .exceptions import BuildRequiredError

            build_dir = self.project.root / "build"

            # Verify prerequisites
            if not build_dir.exists():
                raise BuildRequiredError(
                    build_dir=str(build_dir),
                    details="esp_flash requires firmware to be built first",
                )

            # Verify firmware binaries exist
            bin_files = list(build_dir.glob("**/*.bin"))
            if not bin_files:
                raise BuildRequiredError(
                    build_dir=str(build_dir),
                    details="No firmware binaries found to flash",
                )

            cmd = ["idf.py", "flash"]
            if port:
                cmd.extend(["-p", port])
            cmd.extend(["-b", str(baud)])

            result = self._run_command(cmd, timeout=300)  # 5 minutes
            return format_subprocess_result(result, "Flash")

        @self.mcp.tool()
        @self._log_tool_call
        async def esp_monitor(port: str, baud: int = 115200, seconds: int = 60) -> str:
            """Monitor ESP32 serial output in real-time.

            PURPOSE:
                Capture and display ESP32 device serial log output.

            DESCRIPTION:
                Open specified serial port and read device log output in real-time.
                Used for debugging, viewing program runtime status and error messages.

            PARAMETERS:
                port (str): Serial device path
                    - Examples: "/dev/ttyUSB0", "/dev/ttyACM0"
                    - Required: Yes
                baud (int): Serial baud rate
                    - Default: 115200
                    - Required: No
                seconds (int): Monitoring duration in seconds
                    - Default: 60
                    - Required: No

            RETURNS:
                str: Serial output content with progress updates

            NOTES:
                - Log format is ESP-IDF standard (tag + level + message)
                - Automatically ends after specified time

            EXAMPLE:
                Call: esp_monitor(port="/dev/ttyUSB0", seconds=30)
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

        @self.mcp.tool()
        @self._log_tool_call
        def esp_read_mac(port: str | None = None) -> str:
            """Read MAC address from ESP32 chip.

            PURPOSE:
                Read the factory-programmed MAC address from connected ESP32.

            DESCRIPTION:
                Reads the MAC address from the chip's eFuse memory using esptool.
                Useful for device identification and network configuration.

            PARAMETERS:
                port (str | None): Serial device path (auto-detect if None)

            RETURNS:
                str: MAC address information

            NOTES:
                - Returns factory MAC from eFuse
                - WiFi uses MAC + 1 for station, MAC + 2 for softAP
                - Uses esptool directly

            EXAMPLE:
                Call: esp_read_mac(port="/dev/ttyUSB0")
            """
            cmd = ["esptool.py"]
            if port:
                cmd.extend(["--port", port])
            cmd.append("read_mac")

            result = self._run_command(cmd, timeout=60)

            # For successful reads, include the raw output
            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    message="MAC address read",
                    details=result.stdout.strip(),
                ).to_response()
            else:
                return format_subprocess_result(result, "Read MAC")

        @self.mcp.tool()
        @self._log_tool_call
        def esp_erase_region(address: str, size: int, port: str | None = None) -> str:
            """Erase a specific region of flash memory.

            PURPOSE:
                Erase a specific region of flash without re-flashing entire firmware.

            DESCRIPTION:
                Use esptool to erase a specified region of flash memory.
                Useful for clearing NVS, wiping data partitions, or freeing
                specific flash areas.

            PARAMETERS:
                address (str): Starting address in hex (e.g., "0x9000")
                size (int): Size in bytes to erase
                port (str | None): Serial device path (auto-detect if None)

            RETURNS:
                str: Erasure result with status

            NOTES:
                - Address must be aligned to sector boundary (4KB)
                - Be careful: erased data cannot be recovered
                - Common NVS address: 0x9000

            EXAMPLE:
                Call: esp_erase_region(address="0x9000", size=4096)
            """
            cmd = ["idf.py", "erase-region", address, str(size)]
            if port:
                cmd.extend(["-p", port])

            result = self._run_command(cmd, timeout=180)  # 3 minutes

            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    message=f"Erase region successful: {address} ({size} bytes)",
                    details=result.stdout.strip(),
                ).to_response()
            else:
                return format_subprocess_result(result, "Erase region")

        @self.mcp.tool()
        @self._log_tool_call
        def esp_list_ports() -> str:
            """List all available serial port devices.

            PURPOSE:
                Scan and display all available serial port devices in the system.

            DESCRIPTION:
                Use pyserial to scan system for all serial ports, returning device
                paths and description information. Used to identify connected ESP32
                devices or other serial devices.

            RETURNS:
                str: List of serial ports, each line containing:
                    - Device number
                    - Device path (e.g., /dev/ttyUSB0)
                    - Device description (e.g., CP2102N USB to UART Bridge)

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
