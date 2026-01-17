"""Unit tests for workflow system.

Tests the workflow module components without requiring MCP server.
"""

import subprocess
import tempfile
from pathlib import Path

import pytest

from workflow import (
    DEFAULT_STAGES,
    FileStateManager,
    Stage,
    StageOutput,
    StageStatus,
    Workflow,
    WorkflowState,
    capture_output,
)

# ============================================================================
# Test Stage Model
# ============================================================================


class TestStage:
    """Test Stage data model"""

    def test_stage_creation(self):
        """Test creating a stage"""
        stage = Stage(
            name="test",
            description="Test stage",
            tasks=["task1", "task2"],
            checkers=["checker1"],
        )

        assert stage.name == "test"
        assert stage.description == "Test stage"
        assert len(stage.tasks) == 2
        assert stage.status == StageStatus.PENDING

    def test_stage_is_ready_no_deps(self):
        """Test stage readiness with no dependencies"""
        stage = Stage(name="test", description="Test")
        assert stage.is_ready(set())

    def test_stage_is_ready_with_satisfied_deps(self):
        """Test stage readiness with satisfied dependencies"""
        stage = Stage(name="test", description="Test", depends_on=["init", "config"])
        assert stage.is_ready({"init", "config"})

    def test_stage_is_ready_with_unsatisfied_deps(self):
        """Test stage readiness with unsatisfied dependencies"""
        stage = Stage(name="test", description="Test", depends_on=["init", "config"])
        assert not stage.is_ready({"init"})

    def test_stage_from_dict(self):
        """Test creating stage from dictionary (YAML config)"""
        data = {
            "name": "build",
            "desc": "Build firmware",
            "task": ["Run idf.py build", "Verify artifacts"],
            "checkers": [{"name": "build_check", "class": "BuildChecker"}],
            "depends_on": ["config"],
        }

        stage = Stage.from_dict(data)

        assert stage.name == "build"
        assert stage.description == "Build firmware"
        assert len(stage.tasks) == 2
        assert stage.checkers == ["build_check"]
        assert stage.depends_on == ["config"]


# ============================================================================
# Test StageStatus Enum
# ============================================================================


class TestStageStatus:
    """Test StageStatus enum"""

    def test_status_values(self):
        """Test all status values exist"""
        assert StageStatus.PENDING.value == "pending"
        assert StageStatus.IN_PROGRESS.value == "in_progress"
        assert StageStatus.COMPLETED.value == "completed"
        assert StageStatus.FAILED.value == "failed"
        assert StageStatus.SKIPPED.value == "skipped"


# ============================================================================
# Test WorkflowState
# ============================================================================


class TestWorkflowState:
    """Test WorkflowState data model"""

    def test_workflow_state_creation(self):
        """Test creating workflow state"""
        state = WorkflowState()

        assert state.current_stage is None
        assert len(state.completed_stages) == 0
        assert len(state.failed_stages) == 0
        assert len(state.stage_reports) == 0


# ============================================================================
# Test FileStateManager
# ============================================================================


class TestFileStateManager:
    """Test file-based state management"""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            yield project_root

    def test_file_manager_creates_directories(self, temp_project):
        """Test that file manager creates required directories"""
        manager = FileStateManager(temp_project)

        assert manager.mcp_dir.exists()
        assert manager.workflow_dir.exists()
        assert manager.stages_dir.exists()
        assert manager.logs_dir.exists()

    def test_save_and_get_stage_output(self, temp_project):
        """Test saving and retrieving stage output"""
        manager = FileStateManager(temp_project)

        output = StageOutput(
            stage="build",
            timestamp="2024-01-01T00:00:00",
            success=True,
            command="idf.py build",
            stdout="Build succeeded",
            stderr="",
            exit_code=0,
            duration_seconds=5.0,
            artifacts=["build/app.bin"],
        )

        manager.save_stage_output(output)

        # Retrieve
        retrieved = manager.get_stage_status("build")
        assert retrieved is not None
        assert retrieved.stage == "build"
        assert retrieved.success is True
        assert retrieved.exit_code == 0

    def test_get_workflow_state(self, temp_project):
        """Test getting workflow state"""
        manager = FileStateManager(temp_project)

        state = manager.get_workflow_state()

        assert "project_root" in state
        assert "created_at" in state
        assert state["project_root"] == str(temp_project)

    def test_log_message(self, temp_project):
        """Test logging messages"""
        manager = FileStateManager(temp_project)

        manager.log("Test message", "INFO")

        log_file = manager.logs_dir / "workflow.log"
        assert log_file.exists()

        content = log_file.read_text()
        assert "Test message" in content
        assert "INFO" in content


