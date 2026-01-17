"""Exception hierarchy for ESP-IDF MCP Server.

Provides specific exception types for better error handling and reporting.
Allows external agents to catch and handle specific error scenarios.
"""


class ESPIDFError(Exception):
    """Base exception for all ESP-IDF MCP Server errors.

    All custom exceptions inherit from this base class, allowing
    external agents to catch all ESP-IDF related errors with a
    single except clause.

    Attributes:
        message: Human-readable error description.
        details: Additional error context (optional).
    """

    def __init__(self, message: str, details: str | None = None):
        """Initialize ESP-IDF error.

        Args:
            message: Human-readable error description.
            details: Additional error context.
        """
        self.message = message
        self.details = details
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with details."""
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class EnvironmentError(ESPIDFError):
    """Error in ESP-IDF environment configuration.

    Raised when the ESP-IDF environment is not properly configured
    or required tools are missing.

    Examples:
        - IDF_PATH not set or invalid
        - ESP-IDF version not compatible
        - Required tools (idf.py, esptool.py) not found
        - Cross-compiler toolchain missing
    """

    pass


class BuildError(ESPIDFError):
    """Error during firmware build process.

    Raised when compilation, linking, or other build steps fail.

    Examples:
        - Compilation errors in source code
        - Linker errors (memory overflow, undefined symbols)
        - Missing dependencies or components
        - Invalid configuration
    """

    pass


class ConfigurationError(ESPIDFError):
    """Error in project or tool configuration.

    Raised when configuration settings are invalid or inconsistent.

    Examples:
        - Invalid target chip specified
        - Corrupted sdkconfig file
        - Invalid partition table
        - Missing required configuration files
    """

    pass


class HardwareError(ESPIDFError):
    """Error related to hardware connection or operation.

    Raised when interacting with ESP32 hardware devices fails.

    Examples:
        - Device not found or not connected
        - USB port permissions issue
        - Device not in download mode
        - Flash write failure
        - MAC address read failure
    """

    pass


class FlashError(HardwareError):
    """Error during firmware flashing operation.

    Specific subtype of HardwareError for flash-related failures.

    Examples:
        - Connection timeout
        - Write failure
        - Verification failure
        - Wrong chip type detected
    """

    pass


class MonitorError(HardwareError):
    """Error during serial monitor operation.

    Specific subtype of HardwareError for serial monitor failures.

    Examples:
        - Port open failure
        - Baud rate mismatch
        - Connection lost during monitoring
    """

    pass


class PermissionError(ESPIDFError):
    """Error due to insufficient permissions.

    Raised when an operation is not allowed due to permission
    restrictions or security policies.

    Examples:
        - File system operation not in whitelist
        - Resource limit exceeded
        - Protected file access denied
    """

    pass


class ResourceError(ESPIDFError):
    """Error due to resource limit violation.

    Raised when tool execution exceeds configured resource limits.

    Examples:
        - Memory usage exceeded
        - Execution timeout exceeded
        - Disk usage exceeded
    """

    pass


class ValidationError(ESPIDFError):
    """Error during input or output validation.

    Raised when validation checks fail.

    Examples:
        - Invalid parameter value
        - Missing required parameter
        - Path validation failure
        - Firmware artifact verification failure
    """

    pass


class WorkflowError(ESPIDFError):
    """Error in workflow state or execution.

    Raised when workflow operations fail due to state issues.

    Examples:
        - Stage dependency not satisfied
        - Invalid workflow state transition
        - Stage execution failure
    """

    pass


class PrerequisiteError(ESPIDFError):
    """前置条件未满足时的错误。

    这类错误是"已知的"和"可恢复的"：
    - 包含明确的修复命令
    - 测试遇到时应该 SKIP 而非 FAIL（使用 @skip_on_known_errors 装饰器）
    - 用户看到的是有用的提示而非报错

    Examples:
        - Build directory not found
        - Target chip not configured
        - Required artifacts missing
    """

    pass


class BuildRequiredError(PrerequisiteError):
    """需要先构建的错误 - build 目录或固件不存在。

    当工具需要构建产物但 build 目录不存在时抛出。
    包含修复命令和详细说明。

    Attributes:
        build_dir: 缺失的构建目录路径
        fix_command: 修复命令
    """

    def __init__(self, build_dir: str, details: str | None = None):
        """Initialize build required error.

        Args:
            build_dir: 缺失的构建目录路径
            details: 额外详情
        """
        self.build_dir = build_dir
        self.fix_command = "idf.py build"
        super().__init__(f"Build required: {build_dir} not found", details)


# Map error types to user-friendly descriptions
ERROR_DESCRIPTIONS = {
    "EnvironmentError": "ESP-IDF environment configuration issue",
    "BuildError": "Firmware build compilation/linking error",
    "ConfigurationError": "Project or tool configuration error",
    "HardwareError": "Hardware connection or operation error",
    "FlashError": "Firmware flashing operation error",
    "MonitorError": "Serial monitor operation error",
    "PermissionError": "Permission or security policy violation",
    "ResourceError": "Resource limit exceeded",
    "ValidationError": "Input or output validation failure",
    "WorkflowError": "Workflow state or execution error",
    "PrerequisiteError": "Prerequisite condition not met",
    "BuildRequiredError": "Build artifacts required but not found",
}


def get_error_description(error: Exception) -> str:
    """Get user-friendly description for an error.

    Args:
        error: Exception instance.

    Returns:
        User-friendly error description.

    Example:
        >>> try:
        ...     raise BuildError("Compilation failed")
        ... except ESPIDFError as e:
        ...     print(get_error_description(e))
        Firmware build compilation/linking error
    """
    error_type = type(error).__name__
    return ERROR_DESCRIPTIONS.get(error_type, "Unknown error type")


def get_error_suggestion(error: Exception) -> str | None:
    """Get actionable suggestion for resolving an error.

    Args:
        error: Exception instance.

    Returns:
        Actionable suggestion or None if no specific suggestion available.

    Example:
        >>> try:
        ...     raise EnvironmentError("IDF_PATH not set")
        ... except ESPIDFError as e:
        ...     print(get_error_suggestion(e))
        Source the ESP-IDF export script: source ~/esp/esp-idf/export.sh
    """
    if isinstance(error, EnvironmentError):
        return "Check ESP-IDF environment: source ~/esp/esp-idf/export.sh"

    if isinstance(error, BuildError):
        if "memory" in str(error).lower():
            return "Reduce code size or adjust partition table"
        return "Check source code and configuration"

    # Check specific hardware error types before generic HardwareError
    # because FlashError and MonitorError are subclasses of HardwareError
    if isinstance(error, FlashError):
        return "Check device is in download mode, try lower baud rate"

    if isinstance(error, MonitorError):
        return "Check port is not in use, verify baud rate"

    if isinstance(error, HardwareError):
        return "Check USB connection and device power"

    if isinstance(error, PermissionError):
        return "Check file permissions and operation whitelist"

    if isinstance(error, ResourceError):
        return "Reduce resource usage or adjust limits"

    if isinstance(error, ConfigurationError):
        return "Run 'idf.py menuconfig' to fix configuration"

    if isinstance(error, ValidationError):
        return "Check input parameters and try again"

    if isinstance(error, WorkflowError):
        return "Check workflow state and stage dependencies"

    # Prerequisite errors should come after specific error types
    # since BuildRequiredError is a subclass of PrerequisiteError
    if isinstance(error, BuildRequiredError):
        return f"Build firmware first: {error.fix_command}"

    if isinstance(error, PrerequisiteError):
        return "Check prerequisites and fix missing dependencies"

    return None
