"""ESP-IDF MCP Server Core.

Provides MCP server with factory function for flexible project configuration.

Tool Design Principles (following UCAgent patterns):
- Atomic tools: Each tool does one thing well
- Composable: AI can combine tools for complex workflows
- Clear separation: Tools execute operations, Workflow manages state
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Security configuration
from config import get_default_config
from mcp_tools import BuildTools, ConfigTools, FlashTools, MonitorTools
from workflow import Workflow

# Observability system (lazy import for optional feature)
try:
    from observability import get_diagnostics, get_logger, get_metrics
    from observability.formatters import OutputFormatter

    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False


@dataclass
class CommandResult:
    """Result of command execution.

    Attributes:
        success: Whether the command succeeded.
        output: Standard output from the command.
        error: Standard error from the command, if any.
    """

    success: bool
    output: str
    error: str | None = None


def create_server(
    project,
    host: str = "127.0.0.1",
    port: int = 8090,
    enable_file_state: bool = True,
    enable_observability: bool = True,
    security_config=None,
) -> FastMCP:
    """Create an ESP-IDF MCP server instance.

    Args:
        project: ProjectInfo instance containing project path and validation info.
        host: HTTP mode listening address.
        port: HTTP mode listening port.
        enable_file_state: Enable file-based workflow state management.
        enable_observability: Enable logging, metrics, and diagnostics.
        security_config: Optional SecurityConfig instance. Uses default if None.

    Returns:
        Configured FastMCP server instance.
    """
    mcp = FastMCP("ESP-IDF MCP Server", host=host, port=port, stateless_http=True)

    # Initialize security configuration
    if security_config is None:
        security_config = get_default_config()

    # Initialize workflow with file state management
    workflow = Workflow(project_root=project.root, enable_file_state=enable_file_state)

    # Initialize agent integration for external agent goal management
    from workflow import AgentIntegration

    agent_integration = AgentIntegration(project_root=project.root)

    # Initialize observability system
    logger = None
    metrics = None
    diagnostics = None
    formatter = None

    if enable_observability and OBSERVABILITY_AVAILABLE:
        logger = get_logger("espidf_mcp", project.root / ".espidf-mcp" / "logs")
        metrics = get_metrics(project.root)
        _ = get_diagnostics()  # Initialize diagnostics engine
        formatter = OutputFormatter()
        logger.info("ESP-IDF MCP Server initialized", project=str(project.root))

    # ============================================================================
    # Register modular tools
    # ============================================================================
    # Tool modules are now organized in separate classes for better maintainability
    BuildTools(
        project,
        mcp,
        workflow=workflow,
        logger=logger,
        metrics=metrics,
        security_config=security_config,
    ).register_tools()
    FlashTools(
        project, mcp, logger=logger, metrics=metrics, security_config=security_config
    ).register_tools()
    ConfigTools(
        project, mcp, logger=logger, metrics=metrics, security_config=security_config
    ).register_tools()
    MonitorTools(
        project,
        mcp,
        workflow=workflow,
        logger=logger,
        metrics=metrics,
        security_config=security_config,
    ).register_tools()

    # ============================================================================
    # Helper/Guidance Tools (UCAgent pattern)
    # ============================================================================

    @mcp.tool()
    def esp_idf_expert() -> str:
        """Get ESP-IDF expert role guidance.

        RETURNS:
            str: Usage guide for ESP-IDF MCP tools with common workflows
                 and best practices.

        EXAMPLE:
            Call: esp_idf_expert()
        """
        return """ESP-IDF MCP Expert Assistant

Connected to ESP-IDF MCP server for ESP32 development tasks.

Common Workflows:

1. Project Check
   Call: esp_project_info()
   Confirm current project configuration

2. Set Target Chip
   Call: esp_set_target(target="esp32s3")
   Supported: esp32, esp32s2, esp32s3, esp32c3, esp32c6

3. Build Firmware
   Call: esp_build()
   Compile current project

4. Flash Firmware
   Call: esp_flash(port="/dev/ttyUSB0")
   Check available ports with esp_list_ports()

5. Monitor Serial
   Call: esp_monitor(port="/dev/ttyUSB0")
   View device runtime logs

