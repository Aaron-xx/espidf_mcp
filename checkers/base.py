"""Checker system for ESP-IDF MCP workflow validation.

Provides base classes and utilities for validating workflow stages,
checking build artifacts, and ensuring project quality.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class CheckResult(Enum):
    """Result of a checker execution."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"


@dataclass
class CheckerReport:
    """Report from a checker execution.

    Attributes:
        checker_name: Name of the checker that ran.
        result: Check result status.
        message: Human-readable result message.
        details: Additional details about the check.
        suggestions: List of suggestions if check failed.
        metadata: Additional metadata.
    """

    checker_name: str
    result: CheckResult
    message: str
    details: str = ""
    suggestions: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def is_pass(self) -> bool:
        return self.result == CheckResult.PASS

    def is_fail(self) -> bool:
        return self.result == CheckResult.FAIL

    def is_warning(self) -> bool:
        return self.result == CheckResult.WARNING


class BaseChecker(ABC):
    """Base class for all checkers.

    Checkers validate workflow stages, build artifacts, and project quality.
    Each checker focuses on a specific validation concern.
    """

    # Checker metadata
    name: str = ""
    description: str = ""
    stage: str = ""  # Which workflow stage this checker applies to

    def __init__(self, project_root: Path | None = None):
        """Initialize checker.

        Args:
            project_root: Root directory of the ESP-IDF project.
        """
        self.project_root = project_root or Path.cwd()

    @abstractmethod
    def check(self) -> CheckerReport:
        """Execute the check.

        Returns:
            CheckerReport with validation results.
        """
        pass

    def _pass(self, message: str, details: str = "", **metadata) -> CheckerReport:
        """Create a passing report."""
        return CheckerReport(
            checker_name=self.name,
            result=CheckResult.PASS,
            message=message,
            details=details,
            metadata=metadata,
        )

    def _fail(
        self,
        message: str,
        details: str = "",
        suggestions: list[str] | None = None,
        **metadata,
    ) -> CheckerReport:
        """Create a failing report."""
        return CheckerReport(
            checker_name=self.name,
            result=CheckResult.FAIL,
            message=message,
            details=details,
            suggestions=suggestions or [],
            metadata=metadata,
        )

    def _warning(
        self,
        message: str,
        details: str = "",
        suggestions: list[str] | None = None,
        **metadata,
    ) -> CheckerReport:
        """Create a warning report."""
        return CheckerReport(
            checker_name=self.name,
            result=CheckResult.WARNING,
            message=message,
            details=details,
            suggestions=suggestions or [],
            metadata=metadata,
        )

    def _skip(self, message: str, details: str = "", **metadata) -> CheckerReport:
        """Create a skipped report."""
        return CheckerReport(
            checker_name=self.name,
            result=CheckResult.SKIP,
            message=message,
            details=details,
            metadata=metadata,
        )


class CheckerRegistry:
    """Registry for managing checkers.

    Provides checker registration, lookup, and batch execution.
    """

    def __init__(self):
        self._checkers: dict[str, type[BaseChecker]] = {}
        self._stage_map: dict[str, list[str]] = {}

    def register(self, checker_cls: type[BaseChecker]) -> "CheckerRegistry":
        """Register a checker class.

        Args:
            checker_cls: Checker class to register.

        Returns:
            Self for chaining.
        """
        name = checker_cls.name or checker_cls.__name__
        self._checkers[name] = checker_cls

        stage = checker_cls.stage if hasattr(checker_cls, "stage") else ""
        if stage:
            if stage not in self._stage_map:
                self._stage_map[stage] = []
            self._stage_map[stage].append(name)

        return self

    def get(self, name: str) -> type[BaseChecker] | None:
        """Get checker by name.

        Args:
            name: Checker name.

        Returns:
            Checker class or None.
        """
        return self._checkers.get(name)

    def get_for_stage(self, stage: str) -> list[type[BaseChecker]]:
        """Get all checkers for a specific stage.

        Args:
            stage: Workflow stage name.

        Returns:
            List of checker classes for the stage.
        """
        names = self._stage_map.get(stage, [])
        return [self._checkers[name] for name in names if name in self._checkers]

    def list_all(self) -> list[str]:
        """List all registered checker names."""
        return list(self._checkers.keys())

    def run_check(self, name: str, project_root: Path | None = None) -> CheckerReport:
        """Run a single checker by name.

        Args:
            name: Checker name.
            project_root: Project root directory.

        Returns:
            CheckerReport from the check.
        """
        checker_cls = self._checkers.get(name)
        if not checker_cls:
            return CheckerReport(
                checker_name="Registry",
                result=CheckResult.FAIL,
                message=f"Checker '{name}' not found",
            )

        checker = checker_cls(project_root=project_root)
        return checker.check()

    def run_stage_checks(self, stage: str, project_root: Path | None = None) -> list[CheckerReport]:
        """Run all checkers for a stage.

        Args:
            stage: Workflow stage name.
            project_root: Project root directory.

        Returns:
            List of CheckerReport objects.
        """
        checkers = self.get_for_stage(stage)
        reports = []
        for checker_cls in checkers:
            checker = checker_cls(project_root=project_root)
            reports.append(checker.check())
        return reports