# ============================================================================
# Test StageOutput
# ============================================================================


class TestStageOutput:
    """Test StageOutput data model"""

    def test_stage_output_creation(self):
        """Test creating stage output"""
        output = StageOutput(
            stage="build",
            timestamp="2024-01-01T00:00:00",
            success=True,
            command="idf.py build",
            stdout="Build output",
            stderr="",
            exit_code=0,
            duration_seconds=5.0,
        )

        assert output.stage == "build"
        assert output.success is True

    def test_stage_output_to_dict(self):
        """Test converting stage output to dictionary"""
        output = StageOutput(
            stage="build",
            timestamp="2024-01-01T00:00:00",
            success=True,
            command="idf.py build",
            stdout="Build output",
            stderr="",
            exit_code=0,
            duration_seconds=5.0,
        )

        data = output.to_dict()

        assert data["stage"] == "build"
        assert data["success"] is True
        assert data["duration_seconds"] == 5.0

    def test_stage_output_from_dict(self):
        """Test creating stage output from dictionary"""
        data = {
            "stage": "build",
            "timestamp": "2024-01-01T00:00:00",
            "success": True,
            "command": "idf.py build",
            "stdout": "Build output",
            "stderr": "",
            "exit_code": 0,
            "duration_seconds": 5.0,
            "artifacts": [],
            "metadata": {},
        }

        output = StageOutput.from_dict(data)

        assert output.stage == "build"
        assert output.success is True


# ============================================================================
# Test Workflow
# ============================================================================


