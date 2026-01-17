"""Error pattern recognition and diagnostic suggestions.

Provides intelligent error analysis and fix recommendations for ESP-IDF development.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ErrorPattern:
    """Error pattern definition for matching and diagnostics.

    Attributes:
        name: Unique pattern identifier.
        patterns: List of regex patterns to match.
        category: Error category (environment, build, flash, hardware, etc).
        suggestions: List of actionable fix suggestions.
        severity: Error severity level (error, warning, info).
    """

    name: str
    patterns: list[str]
    category: str
    suggestions: list[str]
    severity: str = "error"

    def matches(self, error_output: str) -> bool:
        """Check if error output matches any pattern.

        Args:
            error_output: Error text to match against.

        Returns:
            True if any pattern matches.
        """
        for pattern in self.patterns:
            try:
                if re.search(pattern, error_output, re.IGNORECASE):
                    return True
            except re.error:
                # Invalid regex, skip
                continue
        return False


@dataclass
class DiagnosticResult:
    """Result of error diagnosis.

    Attributes:
        matched_patterns: List of matched pattern names.
        category: Error category.
        suggestions: List of fix suggestions.
        severity: Maximum severity among matches.
        confidence: Confidence score (0.0 to 1.0).
    """

    matched_patterns: list[str]
    category: str
    suggestions: list[str]
    severity: str
    confidence: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "matched_patterns": self.matched_patterns,
            "category": self.category,
            "suggestions": self.suggestions,
            "severity": self.severity,
            "confidence": self.confidence,
        }


class DiagnosticEngine:
    """Error pattern recognition and suggestion engine.

    Matches error output against known patterns and provides
    actionable fix suggestions.

    Example:
        diagnostics = get_diagnostics()

        # Diagnose error
        result = diagnostics.diagnose("IDF_PATH not set")
        print(f"Category: {result['category']}")
        print(f"Suggestions: {result['suggestions']}")

        # Add custom pattern
        custom = ErrorPattern(
            name="my_error",
            patterns=[r"My specific error"],
            category="custom",
            suggestions=["Fix it this way"]
        )
        diagnostics.add_custom_pattern(custom)
    """

    # Built-in error patterns for common ESP-IDF issues
    PATTERNS = [
        # Environment errors
        ErrorPattern(
            name="idf_path_not_set",
            patterns=[
                r"IDF_PATH.*not set",
                r"Cannot find ESP-IDF",
                r"esp-idf not found",
                r"IDF_PATH.*environment variable",
            ],
            category="environment",
            suggestions=[
                "Source ESP-IDF export script: source ~/esp/esp-idf/export.sh",
                "Install ESP-IDF: https://docs.espressif.com/projects/esp-idf/en/latest/get-started/index.html",
                "Check IDF_PATH environment variable: echo $IDF_PATH",
                "Add export to ~/.bashrc or ~/.zshrc for persistence",
            ],
            severity="error",
        ),
        ErrorPattern(
            name="python_version_mismatch",
            patterns=[
                r"Python .* too old",
                r"requires Python .* or higher",
                r"unsupported Python version",
            ],
            category="environment",
            suggestions=[
                "Update Python to 3.8 or higher",
                "Use python3.8 or later: python3 --version",
                "Create virtual environment with correct Python version",
                "Check ESP-IDF Python requirements",
            ],
            severity="error",
        ),
        # Build errors
        ErrorPattern(
            name="memory_overflow",
            patterns=[
                r"region.*overflow",
                r"section.*will not fit",
                r"out of memory",
                r"IRAM.*overflow",
                r"DRAM.*overflow",
                r"region .* truncated",
            ],
            category="build",
            suggestions=[
                "Reduce component size or remove unused features",
                "Move constants to flash using 'const' keyword",
                "Check partition table: idf.py partition-table",
                "Analyze firmware size: idf.py size",
                "Adjust component dependencies in sdkconfig",
                "Enable optimizations: CONFIG_OPTIMIZATION_LEVEL in sdkconfig",
            ],
            severity="error",
        ),
        ErrorPattern(
            name="compile_error",
            patterns=[
                r"error:.*undefined reference",
                r"fatal error:.*No such file",
                r"compilation terminated",
                r"'.*' does not exist",
                r"No such file or directory",
            ],
            category="build",
            suggestions=[
                "Check for missing includes or typos",
                "Verify component dependencies in CMakeLists.txt",
                "Clean build: idf.py fullclean",
                "Check syntax errors in modified files",
                "Verify component registration in CMakeLists.txt",
            ],
            severity="error",
        ),
        ErrorPattern(
            name="linker_error",
            patterns=[
                r"undefined reference",
                r"linker command failed",
                r"ld returned",
                r"multiple definition",
            ],
            category="build",
            suggestions=[
                "Check for missing source files in CMakeLists.txt",
                "Verify all required libraries are linked",
                "Check for duplicate symbols in code",
                "Clean build: idf.py fullclean && idf.py build",
                "Review component dependencies",
            ],
            severity="error",
        ),
        ErrorPattern(
            name="config_error",
            patterns=[
                r"sdkconfig.*error",
                r"CONFIG_.*not set",
                r"undefined configuration",
                r"missing config option",
            ],
            category="build",
            suggestions=[
                "Run menuconfig: idf.py menuconfig",
                "Check sdkconfig file exists and is valid",
                "Clean build after config changes",
                "Review required config options for project",
            ],
            severity="error",
        ),
        # Hardware/Port errors
        ErrorPattern(
            name="port_not_found",
            patterns=[
                r"Failed to connect",
                r"Port not found",
                r"No serial port",
                r"Permission denied.*dev/tty",
                r"could not open port",
                r"serial\.util\.SerialException",
            ],
            category="hardware",
            suggestions=[
                "Check USB cable connection",
                "Verify device is powered on",
                "Check serial permissions: sudo usermod -a -G dialout $USER",
                "List available ports: espidf-mcp --list-ports (or esp_list_ports)",
                "Try different USB cable or port",
                "Check if another program is using the port",
            ],
            severity="error",
        ),
        ErrorPattern(
            name="port_permission_denied",
            patterns=[
                r"Permission denied",
                r"access denied.*tty",
                r"could not open port.*denied",
                r"errno 13",
            ],
            category="hardware",
            suggestions=[
                "Add user to dialout group: sudo usermod -a -G dialout $USER",
                "Log out and log back in for group change to take effect",
                "Use sudo (not recommended for development)",
                "Check udev rules for serial port",
            ],
            severity="error",
        ),
        # Flash errors
        ErrorPattern(
            name="flash_write_error",
            patterns=[
                r"Failed to write",
                r"Write failed",
                r"Packet content transfer stops",
                r"timeout while waiting for packet header",
            ],
            category="flash",
            suggestions=[
                "Reduce baud rate: try 115200 instead of 460800",
                "Check USB cable quality (use short, shielded cable)",
                "Verify device is in bootloader mode",
                "Try manual download mode: hold BOOT button, press RESET",
                "Check power supply stability",
                "Try different USB port (direct connection, not through hub)",
            ],
            severity="warning",
        ),
        ErrorPattern(
            name="flash_size_mismatch",
            patterns=[
                r"flash size mismatch",
                r"detected size.*not matching",
                r"wrong flash size",
            ],
            category="flash",
            suggestions=[
                "Set correct flash size in menuconfig",
                "Check 'Flash size' option under 'Serial Flasher Config'",
                "Verify flash size matches your hardware",
                "Re-run menuconfig after changing flash size",
            ],
            severity="warning",
        ),
        ErrorPattern(
            name="connection_lost",
            patterns=[
                r"Lost connection",
                r"Connection lost",
                r"device disconnected",
                r"uart error",
            ],
            category="hardware",
            suggestions=[
                "Check USB cable connection",
                "Verify device power supply",
                "Try different USB port",
                "Check for loose connections",
                "Reduce baud rate",
            ],
            severity="warning",
        ),
        # Component errors
        ErrorPattern(
            name="component_not_found",
            patterns=[
                r"Component.*not found",
                r"unknown component",
                r"component.*does not exist",
                r"no such component",
            ],
            category="build",
            suggestions=[
                "Register component in CMakeLists.txt",
                "Check component directory structure",
                "Verify COMPONENT_SRCS and COMPONENT_PRIV_INCLUDED_SRVS",
                "Run idf.py fullclean and rebuild",
            ],
            severity="error",
        ),
        ErrorPattern(
            name="dependency_error",
            patterns=[
                r"unsatisfied dependency",
                r"dependency.*not found",
                r"required component.*missing",
            ],
            category="build",
            suggestions=[
                "Add required component to COMPONENT_REQUIRES in CMakeLists.txt",
                "Check component dependencies",
                "Update component registration",
                "Run idf.py reconfigure",
            ],
            severity="error",
        ),
    ]

    def __init__(self, custom_patterns: list[ErrorPattern] | None = None):
        """Initialize diagnostic engine with built-in patterns.

        Args:
            custom_patterns: Additional custom patterns to add.
        """
        self.patterns = list(self.PATTERNS)

        if custom_patterns:
            for pattern in custom_patterns:
                self.add_custom_pattern(pattern)

    def diagnose(self, error_output: str, context: dict | None = None) -> DiagnosticResult:
        """Analyze error output and return diagnostic report.

        Args:
            error_output: Error text to analyze.
            context: Optional additional context (command, args, etc).

        Returns:
            DiagnosticResult with matched patterns and suggestions.
        """
        matched_patterns = []
        all_suggestions = []
        categories = set()
        severity_level = {"info": 0, "warning": 1, "error": 2}
        max_severity = 0

        # Match against all patterns
        for pattern in self.patterns:
            if pattern.matches(error_output):
                matched_patterns.append(pattern.name)
                categories.add(pattern.category)
                all_suggestions.extend(pattern.suggestions)

                # Track maximum severity
                severity_val = severity_level.get(pattern.severity, 0)
                if severity_val > max_severity:
                    max_severity = severity_val

        # Determine severity
        severity_names = {0: "info", 1: "warning", 2: "error"}
        severity = severity_names.get(max_severity, "info")

        # Calculate confidence based on number of matches
        confidence = min(1.0, len(matched_patterns) * 0.3)

        # Remove duplicate suggestions while preserving order
        seen = set()
        unique_suggestions = []
        for s in all_suggestions:
            if s not in seen:
                unique_suggestions.append(s)
                seen.add(s)

        # Determine category (use most common if multiple)
        if categories:
            # Prioritize: environment > build > flash > hardware
            priority = ["environment", "build", "flash", "hardware", "config"]
            for cat in priority:
                if cat in categories:
                    category = cat
                    break
            else:
                category = list(categories)[0]
        else:
            category = "unknown"

        return DiagnosticResult(
            matched_patterns=matched_patterns,
            category=category,
            suggestions=unique_suggestions,
            severity=severity,
            confidence=confidence,
        )

    def add_custom_pattern(self, pattern: ErrorPattern) -> None:
        """Add custom error pattern.

        Args:
            pattern: ErrorPattern to add.
        """
        # Check for duplicate name
        if any(p.name == pattern.name for p in self.patterns):
            # Replace existing
            self.patterns = [p for p in self.patterns if p.name != pattern.name]

        self.patterns.append(pattern)

    def get_suggestions_for_error(self, error_message: str) -> list[str]:
        """Get actionable suggestions for an error message.

        Convenience method that returns just the suggestions.

        Args:
            error_message: Error message text.

        Returns:
            List of suggestion strings.
        """
        result = self.diagnose(error_message)
        return result.suggestions

    def get_all_patterns(self) -> list[ErrorPattern]:
        """Get all registered error patterns.

        Returns:
            List of all ErrorPattern instances.
        """
        return list(self.patterns)

    def get_patterns_by_category(self, category: str) -> list[ErrorPattern]:
        """Get patterns for a specific category.

        Args:
            category: Category name (build, flash, hardware, etc).

        Returns:
            List of ErrorPattern instances in the category.
        """
        return [p for p in self.patterns if p.category == category]


class DiagnosticContext:
    """Capture and preserve error context for better diagnostics.

    Attributes:
        command: Command that was executed.
        args: Command arguments.
        cwd: Current working directory.
        env_vars: Environment variables (sanitized).
    """

    def __init__(
        self,
        command: str,
        args: dict | None = None,
        cwd: Path | None = None,
        env: dict | None = None,
    ):
        """Initialize error context.

        Args:
            command: Command that was executed.
            args: Command arguments.
            cwd: Current working directory.
            env: Environment variables (will be sanitized).
        """
        self.command = command
        self.args = args or {}
        self.cwd = Path(cwd) if cwd else Path.cwd()
        self.env_vars = self._sanitize_env(env) if env else {}

    def capture(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration: float,
    ) -> dict:
        """Capture complete execution context for diagnostics.

        Args:
            stdout: Standard output.
            stderr: Standard error.
            exit_code: Process exit code.
            duration: Execution duration in seconds.

        Returns:
            Dictionary with full context.
        """
        from datetime import datetime

        return {
            "timestamp": datetime.now().isoformat(),
            "command": self.command,
            "args": self.args,
            "cwd": str(self.cwd),
            "exit_code": exit_code,
            "duration": duration,
            "stdout": stdout[:1000],  # Truncate
            "stderr": stderr[:1000],  # Truncate
            "env_vars": self.env_vars,
        }

    @staticmethod
    def _sanitize_env(env: dict) -> dict:
        """Remove sensitive values from environment.

        Args:
            env: Environment variables dictionary.

        Returns:
            Sanitized environment dict.
        """
        # Patterns for sensitive keys
        sensitive_patterns = [
            "TOKEN",
            "PASSWORD",
            "SECRET",
            "KEY",
            "AUTH",
            "CREDENTIAL",
        ]

        sanitized = {}
        for key, value in env.items():
            # Check if key contains sensitive pattern
            if any(pattern in key.upper() for pattern in sensitive_patterns):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value

        return sanitized

    def to_dict(self) -> dict:
        """Convert context to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "command": self.command,
            "args": self.args,
            "cwd": str(self.cwd),
            "env_vars": self.env_vars,
        }
