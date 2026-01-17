"""Workflow system for ESP-IDF MCP development.

Provides stage-based workflow management with validation and progression.
"""

from .agent_integration import (
    AgentGoal,
    AgentGoalType,
    AgentIntegration,
    RecommendedAction,
)
from .file_state import FileStateManager, StageOutput, capture_output
from .manager import Workflow
from .stages import DEFAULT_STAGES, Stage, StageStatus, WorkflowState

__all__ = [
    # Core classes
    "Workflow",
    "WorkflowState",
    # Stage models
    "Stage",
    "StageStatus",
    "DEFAULT_STAGES",
    # File state
    "FileStateManager",
    "StageOutput",
    "capture_output",
    # Agent integration
    "AgentGoal",
    "AgentGoalType",
    "AgentIntegration",
    "RecommendedAction",
]
