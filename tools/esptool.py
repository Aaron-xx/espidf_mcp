"""esptool wrappers for low-level ESP32 operations.

Provides direct access to esptool functionality for operations
that are not exposed through idf.py.
"""

import subprocess
from pathlib import Path
from typing import Literal

from ..utils import resolve_safe_path
from .base import ESPTool, ToolResult


class ESPToolWrapper(ESPTool):
    """Wrapper for esptool commands using ESPTool base class."""

    def __init__(self, project_root: Path):
        """Initialize esptool wrapper.

        Args:
            project_root: ESP-IDF project root directory.
        """
        super().__init__(
            name="esptool_wrapper",
            description="Low-level esptool operations wrapper",
            timeout=120,
        )
        self.project_root = project_root

    def _run_esptool(self, args: list[str]) -> ToolResult:
        """Run esptool with specified arguments.

        Args:
            args: Arguments to pass to esptool.

        Returns:
            ToolResult with command output.
        """
        try:
            result = subprocess.run(
                ["esptool.py"] + args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    data=result.stdout,
                    meta={"command": "esptool.py " + " ".join(args)},
                )
            else:
                return ToolResult(
                    success=False,
                    error=result.stderr or result.stdout,
                    meta={"command": "esptool.py " + " ".join(args)},
                )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"esptool timed out after {self.timeout}s",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"esptool failed: {e}",
            )


class ESPFlashTool(ESPTool):
    """Tool for low-level flash operations."""

    def __init__(self, project_root: Path):
        super().__init__(
            name="flash_tool",
            description="Low-level flash read/write operations",
            timeout=300,
        )
        self.project_root = project_root

    def read_flash(
        self,
        address: int,
        size: int,
        output_file: str,
        port: str,
        baud: int = 115200,
    ) -> ToolResult:
        """Read flash contents to file.

        Args:
            address: Starting address to read from.
            size: Number of bytes to read.
            output_file: File to write data to.
            port: Serial port device.
            baud: Baud rate (default: 115200).

        Returns:
            ToolResult with read operation status.
        """
        try:
            # Use safe path resolution to prevent directory traversal
            output_path = resolve_safe_path(self.project_root, output_file)
            result = subprocess.run(
                [
                    "esptool.py",
                    "--port",
                    port,
                    "--baud",
                    str(baud),
                    "read_flash",
                    hex(address),
                    str(size),
                    str(output_path),
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    data=f"Flash read complete: {output_path}",
                    meta={"size": size, "address": address, "file": str(output_path)},
                )
            else:
                return ToolResult(
                    success=False,
                    error=result.stderr or result.stdout,
                )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Read flash timed out after {self.timeout}s",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Read flash failed: {e}",
            )

    def write_flash(
        self,
        address: int,
        input_file: str,
        port: str,
        baud: int = 460800,
    ) -> ToolResult:
        """Write data to flash.

        Args:
            address: Starting address to write to.
            input_file: File containing data to write.
            port: Serial port device.
            baud: Baud rate (default: 460800).

        Returns:
            ToolResult with write operation status.
        """
        try:
            # Use safe path resolution to prevent directory traversal
            input_path = resolve_safe_path(self.project_root, input_file)
            if not input_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Input file not found: {input_path}",
                )

            result = subprocess.run(
                [
                    "esptool.py",
                    "--port",
                    port,
                    "--baud",
                    str(baud),
                    "write_flash",
                    hex(address),
                    str(input_path),
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    data=f"Flash write complete: {input_file} -> {hex(address)}",
                    meta={"file": str(input_path), "address": address},
                )
            else:
                return ToolResult(
                    success=False,
                    error=result.stderr or result.stdout,
                )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Write flash timed out after {self.timeout}s",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Write flash failed: {e}",
            )

    def erase_flash(self, port: str) -> ToolResult:
        """Erase entire flash chip.

        Args:
            port: Serial port device.

        Returns:
            ToolResult with erase operation status.
        """
        try:
            result = subprocess.run(
                ["esptool.py", "--port", port, "erase_flash"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    data="Flash erase complete",
                )
            else:
                return ToolResult(
                    success=False,
                    error=result.stderr or result.stdout,
                )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Erase flash timed out after {self.timeout}s",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Erase flash failed: {e}",
            )


class ELFTool(ESPTool):
    """Tool for ELF to binary image conversion."""

    def __init__(self, project_root: Path):
        super().__init__(
            name="elf_tool",
            description="ELF to binary image conversion",
            timeout=60,
        )
        self.project_root = project_root

    def elf2image(
        self,
        elf_file: str | None = None,
        chip: Literal[
            "esp32",
            "esp32s2",
            "esp32s3",
            "esp32c3",
            "esp32c6",
            "esp32h2",
            "esp32c2",
        ] = "esp32",
    ) -> ToolResult:
        """Convert ELF file to binary image.

        Args:
            elf_file: Path to ELF file (default: build/project.elf).
            chip: Target chip type.

        Returns:
            ToolResult with conversion status.
        """
        try:
            if elf_file is None:
                # Try to find the ELF file in build directory
                build_dir = self.project_root / "build"
                elf_files = list(build_dir.glob("*.elf"))
                if not elf_files:
                    return ToolResult(
                        success=False,
                        error="No ELF file found in build directory. Build the project first.",
                    )
                elf_file = str(elf_files[0])

            # Use safe path resolution to prevent directory traversal
            elf_path = resolve_safe_path(self.project_root, elf_file)
            if not elf_path.exists():
                return ToolResult(
                    success=False,
                    error=f"ELF file not found: {elf_path}",
                )

            result = subprocess.run(
                ["esptool.py", "--chip", chip, "elf2image", str(elf_path)],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    data=f"ELF to image conversion complete: {elf_file}",
                    meta={"chip": chip, "elf_file": str(elf_path)},
                )
            else:
                return ToolResult(
                    success=False,
                    error=result.stderr or result.stdout,
                )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"elf2image timed out after {self.timeout}s",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"elf2image failed: {e}",
            )


def create_esptool_tools(project_root: Path) -> dict[str, ESPTool]:
    """Create all esptool-related tools.

    Args:
        project_root: ESP-IDF project root directory.

    Returns:
        Dictionary of tool name to ESPTool instance.
    """
    return {
        "esptool_wrapper": ESPToolWrapper(project_root),
        "flash_tool": ESPFlashTool(project_root),
        "elf_tool": ELFTool(project_root),
    }
