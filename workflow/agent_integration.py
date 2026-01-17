"""Agent integration module for ESP-IDF MCP Server.

This module enables external agents to:
- Set high-level goals and context
- Get recommended actions based on goals
- Receive feedback on execution progress
- Maintain state across agent sessions
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class AgentGoalType(Enum):
    """Types of agent goals for ESP-IDF development."""

    QUICK_BUILD = "quick_build"  # Build firmware as fast as possible
    FULL_DEPLOY = "full_deploy"  # Complete build, flash, and monitor workflow
    CONFIG_CHANGE = "config_change"  # Modify configuration and rebuild
    HARDWARE_TEST = "hardware_test"  # Test hardware connectivity
    FIRMWARE_UPDATE = "firmware_update"  # Update firmware on device
    DIAGNOSTICS = "diagnostics"  # Diagnose build or hardware issues
    CUSTOM = "custom"  # Custom agent-defined goal


@dataclass
class AgentGoal:
    """Represents an external agent's high-level goal.

    Attributes:
        goal_type: Type of goal from AgentGoalType enum.
        description: Human-readable goal description.
        context: Additional context from the agent.
        priority: Priority level (1=low, 5=high).
        constraints: Any constraints or limitations.
    """

    goal_type: AgentGoalType
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 3
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "goal_type": self.goal_type.value,
            "description": self.description,
            "context": self.context,
            "priority": self.priority,
            "constraints": self.constraints,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentGoal":
        """Create from dictionary."""
        return cls(
            goal_type=AgentGoalType(data.get("goal_type", "custom")),
            description=data.get("description", ""),
            context=data.get("context", {}),
            priority=data.get("priority", 3),
            constraints=data.get("constraints", []),
        )


@dataclass
class RecommendedAction:
    """A recommended action for the agent to take.

    Attributes:
        tool_name: Name of the MCP tool to call.
        description: What this action accomplishes.
        priority: Priority level (1=low, 5=high).
        parameters: Suggested parameters for the tool.
        reason: Why this action is recommended.
        estimated_duration: Estimated duration in seconds.
    """

    tool_name: str
    description: str
    priority: int
    parameters: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    estimated_duration: int = 60

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "description": self.description,
            "priority": self.priority,
            "parameters": self.parameters,
            "reason": self.reason,
            "estimated_duration": self.estimated_duration,
        }


class AgentIntegration:
    """Manages agent goal setting and action recommendations.

    This class integrates with the Workflow system to provide
    intelligent action recommendations based on agent goals.
    """

    def __init__(self, project_root: Path):
        """Initialize agent integration.

        Args:
            project_root: Path to ESP-IDF project root.
        """
        self.project_root = Path(project_root)
        self.current_goal: AgentGoal | None = None
        self._load_goal_from_file()

    def _load_goal_from_file(self) -> None:
        """Load current goal from file if exists."""
        goal_file = self.project_root / ".espidf-mcp" / "agent_goal.json"
        if goal_file.exists():
            try:
                data = json.loads(goal_file.read_text())
                self.current_goal = AgentGoal.from_dict(data)
            except (json.JSONDecodeError, ValueError):
                self.current_goal = None

    def _save_goal_to_file(self) -> None:
        """Save current goal to file for persistence."""
        goal_file = self.project_root / ".espidf-mcp" / "agent_goal.json"
        goal_file.parent.mkdir(parents=True, exist_ok=True)
        if self.current_goal:
            goal_file.write_text(json.dumps(self.current_goal.to_dict(), indent=2))
        elif goal_file.exists():
            goal_file.unlink()

    def set_agent_goal(
        self,
        goal_type: str | AgentGoalType,
        description: str,
        context: dict[str, Any] | None = None,
        priority: int = 3,
        constraints: list[str] | None = None,
    ) -> str:
        """Set the external agent's goal.

        Args:
            goal_type: Type of goal (string or AgentGoalType).
            description: Human-readable goal description.
            context: Additional context from the agent.
            priority: Priority level (1-5).
            constraints: Any constraints or limitations.

        Returns:
            Confirmation message with goal summary.

        Example:
            >>> agent_integration.set_agent_goal(
            ...     goal_type="quick_build",
            ...     description="Build firmware for testing",
            ...     priority=4
            ... )
        """
        if isinstance(goal_type, str):
            try:
                goal_type = AgentGoalType(goal_type)
            except ValueError:
                goal_type = AgentGoalType.CUSTOM

        self.current_goal = AgentGoal(
            goal_type=goal_type,
            description=description,
            context=context or {},
            priority=priority,
            constraints=constraints or [],
        )

        self._save_goal_to_file()

        return f"Agent goal set: {description}\nType: {goal_type.value}\nPriority: {priority}/5"

    def get_recommended_actions(
        self,
        workflow_state: dict[str, Any] | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Get recommended actions based on current goal.

        Args:
            workflow_state: Current workflow state (optional).
            limit: Maximum number of actions to return.

        Returns:
            List of recommended actions, sorted by priority.

        Example:
            >>> actions = agent_integration.get_recommended_actions()
            >>> for action in actions:
            ...     print(f"{action['tool_name']}: {action['description']}")
        """
        if not self.current_goal:
            return [
                {
                    "tool_name": "esp_project_info",
                    "description": "Set a goal first to get personalized recommendations",
                    "priority": 5,
                    "parameters": {},
                    "reason": "Need agent goal to provide recommendations",
                    "estimated_duration": 5,
                }
            ]

        actions = []

        # Get recommendations based on goal type
        if self.current_goal.goal_type == AgentGoalType.QUICK_BUILD:
            actions = self._recommend_quick_build(workflow_state)
        elif self.current_goal.goal_type == AgentGoalType.FULL_DEPLOY:
            actions = self._recommend_full_deploy(workflow_state)
        elif self.current_goal.goal_type == AgentGoalType.CONFIG_CHANGE:
            actions = self._recommend_config_change(workflow_state)
        elif self.current_goal.goal_type == AgentGoalType.HARDWARE_TEST:
            actions = self._recommend_hardware_test(workflow_state)
        elif self.current_goal.goal_type == AgentGoalType.FIRMWARE_UPDATE:
            actions = self._recommend_firmware_update(workflow_state)
        elif self.current_goal.goal_type == AgentGoalType.DIAGNOSTICS:
            actions = self._recommend_diagnostics(workflow_state)
        else:
            actions = self._recommend_custom(workflow_state)

        # Sort by priority (descending) and limit
        actions.sort(key=lambda a: a.priority, reverse=True)
        return [a.to_dict() for a in actions[:limit]]

    def _recommend_quick_build(
        self, workflow_state: dict[str, Any] | None
    ) -> list[RecommendedAction]:
        """Recommend actions for quick build goal."""
        actions = [
            RecommendedAction(
                tool_name="esp_project_info",
                description="Verify project configuration",
                priority=5,
                reason="Ensure project is properly configured before building",
                estimated_duration=5,
            ),
            RecommendedAction(
                tool_name="esp_set_target",
                description="Set target chip if needed",
                priority=4,
                parameters={"target": "esp32"},  # Suggested default
                reason="Target must match hardware",
                estimated_duration=10,
            ),
            RecommendedAction(
                tool_name="esp_build",
                description="Build firmware",
                priority=5,
                reason="Primary goal: compile firmware",
                estimated_duration=60,
            ),
            RecommendedAction(
                tool_name="esp_size",
                description="Check firmware size",
                priority=3,
                reason="Verify firmware fits in flash",
                estimated_duration=10,
            ),
        ]
        return actions

    def _recommend_full_deploy(
        self, workflow_state: dict[str, Any] | None
    ) -> list[RecommendedAction]:
        """Recommend actions for full deploy workflow."""
        actions = [
            RecommendedAction(
                tool_name="esp_project_info",
                description="Verify project configuration",
                priority=5,
                estimated_duration=5,
            ),
            RecommendedAction(
                tool_name="esp_build",
                description="Build firmware",
                priority=5,
                reason="Must build before flashing",
                estimated_duration=60,
            ),
            RecommendedAction(
                tool_name="esp_list_ports",
                description="Find connected devices",
                priority=5,
                reason="Need port for flashing",
                estimated_duration=5,
            ),
            RecommendedAction(
                tool_name="esp_flash",
                description="Flash firmware to device",
                priority=5,
                parameters={"port": "/dev/ttyUSB0"},  # Suggested default
                reason="Deploy firmware to hardware",
                estimated_duration=60,
            ),
            RecommendedAction(
                tool_name="esp_monitor",
                description="Monitor device output",
                priority=4,
                parameters={"port": "/dev/ttyUSB0"},
                reason="Verify firmware is running correctly",
                estimated_duration=30,
            ),
        ]
        return actions

    def _recommend_config_change(
        self, workflow_state: dict[str, Any] | None
    ) -> list[RecommendedAction]:
        """Recommend actions for configuration change workflow."""
        actions = [
            RecommendedAction(
                tool_name="esp_project_info",
                description="Check current configuration",
                priority=5,
                estimated_duration=5,
            ),
            RecommendedAction(
                tool_name="esp_set_target",
                description="Change target if needed",
                priority=4,
                estimated_duration=10,
            ),
            RecommendedAction(
                tool_name="esp_clean",
                description="Clean previous build",
                priority=5,
                parameters={"level": "full"},
                reason="Required after config changes",
                estimated_duration=30,
            ),
            RecommendedAction(
                tool_name="esp_build",
                description="Build with new configuration",
                priority=5,
                reason="Apply configuration changes",
                estimated_duration=60,
            ),
        ]
        return actions

    def _recommend_hardware_test(
        self, workflow_state: dict[str, Any] | None
    ) -> list[RecommendedAction]:
        """Recommend actions for hardware testing."""
        actions = [
            RecommendedAction(
                tool_name="esp_list_ports",
                description="List connected devices",
                priority=5,
                reason="Find available devices",
                estimated_duration=5,
            ),
            RecommendedAction(
                tool_name="esp_read_mac",
                description="Read MAC address from device",
                priority=4,
                reason="Verify device communication",
                estimated_duration=10,
            ),
            RecommendedAction(
                tool_name="esp_partition_table",
                description="Check device partition table",
                priority=3,
                reason="Verify device configuration",
                estimated_duration=10,
            ),
        ]
        return actions

    def _recommend_firmware_update(
        self, workflow_state: dict[str, Any] | None
    ) -> list[RecommendedAction]:
        """Recommend actions for firmware update."""
        actions = [
            RecommendedAction(
                tool_name="esp_build",
                description="Ensure firmware is built",
                priority=5,
                reason="Need firmware to flash",
                estimated_duration=60,
            ),
            RecommendedAction(
                tool_name="esp_list_ports",
                description="Find target device",
                priority=5,
                reason="Need port for flashing",
                estimated_duration=5,
            ),
            RecommendedAction(
                tool_name="esp_flash",
                description="Flash firmware",
                priority=5,
                reason="Update device firmware",
                estimated_duration=60,
            ),
        ]
        return actions

    def _recommend_diagnostics(
        self, workflow_state: dict[str, Any] | None
    ) -> list[RecommendedAction]:
        """Recommend actions for diagnostics."""
        actions = [
            RecommendedAction(
                tool_name="esp_project_info",
                description="Check project state",
                priority=5,
                reason="Understand current state",
                estimated_duration=5,
            ),
            RecommendedAction(
                tool_name="esp_workflow_state",
                description="Check workflow progress",
                priority=5,
                reason="See what has been done",
                estimated_duration=5,
            ),
            RecommendedAction(
                tool_name="esp_observability_status",
                description="Check system status",
                priority=4,
                reason="Review metrics and logs",
                estimated_duration=5,
            ),
        ]
        return actions

    def _recommend_custom(self, workflow_state: dict[str, Any] | None) -> list[RecommendedAction]:
        """Recommend actions for custom goals."""
        actions = [
            RecommendedAction(
                tool_name="esp_project_info",
                description="Start by checking project info",
                priority=5,
                reason="Always good first step",
                estimated_duration=5,
            ),
        ]
        return actions

    def get_goal_summary(self) -> dict[str, Any]:
        """Get summary of current agent goal.

        Returns:
            Dictionary with goal information or empty dict if no goal set.
        """
        if not self.current_goal:
            return {}

        return {
            "goal_type": self.current_goal.goal_type.value,
            "description": self.current_goal.description,
            "priority": self.current_goal.priority,
            "context": self.current_goal.context,
            "constraints": self.current_goal.constraints,
        }

    def clear_goal(self) -> str:
        """Clear the current agent goal.

        Returns:
            Confirmation message.
        """
        self.current_goal = None
        self._save_goal_to_file()
        return "Agent goal cleared"
