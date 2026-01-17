"""File-based state management for ESP-IDF workflow.

Uses files to communicate between workflow stages, enabling:
- Output persistence for inspection
- Stage completion verification
- Progress tracking across sessions

File operations use atomic writes to prevent data corruption.
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def atomic_write(filepath: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomically write content to a file.

    Uses the write-then-rename pattern for atomicity:
    1. Write content to a temporary file in the same directory
    2. Sync the temporary file to disk
    3. Rename the temporary file to the target path (atomic on POSIX)

    This ensures that either the old content OR new content exists,
    never partial/corrupted data.

    Args:
        filepath: Target file path to write to.
        content: Content to write.
        encoding: File encoding (default: utf-8).

    Raises:
        OSError: If write or rename operation fails.
    """
    # Create parent directory if needed
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Create temporary file in the same directory as the target
    # This ensures the rename will work (same filesystem)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=filepath.parent,
        prefix=f".{filepath.name}.",
        suffix=".tmp",
        encoding=encoding,
        delete=False,
    ) as tmp_file:
        tmp_path = Path(tmp_file.name)
        tmp_file.write(content)
        # Flush to ensure data is written to the file
        tmp_file.flush()
        # Sync to disk (optional but ensures durability)
        try:
            import os

            os.fsync(tmp_file.fileno())
        except (OSError, AttributeError):
            # fsync may not be available on all platforms
            pass

    # Atomic rename (replaces target if it exists)
    tmp_path.replace(filepath)


def atomic_append(filepath: Path, content: str, encoding: str = "utf-8") -> None:
    """Append content to a file with locking for concurrent access safety.

    Uses filelock for cross-platform file locking to prevent
    concurrent write corruption from multiple processes.

    Improvements:
    - Unique lock file per target path (prevents conflicts)
    - Reduced timeout with retry logic (better responsiveness)
    - File existence verification before write
    - Explicit fsync for durability
    - Better error reporting

    Args:
        filepath: Target file path to append to.
        content: Content to append.
        encoding: File encoding (default: utf-8).

    Raises:
        OSError: If write operation fails.
    """
    import hashlib
    import os
    import time

    from filelock import FileLock, Timeout

    # Create parent directory if needed
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Use unique lock file per target to avoid conflicts
    file_hash = hashlib.md5(str(filepath).encode()).hexdigest()[:8]
    lock_path = filepath.parent / f".{file_hash}.lock"

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            # Use shorter timeout with retry logic
            with FileLock(lock_path, timeout=2):
                # Verify file exists before writing
                if not filepath.exists():
                    filepath.touch()

                # Write with explicit flush
                with open(filepath, "a", encoding=encoding) as f:
                    f.write(content)
                    f.flush()
                    # Force write to disk (atomic append completion)
                    try:
                        os.fsync(f.fileno())
                    except (OSError, AttributeError):
                        # fsync may not be available on all platforms
                        pass

                return  # Success

        except Timeout as e:
            last_error = e
            if attempt < max_retries - 1:
                # Exponential backoff: 0.1s, 0.2s, 0.4s
                time.sleep(0.1 * (2**attempt))
        except Exception as e:
            raise OSError(f"Failed to append to {filepath}: {e}")

    # All retries exhausted
    raise OSError(f"Timeout acquiring lock for {filepath} after {max_retries} attempts")


@dataclass
class StageOutput:
    """Output data from a workflow stage execution.

    Attributes:
        stage: Stage name.
        timestamp: Execution timestamp.
        success: Whether execution succeeded.
        command: Command that was executed.
        stdout: Standard output.
        stderr: Standard error.
        exit_code: Process exit code.
        duration_seconds: Execution duration.
        artifacts: List of generated file paths.
        metadata: Additional metadata.
    """

    stage: str
    timestamp: str
    success: bool
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    artifacts: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "stage": self.stage,
            "timestamp": self.timestamp,
            "success": self.success,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StageOutput":
        """Create from dictionary."""
        return cls(**data)


