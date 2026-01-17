"""Workflow data models for ESP-IDF MCP development.

Defines stage status, stage configuration, and workflow state.
"""

from dataclasses import dataclass, field
from enum import Enum


class StageStatus(Enum):
    """Status of a workflow stage."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Stage:
    """A workflow stage with tasks and validation.

    Attributes:
        name: Unique stage identifier.
        description: Human-readable description.
        tasks: List of task descriptions.
        checkers: List of checker names to run for validation.
        status: Current stage status.
        depends_on: List of stage names this stage depends on.
    """

    name: str
    description: str
    tasks: list[str] = field(default_factory=list)
    checkers: list[str] = field(default_factory=list)
    status: StageStatus = StageStatus.PENDING
    depends_on: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def is_ready(self, completed_stages: set[str]) -> bool:
        """Check if stage is ready to start.

        Args:
            completed_stages: Set of completed stage names.

        Returns:
            True if all dependencies are satisfied.
        """
        return all(dep in completed_stages for dep in self.depends_on)

    @classmethod
    def from_dict(cls, data: dict) -> "Stage":
        """Create Stage from dictionary (YAML config).

        Args:
            data: Dictionary with stage configuration.

        Returns:
            Stage instance.
        """
        return cls(
            name=data.get("name", ""),
            description=data.get("desc", ""),
            tasks=data.get("task", []),
            checkers=[
                c.get("name", "") if isinstance(c, dict) else c for c in data.get("checkers", [])
            ],
            depends_on=data.get("depends_on", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkflowState:
    """State of an active workflow.

    Attributes:
        current_stage: Name of current stage.
        completed_stages: Set of completed stage names.
        failed_stages: Set of failed stage names.
        stage_reports: Mapping of stage names to checker reports.
    """

    current_stage: str | None = None
    completed_stages: set[str] = field(default_factory=set)
    failed_stages: set[str] = field(default_factory=set)
    stage_reports: dict[str, list] = field(default_factory=dict)


# Default workflow stages for ESP-IDF projects
DEFAULT_STAGES = [
    Stage(
        name="init",
        description="Project initialization and validation",
        tasks=[
            "Verify ESP-IDF environment (IDF_PATH)",
            "Validate project structure (CMakeLists.txt)",
            "Check project directory permissions",
        ],
        checkers=["project_structure"],
    ),
    Stage(
        name="config",
        description="Target chip configuration",
        tasks=[
            "Set target chip (idf.py set-target)",
            "Configure project options (menuconfig if needed)",
        ],
        checkers=["target_config"],
        depends_on=["init"],
    ),
    Stage(
        name="build",
        description="Build firmware",
        tasks=[
            "Clean previous builds (optional)",
            "Run idf.py build",
            "Verify build artifacts",
        ],
        checkers=["build_artifacts"],
        depends_on=["config"],
    ),
    Stage(
        name="flash",
        description="Flash firmware to device",
        tasks=[
            "Detect connected ESP32 device",
            "Flash firmware (idf.py flash)",
            "Verify flash success",
        ],
        depends_on=["build"],
    ),
    Stage(
        name="monitor",
        description="Monitor device output",
        tasks=[
            "Start serial monitor",
            "Verify device boot logs",
            "Check for runtime errors",
        ],
        depends_on=["flash"],
    ),
]
