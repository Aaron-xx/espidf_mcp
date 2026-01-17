"""Monitor tools for ESP-IDF MCP Server.

Provides monitoring and workflow state functionality:
- Workflow state query tools
- Stage status tracking
- File-based state management
"""

from .base import BaseTool


class MonitorTools(BaseTool):
    """Monitoring and workflow state tools for ESP-IDF development."""

    def register_tools(self) -> None:
        """Register all monitor tools with the MCP server."""

        @self.mcp.tool()
        @self._log_tool_call
        def esp_workflow_state() -> str:
            """Get detailed workflow state from files.

            PURPOSE:
                Get complete workflow state including stage status,
                dependencies, and progress information.

            DESCRIPTION:
                Returns detailed workflow state by reading from
                .espidf-mcp/workflow/state.json and stage status files.
                This follows UCAgent pattern of providing state query tools.

            RETURNS:
                str: Detailed workflow state information with:
                    - Overall progress percentage
                    - Completed/pending/failed stages
                    - Stage status with file timestamps
                    - Dependency relationships

            NOTES:
                - File state persists across sessions
                - Each stage tracks execution history

            EXAMPLE:
                Call: esp_workflow_state()
            """
            if self.workflow is None:
                return "Workflow state management is disabled."

            progress = self.workflow.get_progress()
            stages = self.workflow.list_stages()

            output = [
                "ESP-IDF MCP Workflow State",
                "=" * 40,
                f"Progress: {progress['progress_percent']:.1f}%",
                f"Completed: {progress['completed']}/{progress['total_stages']}",
                f"Current: {progress.get('current', 'None')}",
                "",
                "Stage Details:",
            ]

            for stage in stages:
                status = stage.status.value.upper()
                deps = f" (deps: {', '.join(stage.depends_on)})" if stage.depends_on else ""

                # Get file status
                stage_output = self.workflow.get_stage_output(stage.name)
                file_info = ""
                if stage_output:
                    file_info = f" [file: {stage_output.timestamp.split('T')[1][:8]}]"

                output.append(f"  [{status}]{file_info} {stage.name}{deps}")

            return "\n".join(output)

        @self.mcp.tool()
        @self._log_tool_call
        def esp_workflow_files() -> str:
            """Show workflow file structure and state.

            PURPOSE:
                Display the file-based workflow state management structure
                and current status of all stages.

            DESCRIPTION:
                Shows the .espidf-mcp/ directory structure, workflow state,
                and completion status of each stage based on stored files.
                This follows UCAgent pattern of transparent state management.

            RETURNS:
                str: Workflow file structure and status information.

            NOTES:
                - File state persists across sessions
                - Each stage has its own directory with output and status
                - History is maintained in workflow/history.json

            EXAMPLE:
                Call: esp_workflow_files()
            """
            if self.workflow is None:
                return "Workflow state management is disabled."

            output = [
                "ESP-IDF MCP File-Based Workflow State",
                "=" * 50,
                f"Project: {self.project.root}",
                f"State Directory: {self.workflow.file_manager.mcp_dir}",
                "",
                "[Workflow State]",
            ]

            # Get workflow state
            state = self.workflow.get_workflow_state()
            output.extend(
                [
                    f"  Created: {state.get('created_at', 'N/A')}",
                    f"  Last Stage: {state.get('last_stage', 'None')}",
                    f"  Last Update: {state.get('last_update', 'None')}",
                    f"  Stages Completed: {state.get('stages_completed', 0)}",
                    "",
                    "[Stage Status from Files]",
                ]
            )

            for stage_name in ["init", "config", "build", "flash", "monitor"]:
                stage_status = self.workflow.get_stage_output(stage_name)
                if stage_status:
                    icon = "✓" if stage_status.success else "✗"
                    output.append(
                        f"  {icon} {stage_name}: {stage_status.timestamp} "
                        f"(exit: {stage_status.exit_code}, duration: {stage_status.duration_seconds:.2f}s)"
                    )
                    if stage_status.artifacts:
                        output.append(f"      Artifacts: {len(stage_status.artifacts)} files")
                else:
                    output.append(f"  ○ {stage_name}: Not yet executed")

            return "\n".join(output)