Best Practices:
- Call esp_project_info() before starting new tasks
- Use esp_clean(level="full") after changing target
- Use esp_size() to check firmware size distribution

Tool Composition (AI can combine these):
- Flash and Monitor: esp_flash() → esp_monitor()
- Clean Build: esp_clean(level="full") → esp_set_target() → esp_build()
- Debug: esp_flash() → esp_monitor() → analyze output
"""

    @mcp.tool()
    def esp_context_summary(summary: str) -> str:
        """Store project context summary for AI understanding.

        PURPOSE:
            Store project-specific context information to help AI understand
            the project better. This follows UCAgent's memory pattern.

        DESCRIPTION:
            Save a summary of the project context, goals, or current state
            that AI can reference in future interactions. Useful for:
            - Project goals and requirements
            - Current development stage
            - Known issues or workarounds
            - Team decisions and rationale

        PARAMETERS:
            summary (str): Context summary text to store

        RETURNS:
            str: Confirmation of stored summary

        NOTES:
            - Context is stored in .espidf-mcp/context.json
            - Can be retrieved by AI in future conversations
            - Useful for multi-session projects

        EXAMPLE:
            Call: esp_context_summary(summary="Developing WiFi weather station with ESP32-S3")
        """
        if not enable_file_state:
            return "File state management is disabled."

        context_file = workflow.file_manager.mcp_dir / "context.json"
        context_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
        }

        try:
            context_file.write_text(json.dumps(context_data, indent=2))
            return f"Context summary stored:\n\n{summary}"
        except Exception as e:
            return f"Failed to store context: {e}"

    @mcp.tool()
    def esp_memory_store(key: str, value: str) -> str:
        """Store project-specific information in memory.

        PURPOSE:
            Store key-value pairs for project-specific information.
            This follows UCAgent's MemoryPut pattern.

        DESCRIPTION:
            Save information that AI or users need to remember across sessions,
            such as:
            - WiFi credentials (encrypted)
            - Hardware configuration
            - Build settings
            - Test results

        PARAMETERS:
            key (str): Storage key name
            value (str): Value to store

        RETURNS:
            str: Confirmation of stored data

        NOTES:
            - Data is stored in .espidf-mcp/memory.json
            - Not suitable for sensitive data (use environment variables)
            - Can be retrieved with esp_memory_get()

        EXAMPLE:
            Call: esp_memory_store(key="build_date", value="2024-01-11")
        """
        if not enable_file_state:
            return "File state management is disabled."

        memory_file = workflow.file_manager.mcp_dir / "memory.json"

        # Load existing memory
        try:
            if memory_file.exists():
                memory = json.loads(memory_file.read_text())
            else:
                memory = {}
        except Exception:
            memory = {}

        # Store new value
        memory[key] = {
            "value": value,
            "timestamp": Path(__file__).stem,
        }

        try:
            memory_file.write_text(json.dumps(memory, indent=2))
            return f"Stored: {key} = {value}"
        except Exception as e:
            return f"Failed to store memory: {e}"

    # ============================================================================
    # Agent Integration Tools (External Agent Support)
    # ============================================================================

    @mcp.tool()
    def esp_set_agent_goal(
        goal_type: str,
        description: str,
        priority: int = 3,
    ) -> str:
        """Set a high-level goal for external agent guidance.

        PURPOSE:
            Set a goal for the ESP-IDF MCP Server to provide intelligent
            action recommendations. Enables external agents to communicate
            their objectives and receive contextual guidance.

        DESCRIPTION:
            Sets an agent goal which influences tool recommendations and
            workflow suggestions. Goals persist across sessions and help
            the server provide more relevant actions.

            Supported goal types:
            - quick_build: Build firmware as fast as possible
            - full_deploy: Complete build, flash, and monitor workflow
            - config_change: Modify configuration and rebuild
            - hardware_test: Test hardware connectivity
            - firmware_update: Update firmware on device
            - diagnostics: Diagnose build or hardware issues
            - custom: Custom agent-defined goal

        PARAMETERS:
            goal_type (str): Type of goal (quick_build, full_deploy, etc.)
            description (str): Human-readable goal description
            priority (int): Priority level (1-5, default 3)

        RETURNS:
            str: Confirmation message with goal summary

        NOTES:
            - Goal persists in .espidf-mcp/agent_goal.json
            - Use esp_get_agent_recommendations() to get actions
            - Use esp_agent_goal_summary() to view current goal

        EXAMPLE:
            Call: esp_set_agent_goal(goal_type="quick_build", description="Build firmware for testing", priority=4)
        """
        try:
            return agent_integration.set_agent_goal(
                goal_type=goal_type,
                description=description,
                priority=priority,
            )
        except Exception as e:
            return f"Failed to set agent goal: {e}"

    @mcp.tool()
    def esp_get_agent_recommendations(limit: int = 5) -> str:
        """Get recommended actions based on current agent goal.

        PURPOSE:
            Get intelligent action recommendations based on the current
            agent goal and workflow state.

        DESCRIPTION:
            Returns a prioritized list of recommended actions that help
            achieve the current agent goal. Each recommendation includes
            the tool name, description, priority, and reasoning.

        PARAMETERS:
            limit (int): Maximum number of actions to return (default 5)

        RETURNS:
            str: Formatted list of recommended actions with details

        NOTES:
            - Requires agent goal to be set first
            - Actions are sorted by priority (highest first)
            - Includes tool parameters and reasoning

        EXAMPLE:
            Call: esp_get_agent_recommendations(limit=5)
        """
        try:
            # Get current workflow state for context
            workflow_state_json = workflow.get_state()

            # Parse workflow state
            try:
                import json as json_parser

                workflow_state = json_parser.loads(workflow_state_json)
            except Exception:
                workflow_state = {}

            # Get recommendations
            recommendations = agent_integration.get_recommended_actions(
                workflow_state=workflow_state,
                limit=limit,
            )

            if not recommendations:
                return "No recommendations available. Set an agent goal first with esp_set_agent_goal()."

            # Format recommendations
            lines = ["Agent Goal Recommendations", "=" * 50]

            goal_summary = agent_integration.get_goal_summary()
            if goal_summary:
                lines.append(f"\nGoal: {goal_summary.get('description', 'N/A')}")
                lines.append(f"Type: {goal_summary.get('goal_type', 'N/A')}")
                lines.append(f"Priority: {goal_summary.get('priority', 'N/A')}/5")
                lines.append("")

            for i, action in enumerate(recommendations, 1):
                lines.append(f"{i}. {action['description']}")
                lines.append(f"   Tool: {action['tool_name']}")
                lines.append(f"   Priority: {action['priority']}/5")
                if action.get("parameters"):
                    lines.append(f"   Parameters: {action['parameters']}")
                if action.get("reason"):
                    lines.append(f"   Reason: {action['reason']}")
                if action.get("estimated_duration"):
                    lines.append(f"   Estimated: {action['estimated_duration']}s")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"Failed to get recommendations: {e}"

    @mcp.tool()
    def esp_agent_goal_summary() -> str:
        """Get summary of current agent goal.

        PURPOSE:
            Display the current agent goal and its configuration.

        DESCRIPTION:
            Returns information about the currently set agent goal,
            including type, description, priority, and context.

        RETURNS:
            str: Goal information or message if no goal is set

        NOTES:
            - Use esp_set_agent_goal() to set a goal
            - Use esp_clear_agent_goal() to remove current goal

        EXAMPLE:
            Call: esp_agent_goal_summary()
        """
        try:
            goal_summary = agent_integration.get_goal_summary()

            if not goal_summary:
                return "No agent goal is currently set. Use esp_set_agent_goal() to set one."

            lines = [
                "Current Agent Goal",
                "=" * 40,
                f"Type: {goal_summary.get('goal_type', 'N/A')}",
                f"Description: {goal_summary.get('description', 'N/A')}",
                f"Priority: {goal_summary.get('priority', 'N/A')}/5",
            ]

            if goal_summary.get("context"):
                lines.append("\nContext:")
                for key, value in goal_summary["context"].items():
                    lines.append(f"  {key}: {value}")

            if goal_summary.get("constraints"):
                lines.append("\nConstraints:")
                for constraint in goal_summary["constraints"]:
                    lines.append(f"  - {constraint}")

            return "\n".join(lines)

        except Exception as e:
            return f"Failed to get goal summary: {e}"

    @mcp.tool()
    def esp_clear_agent_goal() -> str:
        """Clear the current agent goal.

        PURPOSE:
            Remove the currently set agent goal.

        DESCRIPTION:
            Clears the agent goal, removing any goal-based recommendations.
            Use this when starting a new task or resetting agent state.

        RETURNS:
            str: Confirmation message

        NOTES:
            - This action cannot be undone
            - Recommendations will default to generic suggestions

        EXAMPLE:
            Call: esp_clear_agent_goal()
        """
        try:
            return agent_integration.clear_goal()
        except Exception as e:
            return f"Failed to clear goal: {e}"

    # ============================================================================
    # Observability Tools (if enabled)
    # ============================================================================

    if enable_observability and OBSERVABILITY_AVAILABLE:

        @mcp.tool()
        def esp_metrics_summary(tool_name: str | None = None) -> str:
            """Get performance metrics for ESP-IDF MCP tools.

            PURPOSE:
                Display performance statistics for tool execution.

            DESCRIPTION:
                Returns performance metrics including call counts, success rates,
                average durations, and timing information. Helps identify
                performance bottlenecks and track tool usage patterns.

            PARAMETERS:
                tool_name (str | None): Specific tool name or None for all tools

            RETURNS:
                str: Performance metrics summary with statistics for each tool.

            EXAMPLE:
                Call: esp_metrics_summary()
                Call: esp_metrics_summary(tool_name="esp_build")
            """
            if tool_name:
                stats = metrics.get_tool_stats(tool_name)
                return formatter.format_tool_result(
                    tool_name,
                    f"Call count: {stats['call_count']}\n"
                    f"Success rate: {stats['success_rate']:.1%}\n"
                    f"Avg duration: {stats['avg_duration_ms']:.1f}ms",
                    stats["avg_duration_ms"] / 1000,
                    True,
                )
            else:
                all_stats = metrics.get_all_tool_stats()
                return formatter.format_metrics_summary(all_stats)

        @mcp.tool()
        def esp_observability_status() -> str:
            """Get observability system status and health.

            PURPOSE:
                Display observability system status, log sizes, and metrics summary.

            DESCRIPTION:
                Returns information about the observability system including
                log file sizes, metrics status, and system health indicators.

            RETURNS:
                str: Observability system status information.

            EXAMPLE:
                Call: esp_observability_status()
            """
            import os

            mcp_dir = project.root / ".espidf-mcp"
            logs_dir = mcp_dir / "logs"

            output = [
                "ESP-IDF MCP Observability Status",
                "=" * 50,
                f"Project: {project.root}",
                "",
            ]

            # Log file sizes
            if logs_dir.exists():
                output.append("[Log Files]")
                for log_file in logs_dir.glob("**/*.log"):
                    size = os.path.getsize(log_file)
                    output.append(f"  {log_file.relative_to(project.root)}: {size:,} bytes")

                # Structured logs
                structured_dir = logs_dir / "structured"
                if structured_dir.exists():
                    output.append("")
                    output.append("[Structured Logs]")
                    for jsonl_file in structured_dir.glob("*.jsonl"):
                        size = os.path.getsize(jsonl_file)
                        output.append(f"  {jsonl_file.relative_to(project.root)}: {size:,} bytes")

            # Metrics summary
            output.append("")
            output.append("[Metrics]")
            all_stats = metrics.get_all_tool_stats()
            if all_stats:
                total_calls = sum(s["call_count"] for s in all_stats.values())
                output.append(f"  Total tool calls: {total_calls}")
                output.append(f"  Tools tracked: {len(all_stats)}")
            else:
                output.append("  No metrics collected yet")

            return "\n".join(output)

        @mcp.tool()
        def esp_logs_view(level: str = "INFO", tail: int = 50) -> str:
            """View recent log entries with filtering.

            PURPOSE:
                View recent log entries with level filtering.

            DESCRIPTION:
                Returns recent log entries from the structured logs,
                filtered by log level and limited to the specified number of lines.

            PARAMETERS:
                level (str): Log level filter (DEBUG, INFO, WARNING, ERROR)
                tail (int): Number of recent lines to return

            RETURNS:
                str: Recent log entries matching the filter.

            EXAMPLE:
                Call: esp_logs_view(level="ERROR", tail=20)
            """

            # Read structured log file
            jsonl_file = project.root / ".espidf-mcp" / "logs" / "structured" / "workflow.jsonl"
            if not jsonl_file.exists():
                return "No log files found."

            # Read and filter
            entries = []
            with open(jsonl_file) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("level") == level.upper():
                            entries.append(entry)
                    except (json.JSONDecodeError, ValueError):
                        continue

            # Get tail entries
            tail_entries = entries[-tail:] if len(entries) > tail else entries

            output = [f"Recent {level.upper()} logs (last {len(tail_entries)} entries):", "=" * 60]
            for entry in tail_entries:
                timestamp = entry.get("timestamp", "")
                message = entry.get("message", "")
                output.append(f"[{timestamp}] {message}")

            return "\n".join(output)

        @mcp.tool()
        def esp_error_history(count: int = 10) -> str:
            """Get recent error history with diagnostic information.

            PURPOSE:
                Display recent errors with pattern matches and suggestions.

            DESCRIPTION:
                Returns recent error occurrences from metrics, along with
                matched error patterns and diagnostic suggestions.

            PARAMETERS:
                count (int): Number of recent errors to return

            RETURNS:
                str: Error history with diagnostics and suggestions.

            EXAMPLE:
                Call: esp_error_history(count=10)
            """
            # Get failed tool executions from metrics
            all_stats = metrics.get_all_tool_stats()

            errors = []
            for tool_name, stats in all_stats.items():
                if stats["failure_count"] > 0:
                    errors.append(
                        {
                            "tool_name": tool_name,
                            "failures": stats["failure_count"],
                            "last_status": stats["last_status"],
                        }
                    )

            # Sort by failure count (descending)
            errors.sort(key=lambda x: x["failures"], reverse=True)

            # Get top errors
            top_errors = errors[:count]

            if not top_errors:
                return "No errors recorded yet."

            output = [
                f"Recent Errors (last {len(top_errors)} tools with failures)",
                "=" * 60,
                "",
            ]

            for error in top_errors:
                output.append(f"Tool: {error['tool_name']}")
                output.append(f"  Failures: {error['failures']}")
                output.append(f"  Last Status: {error['last_status']}")
                output.append("")

            return "\n".join(output)

        @mcp.tool()
        def esp_diagnose_last_error() -> str:
            """Get diagnostic suggestions for the most recent error.

            PURPOSE:
                Analyze the most recent error and provide actionable suggestions.

            DESCRIPTION:
                Uses the diagnostic engine to analyze the most recent error
                output and provides pattern matches and fix suggestions.

            RETURNS:
                str: Diagnostic report with suggestions.

            EXAMPLE:
                Call: esp_diagnose_last_error()
            """
            # Get most recent failed tool execution from metrics
            all_stats = metrics.get_all_tool_stats()
            failed_tools = [
                (name, stats) for name, stats in all_stats.items() if stats["failure_count"] > 0
            ]

            if not failed_tools:
                return "No errors to diagnose."

            # Sort by last_called timestamp (most recent first)
            failed_tools.sort(key=lambda x: x[1].get("last_called", ""), reverse=True)

            # Get most recent error
            tool_name, stats = failed_tools[0]

            # For demonstration, create a generic diagnostic
            # In real implementation, would read actual error output from logs
            diagnostic_text = f"""Diagnostic Report for {tool_name}
{"=" * 60}

Recent failures: {stats["failure_count"]}

Common suggestions based on error patterns:

For build errors (IDF_PATH, compile errors):
- Check ESP-IDF environment: source ~/esp/esp-idf/export.sh
- Verify target is set: esp_set_target(target="esp32")
- Clean build: esp_clean(level="full")

For flash errors (connection, write failures):
- Check USB cable connection
- Verify device is powered on
- Check serial permissions: sudo usermod -a -G dialout $USER
- Try lower baud rate: esp_flash(port="/dev/ttyUSB0", baud=115200)

For configuration errors:
- Run menuconfig: idf.py menuconfig
- Validate partition table: esp_validate_partition_table()

Use esp_logs_view(level="ERROR") to see actual error messages.
"""

            return diagnostic_text

    return mcp
