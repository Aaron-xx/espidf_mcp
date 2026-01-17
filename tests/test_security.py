"""Unit tests for security and resource limit features."""

import pytest

from config import ResourceLimits, SecurityConfig, ToolTimeouts, get_default_config
from config.permissions import Operation, OperationWhitelist, PathRule
from mcp_tools.base import ResourceMonitor


class TestResourceLimits:
    """Test ResourceLimits configuration."""

    def test_default_limits(self):
        """Test default resource limit values."""
        limits = ResourceLimits()
        assert limits.max_memory_mb == 1024
        assert limits.max_execution_time == 600
        assert limits.max_disk_usage_mb == 2048
        assert limits.max_subprocesses == 5
        assert limits.enable_monitoring is True

    def test_custom_limits(self):
        """Test custom resource limit values."""
        limits = ResourceLimits(
            max_memory_mb=512,
            max_execution_time=300,
            max_disk_usage_mb=1024,
        )
        assert limits.max_memory_mb == 512
        assert limits.max_execution_time == 300
        assert limits.max_disk_usage_mb == 1024

    def test_disable_monitoring(self):
        """Test disabling resource monitoring."""
        limits = ResourceLimits(enable_monitoring=False)
        assert limits.enable_monitoring is False


class TestToolTimeouts:
    """Test ToolTimeouts configuration."""

    def test_default_timeouts(self):
        """Test default timeout values."""
        timeouts = ToolTimeouts()
        assert timeouts.build == 600
        assert timeouts.flash == 600
        assert timeouts.monitor == 1200
        assert timeouts.clean == 60
        assert timeouts.size == 30
        assert timeouts.default == 60

    def test_get_timeout_known_tool(self):
        """Test getting timeout for known tools."""
        timeouts = ToolTimeouts()
        assert timeouts.get_timeout("esp_build") == 600
        assert timeouts.get_timeout("esp_flash") == 600
        assert timeouts.get_timeout("esp_monitor") == 1200
        assert timeouts.get_timeout("esp_clean") == 60
        assert timeouts.get_timeout("esp_size") == 30

    def test_get_timeout_unknown_tool(self):
        """Test getting timeout for unknown tools returns default."""
        timeouts = ToolTimeouts()
        assert timeouts.get_timeout("esp_unknown_tool") == 60
        assert timeouts.get_timeout("random_tool") == 60

    def test_get_timeout_without_prefix(self):
        """Test timeout lookup works without esp_ prefix."""
        timeouts = ToolTimeouts()
        assert timeouts.get_timeout("build") == 600
        assert timeouts.get_timeout("flash") == 600
        assert timeouts.get_timeout("monitor") == 1200


class TestSecurityConfig:
    """Test SecurityConfig configuration."""

    def test_default_security_config(self):
        """Test default security configuration."""
        config = SecurityConfig()
        assert isinstance(config.resource_limits, ResourceLimits)
        assert isinstance(config.timeouts, ToolTimeouts)
        assert config.strict_mode is False

    def test_custom_security_config(self):
        """Test custom security configuration."""
        limits = ResourceLimits(max_memory_mb=512)
        timeouts = ToolTimeouts(build=300)
        config = SecurityConfig(resource_limits=limits, timeouts=timeouts, strict_mode=True)
        assert config.resource_limits.max_memory_mb == 512
        assert config.timeouts.build == 300
        assert config.strict_mode is True

    def test_get_default_config(self):
        """Test get_default_config factory function."""
        config = get_default_config()
        assert isinstance(config, SecurityConfig)
        assert config.resource_limits.enable_monitoring is True


