"""Unit tests for exception hierarchy and error handling."""

from mcp_tools.exceptions import (
    BuildError,
    ConfigurationError,
    EnvironmentError,
    ESPIDFError,
    FlashError,
    HardwareError,
    MonitorError,
    PermissionError,
    ResourceError,
    ValidationError,
    WorkflowError,
    get_error_description,
    get_error_suggestion,
)


class TestESPIDFError:
    """Test base ESPIDFError class."""

    def test_error_creation(self):
        """Test creating an ESP-IDF error."""
        error = ESPIDFError("Test error")
        assert error.message == "Test error"
        assert error.details is None
        assert "Test error" in str(error)

    def test_error_with_details(self):
        """Test creating an error with details."""
        error = ESPIDFError("Test error", details="Additional context")
        assert error.message == "Test error"
        assert error.details == "Additional context"
        assert "Additional context" in str(error)

    def test_format_message_without_details(self):
        """Test message formatting without details."""
        error = ESPIDFError("Test error")
        assert error._format_message() == "Test error"

    def test_format_message_with_details(self):
        """Test message formatting with details."""
        error = ESPIDFError("Test error", details="Details here")
        assert error._format_message() == "Test error: Details here"


class TestSpecificErrorTypes:
    """Test specific error type subclasses."""

    def test_environment_error(self):
        """Test EnvironmentError is ESPIDFError subclass."""
        error = EnvironmentError("IDF_PATH not set")
        assert isinstance(error, ESPIDFError)
        assert isinstance(error, Exception)

    def test_build_error(self):
        """Test BuildError is ESPIDFError subclass."""
        error = BuildError("Compilation failed")
        assert isinstance(error, ESPIDFError)

    def test_configuration_error(self):
        """Test ConfigurationError is ESPIDFError subclass."""
        error = ConfigurationError("Invalid target")
        assert isinstance(error, ESPIDFError)

    def test_hardware_error(self):
        """Test HardwareError is ESPIDFError subclass."""
        error = HardwareError("Device not found")
        assert isinstance(error, ESPIDFError)

    def test_flash_error_is_hardware_error(self):
        """Test FlashError is HardwareError subclass."""
        error = FlashError("Flash write failed")
        assert isinstance(error, HardwareError)
        assert isinstance(error, ESPIDFError)

    def test_monitor_error_is_hardware_error(self):
        """Test MonitorError is HardwareError subclass."""
        error = MonitorError("Port busy")
        assert isinstance(error, HardwareError)
        assert isinstance(error, ESPIDFError)

    def test_permission_error(self):
        """Test PermissionError is ESPIDFError subclass."""
        error = PermissionError("Access denied")
        assert isinstance(error, ESPIDFError)

    def test_resource_error(self):
        """Test ResourceError is ESPIDFError subclass."""
        error = ResourceError("Memory limit exceeded")
        assert isinstance(error, ESPIDFError)

    def test_validation_error(self):
        """Test ValidationError is ESPIDFError subclass."""
        error = ValidationError("Invalid parameter")
        assert isinstance(error, ESPIDFError)

    def test_workflow_error(self):
        """Test WorkflowError is ESPIDFError subclass."""
        error = WorkflowError("Stage not ready")
        assert isinstance(error, ESPIDFError)


class TestErrorDescriptions:
    """Test error description mapping."""

    def test_environment_error_description(self):
        """Test EnvironmentError description."""
        error = EnvironmentError("IDF_PATH not set")
        description = get_error_description(error)
        assert "environment" in description.lower()

    def test_build_error_description(self):
        """Test BuildError description."""
        error = BuildError("Compilation failed")
        description = get_error_description(error)
        assert "build" in description.lower()

    def test_configuration_error_description(self):
        """Test ConfigurationError description."""
        error = ConfigurationError("Invalid target")
        description = get_error_description(error)
        assert "configuration" in description.lower()

    def test_hardware_error_description(self):
        """Test HardwareError description."""
        error = HardwareError("Device not found")
        description = get_error_description(error)
        assert "hardware" in description.lower()

    def test_flash_error_description(self):
        """Test FlashError description."""
        error = FlashError("Flash write failed")
        description = get_error_description(error)
        assert "flash" in description.lower()

    def test_monitor_error_description(self):
        """Test MonitorError description."""
        error = MonitorError("Port busy")
        description = get_error_description(error)
        assert "monitor" in description.lower()

    def test_permission_error_description(self):
        """Test PermissionError description."""
        error = PermissionError("Access denied")
        description = get_error_description(error)
        assert "permission" in description.lower()

    def test_resource_error_description(self):
        """Test ResourceError description."""
        error = ResourceError("Memory limit exceeded")
        description = get_error_description(error)
        assert "resource" in description.lower()

    def test_validation_error_description(self):
        """Test ValidationError description."""
        error = ValidationError("Invalid parameter")
        description = get_error_description(error)
        assert "validation" in description.lower()

    def test_workflow_error_description(self):
        """Test WorkflowError description."""
        error = WorkflowError("Stage not ready")
        description = get_error_description(error)
        assert "workflow" in description.lower()

    def test_unknown_error_description(self):
        """Test unknown error type description."""
        error = Exception("Unknown error")
        description = get_error_description(error)
        assert "unknown" in description.lower()