# Built-in checkers for ESP-IDF projects


class ProjectStructureChecker(BaseChecker):
    """Check if project has valid ESP-IDF structure."""

    name = "project_structure"
    description = "Validates ESP-IDF project structure"
    stage = "init"

    def check(self) -> CheckerReport:
        """Check project structure."""
        cmake_path = self.project_root / "CMakeLists.txt"

        if not cmake_path.exists():
            return self._fail(
                message="CMakeLists.txt not found",
                details=f"Looked in: {self.project_root}",
                suggestions=[
                    "Ensure you are in an ESP-IDF project directory",
                    "Check parent directory for CMakeLists.txt",
                ],
            )

        try:
            content = cmake_path.read_text()
            if "cmake_minimum_required" not in content.lower():
                return self._fail(
                    message="CMakeLists.txt missing cmake_minimum_required",
                    details="File exists but does not appear to be a valid CMake file",
                )

            if "include(ESP-IDF)" not in content and "idf_component_register" not in content:
                return self._warning(
                    message="CMakeLists.txt may not be an ESP-IDF project file",
                    details="No ESP-IDF include or component registration found",
                )

            return self._pass(
                message="Project structure is valid",
                details=f"Found CMakeLists.txt at {cmake_path}",
            )

        except Exception as e:
            return self._fail(
                message="Failed to read CMakeLists.txt",
                details=str(e),
            )


class BuildArtifactsChecker(BaseChecker):
    """Check if build artifacts exist and are valid."""

    name = "build_artifacts"
    description = "Validates build artifacts exist"
    stage = "build"

    def check(self) -> CheckerReport:
        """Check build artifacts."""
        build_dir = self.project_root / "build"

        if not build_dir.exists():
            return self._fail(
                message="Build directory not found",
                details=f"Expected: {build_dir}",
                suggestions=["Run 'idf.py build' first"],
            )

        # Check for firmware binaries
        bin_files = list(build_dir.glob("**/*.bin"))
        if not bin_files:
            return self._fail(
                message="No firmware binaries found",
                details=f"No .bin files in {build_dir}",
                suggestions=["Build may have failed", "Check build output for errors"],
            )

        return self._pass(
            message="Build artifacts found",
            details=f"Found {len(bin_files)} .bin files in {build_dir}",
        )


class TargetConfigChecker(BaseChecker):
    """Check if ESP-IDF target is configured."""

    name = "target_config"
    description = "Validates ESP-IDF target chip configuration"
    stage = "config"

    def check(self) -> CheckerReport:
        """Check target configuration."""
        sdkconfig = self.project_root / "sdkconfig"

        if not sdkconfig.exists():
            return self._fail(
                message="sdkconfig not found",
                details=f"Expected: {sdkconfig}",
                suggestions=["Run 'idf.py set-target <chip>' first"],
            )

        try:
            content = sdkconfig.read_text()
            # Look for CONFIG_IDF_TARGET
            for line in content.splitlines():
                if line.startswith("CONFIG_IDF_TARGET="):
                    target = line.split("=")[1].strip('"')
                    return self._pass(
                        message=f"Target configured: {target}",
                        details=f"Found in {sdkconfig}",
                    )

            return self._warning(
                message="Target not explicitly set in sdkconfig",
                details="CONFIG_IDF_TARGET not found",
                suggestions=["Run 'idf.py set-target <chip>' to configure target"],
            )

        except Exception as e:
            return self._fail(
                message="Failed to read sdkconfig",
                details=str(e),
            )