class TestOperationWhitelist:
    """Test OperationWhitelist permission system."""

    @pytest.fixture
    def project_root(self, tmp_path):
        """Create a temporary project root."""
        return tmp_path / "project"

    @pytest.fixture
    def whitelist(self, project_root):
        """Create an operation whitelist for testing."""
        return OperationWhitelist(project_root=project_root, strict_mode=True)

    def test_default_path_rules(self, project_root):
        """Test default path rules are configured."""
        whitelist = OperationWhitelist(project_root=project_root)
        assert len(whitelist.path_rules) > 0
        assert any("build" in rule.path_pattern for rule in whitelist.path_rules)
        assert any("main" in rule.path_pattern for rule in whitelist.path_rules)

    def test_check_operation_allowed_path(self, whitelist, project_root):
        """Test operation check on allowed path."""
        # build directory allows read, write, delete
        build_dir = project_root / "build" / "test.txt"
        assert whitelist.check_operation("read", build_dir) is True
        assert whitelist.check_operation("write", build_dir) is True
        assert whitelist.check_operation("delete", build_dir) is True

    def test_check_operation_disallowed_operation(self, whitelist, project_root):
        """Test operation check for disallowed operation."""
        # build directory does not allow execute
        build_dir = project_root / "build" / "script.sh"
        assert whitelist.check_operation("execute", build_dir) is False

    def test_check_operation_outside_allowed_paths(self, whitelist, tmp_path):
        """Test operation check outside allowed paths in strict mode."""
        outside_path = tmp_path / "outside" / "test.txt"
        assert whitelist.check_operation("read", outside_path) is False

    def test_check_operation_non_strict_mode(self, project_root):
        """Test operation check in non-strict mode allows project root."""
        whitelist = OperationWhitelist(project_root=project_root, strict_mode=False)
        # In non-strict mode, paths within project root are allowed
        custom_dir = project_root / "custom" / "test.txt"
        assert whitelist.check_operation("read", custom_dir) is True

    def test_custom_path_rules(self, project_root):
        """Test custom path rules."""
        custom_rules = [
            PathRule(
                path_pattern="{project_root}/custom",
                allowed_operations=["read", "write"],
                description="Custom directory",
            )
        ]
        whitelist = OperationWhitelist(project_root=project_root, path_rules=custom_rules)
        custom_dir = project_root / "custom" / "test.txt"
        assert whitelist.check_operation("read", custom_dir) is True
        assert whitelist.check_operation("write", custom_dir) is True
        assert whitelist.check_operation("delete", custom_dir) is False

    def test_get_allowed_paths_summary(self, whitelist):
        """Test getting allowed paths summary."""
        summary = whitelist.get_allowed_paths_summary()
        assert "Operation Whitelist" in summary
        assert "build" in summary
        assert "Operations:" in summary


class TestResourceMonitor:
    """Test ResourceMonitor functionality."""

    def test_resource_monitor_initialization(self):
        """Test resource monitor initialization."""
        monitor = ResourceMonitor(max_memory_mb=512, max_execution_time=300)
        assert monitor.max_memory_mb == 512
        assert monitor.max_execution_time == 300
        assert monitor.start_time is None
        assert monitor.start_memory is None

    def test_resource_monitor_start(self):
        """Test starting resource monitoring."""
        monitor = ResourceMonitor()
        monitor.start()
        assert monitor.start_time is not None
        # start_memory may be None if psutil is not available

    def test_get_usage_summary(self):
        """Test getting resource usage summary."""
        monitor = ResourceMonitor()
        summary = monitor.get_usage_summary()
        assert "monitoring_enabled" in summary
        assert isinstance(summary["monitoring_enabled"], bool)

    def test_check_limits_without_psutil(self):
        """Test check_limits gracefully handles missing psutil."""
        monitor = ResourceMonitor()
        monitor.start()
        # Should not raise exception even if psutil is not available
        monitor.check_limits("test_tool")


class TestPathRule:
    """Test PathRule dataclass."""

    def test_path_rule_creation(self):
        """Test creating a path rule."""
        rule = PathRule(
            path_pattern="{project_root}/test",
            allowed_operations=["read", "write"],
            description="Test directory",
        )
        assert rule.path_pattern == "{project_root}/test"
        assert rule.allowed_operations == ["read", "write"]
        assert rule.description == "Test directory"

    def test_path_rule_variable_expansion(self, tmp_path):
        """Test variable expansion in path patterns."""
        rule = PathRule(
            path_pattern="{project_root}/build",
            allowed_operations=["read"],
            description="Build directory",
        )
        expanded = rule.path_pattern.format(project_root=str(tmp_path))
        assert str(tmp_path) in expanded
        assert "build" in expanded


class TestOperation:
    """Test Operation dataclass."""

    def test_operation_creation(self):
        """Test creating an operation."""
        op = Operation(name="read", description="Read file contents")
        assert op.name == "read"
        assert op.description == "Read file contents"

    def test_valid_operation_names(self):
        """Test valid operation names."""
        valid_names = ["read", "write", "delete", "execute"]
        for name in valid_names:
            op = Operation(name=name, description=f"{name} operation")
            assert op.name == name
