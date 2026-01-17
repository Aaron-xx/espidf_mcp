# ESP-IDF MCP Server - Agent Integration Guide

This guide explains how external agents can use the ESP-IDF MCP Server's agent integration features to receive intelligent guidance and action recommendations.

## Overview

The agent integration system enables external AI agents to:
- Set high-level goals for ESP-IDF development tasks
- Receive context-aware action recommendations
- Maintain goal state across sessions
- Get prioritized action lists with reasoning

## Agent Goals

### Goal Types

| Goal Type | Description | Use Case |
|-----------|-------------|----------|
| `quick_build` | Build firmware as fast as possible | Quick compilation for testing |
| `full_deploy` | Complete build, flash, and monitor | Deploy firmware to device |
| `config_change` | Modify configuration and rebuild | Change target or settings |
| `hardware_test` | Test hardware connectivity | Verify device connection |
| `firmware_update` | Update firmware on device | Re-flash device |
| `diagnostics` | Diagnose build or hardware issues | Troubleshoot problems |
| `custom` | Custom agent-defined goal | Specialized tasks |

## MCP Tools

### 1. esp_set_agent_goal

Set a high-level goal for the server to guide recommendations.

**Parameters:**
- `goal_type` (str): Type of goal
- `description` (str): Human-readable goal description
- `priority` (int): Priority level 1-5 (default 3)

**Example:**
```python
esp_set_agent_goal(
    goal_type="quick_build",
    description="Build firmware for quick testing",
    priority=4
)
```

### 2. esp_get_agent_recommendations

Get recommended actions based on current goal.

**Parameters:**
- `limit` (int): Maximum actions to return (default 5)

**Returns:**
- Tool name
- Description
- Priority
- Parameters
- Reasoning
- Estimated duration

### 3. esp_agent_goal_summary

Display current goal configuration.

### 4. esp_clear_agent_goal

Remove the current goal.

## Usage Patterns

### Quick Build Workflow
```python
esp_set_agent_goal(goal_type="quick_build", description="Build for testing")
actions = esp_get_agent_recommendations(limit=5)
for action in parse_actions(actions):
    call_tool(action['tool_name'], **action['parameters'])
```

### Full Deployment Workflow
```python
esp_set_agent_goal(goal_type="full_deploy", description="Deploy to ESP32-S3")
actions = esp_get_agent_recommendations()
for action in actions:
    if action['priority'] >= 4:
        execute_action(action)
```

## Best Practices

1. Always set a goal first
2. Check goal summary to verify
3. Execute by priority order
4. Handle errors gracefully
5. Clear goals when done