class TestWorkflow:
    """Test Workflow core logic"""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            yield project_root

    def test_workflow_creation(self, temp_project):
        """Test creating workflow"""
        workflow = Workflow(project_root=temp_project, enable_file_state=False)

        assert len(workflow.stages) == 5  # DEFAULT_STAGES
        assert "init" in workflow.stages
        assert "build" in workflow.stages

    def test_workflow_get_stage(self, temp_project):
        """Test getting a stage by name"""
        workflow = Workflow(project_root=temp_project, enable_file_state=False)

        stage = workflow.get_stage("build")
        assert stage is not None
        assert stage.name == "build"

    def test_workflow_list_stages(self, temp_project):
        """Test listing stages in dependency order"""
        workflow = Workflow(project_root=temp_project, enable_file_state=False)

        stages = workflow.list_stages()

        # Should return all stages
        assert len(stages) == 5

        # Check dependency order: init should come before config
        stage_names = [s.name for s in stages]
        assert stage_names.index("init") < stage_names.index("config")
        assert stage_names.index("config") < stage_names.index("build")

    def test_workflow_start_stage(self, temp_project):
        """Test starting a stage"""
        workflow = Workflow(project_root=temp_project, enable_file_state=False)

        success, message = workflow.start_stage("init")

        assert success is True
        assert "started" in message.lower()

    def test_workflow_start_stage_missing_deps(self, temp_project):
        """Test starting stage with missing dependencies"""
        workflow = Workflow(project_root=temp_project, enable_file_state=False)

        success, message = workflow.start_stage("build")

        assert success is False
        assert "dependencies" in message.lower()

    def test_workflow_complete_stage(self, temp_project):
        """Test completing a stage"""
        workflow = Workflow(project_root=temp_project, enable_file_state=False)

        # First start the stage
        workflow.start_stage("init")

        # Then complete it
        success, message = workflow.complete_stage("init")

        assert success is True
        assert "completed" in message.lower()
        assert "init" in workflow.state.completed_stages

    def test_workflow_get_progress(self, temp_project):
        """Test getting workflow progress"""
        workflow = Workflow(project_root=temp_project, enable_file_state=False)

        progress = workflow.get_progress()

        assert progress["total_stages"] == 5
        assert progress["completed"] == 0
        assert progress["progress_percent"] == 0.0

    def test_workflow_get_next_stage(self, temp_project):
        """Test getting next stage to execute"""
        workflow = Workflow(project_root=temp_project, enable_file_state=False)

        # Initially, init should be next (no deps)
        next_stage = workflow.get_next_stage()
        assert next_stage is not None
        assert next_stage.name == "init"

    def test_workflow_save_stage_output(self, temp_project):
        """Test saving stage output"""
        workflow = Workflow(project_root=temp_project, enable_file_state=True)

        result = subprocess.CompletedProcess(
            args=["idf.py", "build"],
            returncode=0,
            stdout="Build succeeded",
            stderr="",
        )

        output = workflow.save_stage_output(
            stage_name="build",
            command="idf.py build",
            result=result,
            duration=5.0,
            artifacts=["build/app.bin"],
        )

        assert output is not None
        assert output.stage == "build"
        assert output.success is True

    def test_workflow_is_stage_complete(self, temp_project):
        """Test checking if stage is complete"""
        workflow = Workflow(project_root=temp_project, enable_file_state=True)

        # Initially not complete
        assert not workflow.is_stage_complete("build")

        # Save successful output
        result = subprocess.CompletedProcess(
            args=["idf.py", "build"],
            returncode=0,
            stdout="Build succeeded",
            stderr="",
        )

        workflow.save_stage_output(
            stage_name="build",
            command="idf.py build",
            result=result,
            duration=5.0,
        )

        # Now should be complete
        assert workflow.is_stage_complete("build")


# ============================================================================
# Test Default Stages
# ============================================================================


class TestDefaultStages:
    """Test default workflow stages"""

    def test_default_stages_count(self):
        """Test default stages have correct count"""
        assert len(DEFAULT_STAGES) == 5

    def test_default_stages_dependencies(self):
        """Test default stages have correct dependencies"""
        stages_dict = {s.name: s for s in DEFAULT_STAGES}

        # init has no deps
        assert stages_dict["init"].depends_on == []

        # config depends on init
        assert "init" in stages_dict["config"].depends_on

        # build depends on config
        assert "config" in stages_dict["build"].depends_on

        # flash depends on build
        assert "build" in stages_dict["flash"].depends_on

        # monitor depends on flash
        assert "flash" in stages_dict["monitor"].depends_on


# ============================================================================
# Test Capture Output
# ============================================================================


class TestCaptureOutput:
    """Test capture_output function"""

    def test_capture_output_success(self):
        """Test capturing successful command output"""
        result = subprocess.CompletedProcess(
            args=["echo", "hello"],
            returncode=0,
            stdout="hello",
            stderr="",
        )

        output = capture_output(
            project_root=Path("/tmp/test"),
            stage_name="test",
            command="echo hello",
            result=result,
            artifacts=[],
            metadata={"test": "value"},
        )

        assert output.stage == "test"
        assert output.success is True
        assert output.stdout == "hello"
        assert output.exit_code == 0

    def test_capture_output_failure(self):
        """Test capturing failed command output"""
        result = subprocess.CompletedProcess(
            args=["false"],
            returncode=1,
            stdout="",
            stderr="Error",
        )

        output = capture_output(
            project_root=Path("/tmp/test"),
            stage_name="test",
            command="false",
            result=result,
            artifacts=[],
        )

        assert output.success is False
        assert output.exit_code == 1
        assert output.stderr == "Error"
