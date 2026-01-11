"""ESP-IDF Project Detection Module.

Provides automatic detection and validation of ESP-IDF projects.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectInfo:
    """ESP-IDF project information.

    Attributes:
        root: Project root directory path.
        cmake_path: Path to CMakeLists.txt file.
        sdkconfig_path: Path to sdkconfig file.
        is_valid: Whether the project is valid.
    """

    root: Path
    cmake_path: Path
    sdkconfig_path: Path
    is_valid: bool = False

    @classmethod
    def detect(cls, cwd: Path | None = None) -> "ProjectInfo":
        """Detect if current directory is an ESP-IDF project.

        Args:
            cwd: Working directory, defaults to current directory.

        Returns:
            ProjectInfo instance.
        """
        work_dir = Path(cwd or os.getcwd())
        cmake_path = work_dir / "CMakeLists.txt"
        sdkconfig_path = work_dir / "sdkconfig"

        is_valid = cmake_path.exists()
        return cls(
            root=work_dir, cmake_path=cmake_path, sdkconfig_path=sdkconfig_path, is_valid=is_valid
        )

    def validate(self) -> tuple[bool, str]:
        """Validate project, returns (is_valid, message).

        Returns:
            Tuple of (is_valid, error_message or success_message).
        """
        if not self.cmake_path.exists():
            return (
                False,
                f"CMakeLists.txt not found, confirm this is ESP-IDF project directory: {self.root}",
            )

        # Check CMakeLists.txt content
        try:
            content = self.cmake_path.read_text()
            if (
                "cmake_minimum_required" not in content.lower()
                and "include(ESP-IDF)" not in content
            ):
                return (
                    False,
                    f"CMakeLists.txt does not appear to be ESP-IDF project file: {self.cmake_path}",
                )
        except Exception as e:
            return False, f"Cannot read CMakeLists.txt: {e}"

        return True, "Project validation passed"

    def get_error_suggestions(self) -> list[str]:
        """Provide suggestions based on error state.

        Returns:
            List of suggestion strings.
        """
        suggestions = []

        if not self.cmake_path.exists():
            suggestions.append("Check if you are in ESP-IDF project root directory")
            suggestions.append(f"Check parent directory: {self.root.parent / 'CMakeLists.txt'}")
            suggestions.append("Ensure project was initialized via ESP-IDF build system")

            # Check if parent directory has CMakeLists.txt
            parent_cmake = self.root.parent / "CMakeLists.txt"
            if parent_cmake.exists():
                suggestions.append(
                    f"Found CMakeLists.txt in parent directory, try: cd {self.root.parent}"
                )
        else:
            # CMakeLists.txt exists but content is wrong
            try:
                content = self.cmake_path.read_text()
                if "cmake_minimum_required" not in content.lower():
                    suggestions.append("CMakeLists.txt missing cmake_minimum_required declaration")
                if "include(ESP-IDF)" not in content:
                    suggestions.append("CMakeLists.txt missing ESP-IDF include statement")
                suggestions.append("Ensure this is an ESP-IDF project template created project")
            except Exception:
                suggestions.append("Cannot read CMakeLists.txt content, check file permissions")

        return suggestions