class FileStateManager:
    """Manages workflow state through files.

    Creates a .espidf-mcp/ directory structure:
    .espidf-mcp/
    ├── workflow/
    │   ├── state.json          # Overall workflow state
    │   ├── current_stage.txt  # Currently executing stage
    │   └── history.json       # Stage execution history
    ├── stages/
    │   ├── build/
    │   │   ├── output.txt      # Build output
    │   │   ├── status.json     # Build status
    │   │   └── artifacts/      # Generated .bin files
    │   ├── flash/
    │   └── monitor/
    └── logs/
        └── workflow.log        # Complete workflow log
    """

    def __init__(self, project_root: Path):
        """Initialize file state manager.

        Args:
            project_root: ESP-IDF project root directory.
        """
        self.project_root = Path(project_root)
        self.mcp_dir = self.project_root / ".espidf-mcp"
        self.workflow_dir = self.mcp_dir / "workflow"
        self.stages_dir = self.mcp_dir / "stages"
        self.logs_dir = self.mcp_dir / "logs"

        # Create directories
        self.mcp_dir.mkdir(exist_ok=True)
        self.workflow_dir.mkdir(exist_ok=True)
        self.stages_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

    def get_stage_dir(self, stage_name: str) -> Path:
        """Get directory for a specific stage.

        Args:
            stage_name: Name of the stage.

        Returns:
            Path to stage directory.
        """
        stage_dir = self.stages_dir / stage_name
        stage_dir.mkdir(exist_ok=True)
        return stage_dir

    def save_stage_output(self, stage_output: StageOutput) -> Path:
        """Save stage execution output to file.

        Uses atomic writes to prevent data corruption.

        Args:
            stage_output: Stage execution data.

        Returns:
            Path to saved status file.
        """
        stage_dir = self.get_stage_dir(stage_output.stage)

        # Save status as JSON (atomic write)
        status_file = stage_dir / "status.json"
        atomic_write(status_file, json.dumps(stage_output.to_dict(), indent=2))

        # Save raw output (atomic write)
        output_file = stage_dir / "output.txt"
        output_content = [
            f"Stage: {stage_output.stage}",
            f"Timestamp: {stage_output.timestamp}",
            f"Command: {stage_output.command}",
            f"Exit Code: {stage_output.exit_code}",
            f"Duration: {stage_output.duration_seconds:.2f}s",
            f"Success: {stage_output.success}",
            "",
            "=" * 60,
            "STDOUT:",
            "=" * 60,
            stage_output.stdout,
            "",
            "=" * 60,
            "STDERR:",
            "=" * 60,
            stage_output.stderr,
        ]
        atomic_write(output_file, "\n".join(output_content))

        # Update workflow state
        self._update_workflow_state(stage_output)

        return status_file

    def get_stage_status(self, stage_name: str) -> StageOutput | None:
        """Read stage status from file.

        Args:
            stage_name: Name of the stage.

        Returns:
            StageOutput if status file exists, None otherwise.
        """
        status_file = self.stages_dir / stage_name / "status.json"
        if not status_file.exists():
            return None

        try:
            data = json.loads(status_file.read_text())
            return StageOutput.from_dict(data)
        except Exception:
            return None

    def _update_workflow_state(self, stage_output: StageOutput):
        """Update overall workflow state.

        Uses atomic writes to prevent data corruption.

        Args:
            stage_output: Latest stage execution data.
        """
        # Update current stage (atomic write)
        current_file = self.workflow_dir / "current_stage.txt"
        atomic_write(current_file, stage_output.stage)

        # Update history (atomic write)
        history_file = self.workflow_dir / "history.json"
        history = []
        if history_file.exists():
            try:
                history = json.loads(history_file.read_text())
            except Exception:
                pass

        # Add new entry
        history.append(
            {
                "stage": stage_output.stage,
                "timestamp": stage_output.timestamp,
                "success": stage_output.success,
                "exit_code": stage_output.exit_code,
                "duration": stage_output.duration_seconds,
            }
        )

        # Keep only last 100 entries
        history = history[-100:]
        atomic_write(history_file, json.dumps(history, indent=2))

        # Update overall state (atomic write)
        state_file = self.workflow_dir / "state.json"
        state = self._load_workflow_state()
        state["last_stage"] = stage_output.stage
        state["last_update"] = stage_output.timestamp
        state["stages_completed"] = state.get("stages_completed", 0) + (
            1 if stage_output.success else 0
        )
        atomic_write(state_file, json.dumps(state, indent=2))

    def _load_workflow_state(self) -> dict:
        """Load workflow state from file.

        Returns:
            Current workflow state dict.
        """
        state_file = self.workflow_dir / "state.json"
        if state_file.exists():
            try:
                return json.loads(state_file.read_text())
            except Exception:
                pass
        return {
            "project_root": str(self.project_root),
            "created_at": datetime.now().isoformat(),
            "last_stage": None,
            "last_update": None,
            "stages_completed": 0,
        }

    def get_workflow_state(self) -> dict:
        """Get current workflow state.

        Returns:
            Workflow state dict.
        """
        return self._load_workflow_state()

    def log(self, message: str, level: str = "INFO", **context):
        """Write message to workflow log with structured output.

        Writes to both human-readable log and JSON structured log.
        Uses atomic appends with file locking for concurrent access safety.

        Args:
            message: Log message.
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            **context: Additional metadata for structured log.
        """
        # Human-readable log (original format)
        log_file = self.logs_dir / "workflow.log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        atomic_append(log_file, log_entry)

        # Structured JSON log
        self._write_structured_log(message, level, **context)

    def _write_structured_log(self, message: str, level: str, **context):
        """Write structured log entry to JSONL file.

        Uses atomic append with file locking for concurrent access safety.

        Args:
            message: Log message.
            level: Log level.
            **context: Additional metadata.
        """
        # Create structured logs directory
        structured_dir = self.logs_dir / "structured"
        structured_dir.mkdir(exist_ok=True)

        # Write to workflow.jsonl
        structured_file = structured_dir / "workflow.jsonl"

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "logger": "workflow",
            "project_root": str(self.project_root),
            **context,
        }

        atomic_append(structured_file, json.dumps(log_entry, ensure_ascii=False) + "\n")


def capture_output(
    project_root: Path,
    stage_name: str,
    command: str,
    result: "subprocess.CompletedProcess[str]",
    artifacts: list[str] | None = None,
    metadata: dict | None = None,
) -> StageOutput:
    """Capture subprocess result as StageOutput.

    Args:
        project_root: Project root directory.
        stage_name: Name of the stage.
        command: Command that was executed.
        result: Subprocess result.
        artifacts: List of generated files.
        metadata: Additional metadata.

    Returns:
        StageOutput instance.
    """
    return StageOutput(
        stage=stage_name,
        timestamp=datetime.now().isoformat(),
        success=result.returncode == 0,
        command=command,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.returncode,
        duration_seconds=0.0,  # Would need to track time separately
        artifacts=artifacts or [],
        metadata=metadata or {},
    )