class TestErrorSuggestions:
    """Test error suggestion generation."""

    def test_environment_error_suggestion(self):
        """Test EnvironmentError suggestion."""
        error = EnvironmentError("IDF_PATH not set")
        suggestion = get_error_suggestion(error)
        assert suggestion is not None
        assert "export.sh" in suggestion

    def test_build_error_suggestion(self):
        """Test BuildError suggestion."""
        error = BuildError("Compilation failed")
        suggestion = get_error_suggestion(error)
        assert suggestion is not None

    def test_build_error_memory_suggestion(self):
        """Test BuildError memory-related suggestion."""
        error = BuildError("Memory overflow")
        suggestion = get_error_suggestion(error)
        assert "partition" in suggestion.lower()

    def test_hardware_error_suggestion(self):
        """Test HardwareError suggestion."""
        error = HardwareError("Device not found")
        suggestion = get_error_suggestion(error)
        assert suggestion is not None
        assert "usb" in suggestion.lower() or "connection" in suggestion.lower()

    def test_flash_error_suggestion(self):
        """Test FlashError suggestion."""
        error = FlashError("Connection timeout")
        suggestion = get_error_suggestion(error)
        assert suggestion is not None
        assert "download" in suggestion.lower() or "baud" in suggestion.lower()

    def test_monitor_error_suggestion(self):
        """Test MonitorError suggestion."""
        error = MonitorError("Port busy")
        suggestion = get_error_suggestion(error)
        assert suggestion is not None
        assert "port" in suggestion.lower() or "baud" in suggestion.lower()

    def test_permission_error_suggestion(self):
        """Test PermissionError suggestion."""
        error = PermissionError("Access denied")
        suggestion = get_error_suggestion(error)
        assert suggestion is not None
        assert "permission" in suggestion.lower()

    def test_resource_error_suggestion(self):
        """Test ResourceError suggestion."""
        error = ResourceError("Memory limit exceeded")
        suggestion = get_error_suggestion(error)
        assert suggestion is not None
        assert "resource" in suggestion.lower() or "limit" in suggestion.lower()

    def test_configuration_error_suggestion(self):
        """Test ConfigurationError suggestion."""
        error = ConfigurationError("Invalid target")
        suggestion = get_error_suggestion(error)
        assert suggestion is not None
        assert "menuconfig" in suggestion

    def test_validation_error_suggestion(self):
        """Test ValidationError suggestion."""
        error = ValidationError("Invalid parameter")
        suggestion = get_error_suggestion(error)
        assert suggestion is not None
        assert "parameter" in suggestion.lower()

    def test_workflow_error_suggestion(self):
        """Test WorkflowError suggestion."""
        error = WorkflowError("Stage not ready")
        suggestion = get_error_suggestion(error)
        assert suggestion is not None
        assert "workflow" in suggestion.lower() or "stage" in suggestion.lower()

    def test_unknown_error_no_suggestion(self):
        """Test unknown error type returns no suggestion."""
        error = Exception("Unknown error")
        suggestion = get_error_suggestion(error)
        assert suggestion is None


class TestExceptionCatching:
    """Test exception catching patterns."""

    def test_catch_all_espidf_errors(self):
        """Test catching all ESP-IDF errors with base class."""
        errors = [
            EnvironmentError("test"),
            BuildError("test"),
            ConfigurationError("test"),
            HardwareError("test"),
            FlashError("test"),
            MonitorError("test"),
            PermissionError("test"),
            ResourceError("test"),
            ValidationError("test"),
            WorkflowError("test"),
        ]

        caught = []
        for error in errors:
            try:
                raise error
            except ESPIDFError as e:
                caught.append(e)

        assert len(caught) == len(errors)

    def test_catch_specific_hardware_errors(self):
        """Test catching hardware errors with specific subclass."""
        errors = [
            FlashError("test"),
            MonitorError("test"),
        ]

        caught = []
        for error in errors:
            try:
                raise error
            except HardwareError as e:
                caught.append(e)

        assert len(caught) == len(errors)

    def test_non_espidf_error_not_caught(self):
        """Test non-ESP-IDF errors are not caught by ESPIDFError."""
        caught = False
        try:
            raise ValueError("Not an ESP-IDF error")
        except ESPIDFError:
            caught = True
        except ValueError:
            pass

        assert not caught
