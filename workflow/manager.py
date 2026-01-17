"""Workflow manager for ESP-IDF MCP development.

Manages project stages with validation, dependencies, and progression.
"""

import subprocess
from pathlib import Path

from checkers import CheckerRegistry, CheckerReport

from .file_state import FileStateManager, StageOutput, capture_output
from .stages import DEFAULT_STAGES, Stage, StageStatus, WorkflowState


class Workflow:
    """Stage-based workflow for ESP-IDF development.

    Manages project stages with validation, dependencies, and progression.
    """

    def __init__(
        self,
        stages: list[Stage] | None = None,
        checker_registry: CheckerRegistry | None = None,
        project_root: Path | None = None,
        enable_file_state: bool = True,
    ):
        """Initialize workflow.

        Args:
            stages: List of workflow stages (uses default if None).
            checker_registry: Checker registry for validation.
            project_root: Project root directory.
            enable_file_state: Enable file-based state management.
        """
        # Create deep copies of stages to avoid mutating DEFAULT_STAGES
        from dataclasses import replace

        stage_list = stages or DEFAULT_STAGES
        self.stages = {s.name: replace(s, status=StageStatus.PENDING) for s in stage_list}
        self.checkers = checker_registry or CheckerRegistry()
        self.project_root = project_root or Path.cwd()
        self.state = WorkflowState()
        self.enable_file_state = enable_file_state

        # Initialize file state manager
        if enable_file_state:
            self.file_manager = FileStateManager(self.project_root)
        else:
            self.file_manager = None

        # Load previous workflow state if exists
        self._load_state_from_files()

    def get_stage(self, name: str) -> Stage | None:
        """Get stage by name."""
        return self.stages.get(name)

    def list_stages(self) -> list[Stage]:
        """List all stages in dependency order."""
        ordered = []
        remaining = set(self.stages.keys())

        while remaining:
            # Find stages with all dependencies satisfied
            completed = {s.name for s in ordered}
            ready = [name for name in remaining if self.stages[name].is_ready(completed)]
            if not ready:
                # Circular dependency or missing dependency
                ready = [next(iter(remaining))]

            for name in sorted(ready):
                ordered.append(self.stages[name])
                remaining.remove(name)

        return ordered

    def start_stage(self, name: str) -> tuple[bool, str]:
        """Start a workflow stage.

        Args:
            name: Stage name to start.

        Returns:
            Tuple of (success, message).
        """
        stage = self.get_stage(name)
        if not stage:
            return False, f"Stage '{name}' not found"

        if not stage.is_ready(self.state.completed_stages):
            missing = [d for d in stage.depends_on if d not in self.state.completed_stages]
            return False, f"Dependencies not satisfied: {missing}"

        if stage.status == StageStatus.COMPLETED:
            return False, f"Stage '{name}' already completed"

        stage.status = StageStatus.IN_PROGRESS
        self.state.current_stage = name
        return True, f"Stage '{name}' started"

    def validate_stage(self, name: str) -> list[CheckerReport]:
        """Run all checkers for a stage.

        Args:
            name: Stage name to validate.

        Returns:
            List of checker reports.
        """
        stage = self.get_stage(name)
        if not stage:
            return []

        reports = self.checkers.run_stage_checks(name, self.project_root)
        self.state.stage_reports[name] = reports

        # Update stage status based on reports
        failed = any(r.is_fail() for r in reports)
        if failed:
            stage.status = StageStatus.FAILED
            self.state.failed_stages.add(name)
        else:
            stage.status = StageStatus.COMPLETED
            self.state.completed_stages.add(name)

        return reports

    def complete_stage(self, name: str) -> tuple[bool, str]:
        """Mark a stage as completed.

        Args:
            name: Stage name to complete.

        Returns:
            Tuple of (success, message).
        """
        stage = self.get_stage(name)
        if not stage:
            return False, f"Stage '{name}' not found"

        stage.status = StageStatus.COMPLETED
        self.state.completed_stages.add(name)
        if self.state.current_stage == name:
            self.state.current_stage = None

        return True, f"Stage '{name}' completed"

    def get_progress(self) -> dict:
        """Get workflow progress summary.

        Returns:
            Dictionary with progress information.
        """
        total = len(self.stages)
        completed = len(self.state.completed_stages)
        failed = len(self.state.failed_stages)

        return {
            "total_stages": total,
            "completed": completed,
            "failed": failed,
            "current": self.state.current_stage,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
            "stages": {name: stage.status.value for name, stage in self.stages.items()},
        }

    def get_next_stage(self) -> Stage | None:
        """Get the next stage to execute.

        Returns:
            Next stage or None if all complete.
        """
        for stage in self.list_stages():
            if stage.status == StageStatus.PENDING and stage.is_ready(self.state.completed_stages):
                return stage
        return None

    def _load_state_from_files(self):
        """Load workflow state from files if file state is enabled."""
        if not self.file_manager:
            return

        # Load workflow state
        workflow_state = self.file_manager.get_workflow_state()

        # Restore completed stages from file history
        for stage_name in self.stages.keys():
            stage_status = self.file_manager.get_stage_status(stage_name)
            if stage_status and stage_status.success:
                self.state.completed_stages.add(stage_name)
                self.stages[stage_name].status = StageStatus.COMPLETED
            elif stage_status and not stage_status.success:
                self.stages[stage_name].status = StageStatus.FAILED
                self.state.failed_stages.add(stage_name)

        # Log state loading
        if workflow_state.get("last_stage"):
            self.file_manager.log(
                f"Loaded workflow state: {len(self.state.completed_stages)} stages completed"
            )

    def save_stage_output(
        self,
        stage_name: str,
        command: str,
        result: subprocess.CompletedProcess[str],
        duration: float,
        artifacts: list[str] | None = None,
    ) -> StageOutput:
        """Save stage execution output to file.

        Args:
            stage_name: Name of the stage.
            command: Command that was executed.
            result: Subprocess result.
            duration: Execution duration in seconds.
            artifacts: List of generated artifact files.

        Returns:
            StageOutput instance.
        """
        if not self.file_manager:
            return None

        # Capture output
        stage_output = capture_output(
            self.project_root,
            stage_name,
            command,
            result,
            artifacts,
            {"duration": duration},
        )

        # Save to file
        self.file_manager.save_stage_output(stage_output)

        # Update stage status
        if result.returncode == 0:
            self.stages[stage_name].status = StageStatus.COMPLETED
            self.state.completed_stages.add(stage_name)
        else:
            self.stages[stage_name].status = StageStatus.FAILED
            self.state.failed_stages.add(stage_name)

        # Log completion
        status = "SUCCESS" if result.returncode == 0 else "FAILED"
        self.file_manager.log(f"Stage {stage_name}: {status}")

        return stage_output

    def get_stage_output(self, stage_name: str) -> StageOutput | None:
        """Get stage output from file.

        Args:
            stage_name: Name of the stage.

        Returns:
            StageOutput if available, None otherwise.
        """
        if not self.file_manager:
            return None
        return self.file_manager.get_stage_status(stage_name)

    def get_stage_log(self, stage_name: str) -> str | None:
        """Get raw stage output log.

        Args:
            stage_name: Name of the stage.

        Returns:
            Raw output text if available, None otherwise.
        """
        if not self.file_manager:
            return None

        output_file = self.file_manager.stages_dir / stage_name / "output.txt"
        if output_file.exists():
            return output_file.read_text()
        return None

    def is_stage_complete(self, stage_name: str) -> bool:
        """Check if stage is complete based on file state.

        Args:
            stage_name: Name of the stage.

        Returns:
            True if stage completed successfully, False otherwise.
        """
        stage_status = self.get_stage_output(stage_name)
        return stage_status is not None and stage_status.success

    def get_failed_stages(self) -> list[str]:
        """Get list of failed stages from file state.

        Returns:
            List of failed stage names.
        """
        if not self.file_manager:
            return list(self.state.failed_stages)

        failed = []
        for stage_name in self.stages.keys():
            stage_status = self.get_stage_output(stage_name)
            if stage_status and not stage_status.success:
                failed.append(stage_name)

        return failed

    def log(self, message: str, level: str = "INFO"):
        """Write message to workflow log.

        Args:
            message: Log message.
            level: Log level.
        """
        if self.file_manager:
            self.file_manager.log(message, level)

    def get_workflow_state(self) -> dict:
        """Get current workflow state from file manager.

        Returns:
            Workflow state dict.
        """
        if self.file_manager:
            return self.file_manager.get_workflow_state()
        return {}
