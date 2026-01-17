"""Unit tests for observability system.

Tests the logger, metrics, and diagnostics modules.
"""

import json
import tempfile
from pathlib import Path

import pytest

from observability import get_diagnostics, get_logger, get_metrics, reset
from observability.diagnostics import ErrorPattern
from observability.formatters import OutputFormatter, TableFormatter


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before each test."""
    reset()
    yield
    reset()


# ============================================================================
# Test Logger
# ============================================================================


class TestMCPLogger:
    """Test MCPLogger dual-format logging system."""

    def test_logger_initialization(self):
        """Test logger can be initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            logger = get_logger("test", log_dir)

            assert logger.name == "test"
            assert logger.log_dir == log_dir

    def test_logger_creates_directories(self):
        """Test logger creates required directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            logger = get_logger("test", log_dir)

            assert logger.log_dir.exists()
            assert logger.json_dir.exists()

    def test_logger_info_level(self):
        """Test INFO level logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            logger = get_logger("test", log_dir)

            logger.info("Test message", test_key="test_value")

            # Check structured log was created
            jsonl_file = log_dir / "structured" / "test.jsonl"
            assert jsonl_file.exists()

            # Read and verify JSON content
            with open(jsonl_file) as f:
                entry = json.loads(f.readline().strip())
                assert entry["message"] == "Test message"
                assert entry["level"] == "INFO"
                # Extra fields are in context dict
                context = entry.get("context", {})
                assert context.get("test_key") == "test_value"

    def test_logger_error_level(self):
        """Test ERROR level logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            logger = get_logger("test", log_dir)

            logger.error("Error message", error_code=500)

            # Check structured log
            jsonl_file = log_dir / "structured" / "test.jsonl"
            with open(jsonl_file) as f:
                entry = json.loads(f.readline().strip())
                assert entry["message"] == "Error message"
                assert entry["level"] == "ERROR"
                # Extra fields are in context dict
                context = entry.get("context", {})
                assert context.get("error_code") == 500

    def test_logger_log_tool_call(self):
        """Test structured tool call logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            logger = get_logger("test", log_dir)

            logger.log_tool_call(
                tool_name="esp_build",
                args={"target": "esp32"},
                result="Build succeeded",
                duration=5.2,
                success=True,
            )

            # Check structured log
            jsonl_file = log_dir / "structured" / "test.jsonl"
            with open(jsonl_file) as f:
                entry = json.loads(f.readline().strip())
                # Extra fields are in context dict
                context = entry.get("context", {})
                assert context.get("tool_name") == "esp_build"
                assert context.get("success") is True
                assert context.get("duration_seconds") == 5.2

    def test_logger_log_stage_transition(self):
        """Test structured stage transition logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            logger = get_logger("test", log_dir)

            logger.log_stage_transition(
                stage="build",
                from_status="pending",
                to_status="completed",
                metadata={"duration": 5.2},
            )

            # Check structured log
            jsonl_file = log_dir / "structured" / "test.jsonl"
            with open(jsonl_file) as f:
                entry = json.loads(f.readline().strip())
                # Extra fields are in context dict
                context = entry.get("context", {})
                assert context.get("stage") == "build"
                assert context.get("from_status") == "pending"
                assert context.get("to_status") == "completed"
                assert context.get("duration") == 5.2


# ============================================================================
# Test Metrics
# ============================================================================


class TestMetricsCollector:
    """Test MetricsCollector performance tracking."""

    def test_metrics_initialization(self):
        """Test metrics collector initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            metrics = get_metrics(project_root)

            assert metrics.project_root == project_root

    def test_record_tool_execution(self):
        """Test recording tool execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            metrics = get_metrics(project_root)

            metrics.record_tool_execution("esp_build", 5.2, True)

            stats = metrics.get_tool_stats("esp_build")
            assert stats["call_count"] == 1
            assert stats["success_rate"] == 1.0
            assert stats["avg_duration_ms"] == 5200.0

    def test_record_multiple_executions(self):
        """Test recording multiple tool executions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            metrics = get_metrics(project_root)

            metrics.record_tool_execution("esp_build", 5.0, True)
            metrics.record_tool_execution("esp_build", 10.0, True)

            stats = metrics.get_tool_stats("esp_build")
            assert stats["call_count"] == 2
            assert stats["success_rate"] == 1.0
            assert stats["avg_duration_ms"] == 7500.0  # (5 + 10) / 2 * 1000

    def test_record_failure(self):
        """Test recording failed tool execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            metrics = get_metrics(project_root)

            metrics.record_tool_execution("esp_build", 3.0, False)

            stats = metrics.get_tool_stats("esp_build")
            assert stats["call_count"] == 1
            assert stats["success_rate"] == 0.0
            assert stats["failure_count"] == 1

    def test_get_all_tool_stats(self):
        """Test getting statistics for all tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            metrics = get_metrics(project_root)

            metrics.record_tool_execution("esp_build", 5.0, True)
            metrics.record_tool_execution("esp_flash", 2.0, True)

            all_stats = metrics.get_all_tool_stats()
            assert "esp_build" in all_stats
            assert "esp_flash" in all_stats
            assert len(all_stats) == 2

    def test_get_bottlenecks(self):
        """Test identifying performance bottlenecks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            metrics = get_metrics(project_root)

            # Record some executions with different durations
            for _ in range(5):
                metrics.record_tool_execution("esp_build", 5.0, True)
            for _ in range(3):
                metrics.record_tool_execution("esp_flash", 15.0, True)

            bottlenecks = metrics.get_bottlenecks()
            assert len(bottlenecks) > 0
            # esp_flash should be first (slower)
            assert bottlenecks[0]["tool_name"] == "esp_flash"

    def test_get_failure_summary(self):
        """Test getting failure summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            metrics = get_metrics(project_root)

            # Record failures
            metrics.record_tool_execution("esp_build", 1.0, False)
            metrics.record_tool_execution("esp_build", 1.0, False)
            metrics.record_tool_execution("esp_build", 3.0, True)

            summary = metrics.get_failure_summary()
            assert "esp_build" in summary
            assert summary["esp_build"]["total_failures"] == 2

    def test_stage_metrics(self):
        """Test recording stage metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            metrics = get_metrics(project_root)

            metrics.record_stage_duration("build", 5.2, True)
            metrics.record_stage_duration("build", 4.8, True)

            stage_metrics = metrics.get_stage_metrics("build")
            assert stage_metrics is not None
            assert stage_metrics.total_runs == 2
            assert stage_metrics.successful_runs == 2
            assert stage_metrics.avg_duration_seconds == 5.0


# ============================================================================
# Test Diagnostics
# ============================================================================


class TestDiagnosticEngine:
    """Test DiagnosticEngine error pattern recognition."""

    def test_diagnose_idf_path_error(self):
        """Test diagnosing IDF_PATH not set error."""
        diagnostics = get_diagnostics()

        result = diagnostics.diagnose("IDF_PATH is not set")

        assert result.category == "environment"
        assert len(result.matched_patterns) > 0
        assert len(result.suggestions) > 0
        assert result.severity == "error"

    def test_diagnose_memory_overflow(self):
        """Test diagnosing memory overflow error."""
        diagnostics = get_diagnostics()

        result = diagnostics.diagnose("region IRAM overflow")

        assert result.category == "build"
        assert "memory_overflow" in result.matched_patterns
        assert len(result.suggestions) > 0

    def test_diagnose_port_not_found(self):
        """Test diagnosing port not found error."""
        diagnostics = get_diagnostics()

        result = diagnostics.diagnose("Failed to connect: port not found")

        assert result.category == "hardware"
        assert "port_not_found" in result.matched_patterns

    def test_diagnose_flash_write_error(self):
        """Test diagnosing flash write error."""
        diagnostics = get_diagnostics()

        result = diagnostics.diagnose("Failed to write flash data")

        assert result.category == "flash"
        assert "flash_write_error" in result.matched_patterns

    def test_add_custom_pattern(self):
        """Test adding custom error pattern."""
        diagnostics = get_diagnostics()

        custom = ErrorPattern(
            name="custom_error",
            patterns=[r"Custom error pattern"],
            category="custom",
            suggestions=["Custom fix"],
            severity="warning",
        )

        diagnostics.add_custom_pattern(custom)

        result = diagnostics.diagnose("Custom error pattern")
        assert "custom_error" in result.matched_patterns

    def test_get_suggestions_for_error(self):
        """Test getting suggestions for error."""
        diagnostics = get_diagnostics()

        suggestions = diagnostics.get_suggestions_for_error("IDF_PATH not set")

        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert any("source" in s.lower() for s in suggestions)

    def test_get_all_patterns(self):
        """Test getting all error patterns."""
        diagnostics = get_diagnostics()

        patterns = diagnostics.get_all_patterns()

        assert len(patterns) > 10  # Should have many built-in patterns

    def test_get_patterns_by_category(self):
        """Test getting patterns by category."""
        diagnostics = get_diagnostics()

        build_patterns = diagnostics.get_patterns_by_category("build")

        assert len(build_patterns) > 0
        for pattern in build_patterns:
            assert pattern.category == "build"


# ============================================================================
# Test Formatters
# ============================================================================


class TestOutputFormatter:
    """Test OutputFormatter for different audiences."""

    def test_format_tool_result(self):
        """Test formatting tool result."""
        formatter = OutputFormatter()

        output = formatter.format_tool_result("esp_build", "Build succeeded", 5.2, True)

        assert "esp_build" in output
        assert "SUCCESS" in output
        assert "5.20s" in output

    def test_format_metrics_summary(self):
        """Test formatting metrics summary."""
        formatter = OutputFormatter()

        metrics = {
            "esp_build": {
                "call_count": 10,
                "success_rate": 0.9,
                "avg_duration_ms": 5200,
                "last_called": "2024-01-01T12:00:00",
            }
        }

        output = formatter.format_metrics_summary(metrics)

        assert "Performance Metrics" in output
        assert "esp_build" in output
        assert "90.0%" in output

    def test_format_diagnostic_report(self):
        """Test formatting diagnostic report."""
        formatter = OutputFormatter()

        output = formatter.format_diagnostic_report(
            matched_patterns=["memory_overflow", "link_error"],
            suggestions=["Reduce size", "Check dependencies"],
            severity="error",
        )

        assert "Diagnostic Report" in output
        assert "memory_overflow" in output
        assert "Suggestions" in output

    def test_format_bottlenecks(self):
        """Test formatting bottleneck report."""
        formatter = OutputFormatter()

        bottlenecks = [{"tool_name": "esp_flash", "avg_duration_ms": 15000, "percentile": 90}]

        output = formatter.format_bottlenecks(bottlenecks)

        assert "Performance Bottlenecks" in output
        assert "esp_flash" in output


class TestTableFormatter:
    """Test TableFormatter for tabular data."""

    def test_format_tool_stats_table(self):
        """Test formatting tool statistics as table."""
        formatter = TableFormatter()

        stats = {
            "esp_build": {
                "call_count": 10,
                "success_rate": 0.9,
                "avg_duration_ms": 5200,
                "last_called": "2024-01-01",
            }
        }

        table = formatter.format_tool_stats_table(stats)

        assert "Tool" in table
        assert "esp_build" in table
        assert "10" in table

    def test_format_error_history_table(self):
        """Test formatting error history as table."""
        formatter = TableFormatter()

        errors = [
            {
                "timestamp": "2024-01-01T12:00:00",
                "tool_name": "esp_build",
                "pattern": "memory_overflow",
                "severity": "error",
            }
        ]

        table = formatter.format_error_history_table(errors)

        assert "Time" in table
        assert "esp_build" in table
        assert "memory_overflow" in table


# ============================================================================
# Test Integration
# ============================================================================


class TestObservabilityIntegration:
    """Test integration between observability components."""

    def test_end_to_end_workflow(self):
        """Test complete observability workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Get components
            logger = get_logger("test", project_root / "logs")
            metrics = get_metrics(project_root)
            diagnostics = get_diagnostics()

            # Simulate tool execution
            duration = 1.5
            success = True

            # Record metrics
            metrics.record_tool_execution("test_tool", duration, success)

            # Log execution
            logger.log_tool_call("test_tool", {}, "Tool output", duration, success)

            # Verify
            stats = metrics.get_tool_stats("test_tool")
            assert stats["call_count"] == 1

    def test_error_diagnosis_workflow(self):
        """Test error diagnosis workflow."""
        diagnostics = get_diagnostics()

        # Simulate error
        error_output = "IDF_PATH not set"

        # Diagnose
        result = diagnostics.diagnose(error_output)

        # Verify
        assert result.matched_patterns
        assert result.suggestions

    def test_metrics_persistence(self):
        """Test metrics are persisted to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            metrics = get_metrics(project_root)

            # Record some data
            metrics.record_tool_execution("esp_build", 5.0, True)

            # Check file was created
            metrics_file = project_root / ".espidf-mcp" / "metrics.json"
            assert metrics_file.exists()

            # Load and verify
            data = json.loads(metrics_file.read_text())
            assert "tool_executions" in data
