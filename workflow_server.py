"""ESP-IDF MCP Workflow Server.

Extends the base MCP server with workflow management capabilities including:
- Stage-based development workflow
- Checker validation system
- Progress tracking and reporting
"""

from mcp.server.fastmcp import FastMCP

from checkers import (
    BuildArtifactsChecker,
    CheckerRegistry,
    ProjectStructureChecker,
    TargetConfigChecker,
)
from config import Config
from workflow import Workflow


def create_workflow_server(
    project,
    config: Config | None = None,
    host: str = "127.0.0.1",
    port: int = 8090,
) -> FastMCP:
    """Create an ESP-IDF MCP server with workflow support.

    Args:
        project: ProjectInfo instance.
        config: Optional configuration.
        host: HTTP server host.
        port: HTTP server port.

    Returns:
        Configured FastMCP server with workflow tools.
    """
    config = config or Config.load()
    mcp = FastMCP("ESP-IDF MCP Workflow", host=host, port=port, stateless_http=True)

    # Initialize checker registry with built-in checkers
    checker_registry = CheckerRegistry()
    checker_registry.register(ProjectStructureChecker)
    checker_registry.register(BuildArtifactsChecker)
    checker_registry.register(TargetConfigChecker)

    # Initialize workflow
    workflow = Workflow(
        checker_registry=checker_registry,
        project_root=project.root,
    )

    @mcp.tool()
    def esp_workflow_status() -> str:
        """Get current workflow status and progress.

        PURPOSE:
            Display the current state of the ESP-IDF development workflow.

        DESCRIPTION:
            Shows workflow progress including completed stages, current stage,
            and overall completion percentage. Use to track development progress.

        RETURNS:
            str: Formatted workflow status with stage information.
        """
        progress = workflow.get_progress()
        stages = workflow.list_stages()

        output = [
            "ESP-IDF Workflow Status",
            "=" * 40,
            f"Progress: {progress['progress_percent']:.1f}%",
            f"Completed: {progress['completed']}/{progress['total_stages']}",
            "",
            "Stages:",
        ]

        for stage in stages:
            status = stage.status.value
            current = " <-" if stage.name == progress.get("current") else ""
            output.append(f"  [{status}] {stage.name}: {stage.description}{current}")

        return "\n".join(output)

    @mcp.tool()
    def esp_workflow_list() -> str:
        """List all workflow stages.

        PURPOSE:
            Display all available workflow stages in dependency order.

        DESCRIPTION:
            Shows each stage with its description, tasks, and dependencies.
            Use to understand the complete development workflow.

        RETURNS:
            str: Formatted list of all stages.
        """
        stages = workflow.list_stages()
        output = ["ESP-IDF Workflow Stages", "=" * 40]

        for i, stage in enumerate(stages, 1):
            deps = f" (depends on: {', '.join(stage.depends_on)})" if stage.depends_on else ""
            output.append(f"\n{i}. {stage.name}{deps}")
            output.append(f"   {stage.description}")

            if stage.tasks:
                output.append("   Tasks:")
                for task in stage.tasks:
                    output.append(f"     - {task}")

            if stage.checkers:
                output.append(f"   Checkers: {', '.join(stage.checkers)}")

        return "\n".join(output)

    @mcp.tool()
    def esp_workflow_next() -> str:
        """Get the next recommended workflow stage.

        PURPOSE:
            Identify the next stage to execute based on current progress.

        DESCRIPTION:
            Returns the next pending stage that has all dependencies satisfied.
            Use to plan next steps in development workflow.

        RETURNS:
            str: Information about the next stage or completion message.
        """
        next_stage = workflow.get_next_stage()

        if not next_stage:
            return "All stages completed! Workflow finished."

        output = [
            f"Next Stage: {next_stage.name}",
            f"Description: {next_stage.description}",
            "",
            "Tasks:",
        ]
        for task in next_stage.tasks:
            output.append(f"  - {task}")

        if next_stage.depends_on:
            output.append(f"\nDependencies satisfied: {', '.join(next_stage.depends_on)}")

        output.append("\nTo start this stage, use workflow tools or run commands directly.")

        return "\n".join(output)

    @mcp.tool()
    def esp_workflow_validate(stage: str) -> str:
        """Run checkers for a specific workflow stage.

        PURPOSE:
            Validate a workflow stage by running its checkers.

        DESCRIPTION:
            Executes all registered checkers for the specified stage.
            Checkers validate project state, build artifacts, and configuration.

        PARAMETERS:
            stage (str): Stage name to validate
                - Examples: "init", "config", "build"
                - Required: Yes

        RETURNS:
            str: Validation results with pass/fail status and suggestions.
        """
        reports = workflow.validate_stage(stage)

        if not reports:
            return f"No checkers found for stage '{stage}'"

        output = [f"Validation Results for Stage '{stage}'", "=" * 40]

        for report in reports:
            status_icon = {
                "pass": "✓",
                "fail": "✗",
                "warning": "⚠",
                "skip": "→",
            }.get(report.result.value, "?")

            output.append(f"\n{status_icon} {report.checker_name}: {report.result.value.upper()}")
            output.append(f"  {report.message}")

            if report.details:
                output.append(f"  Details: {report.details}")

            if report.suggestions:
                output.append("  Suggestions:")
                for suggestion in report.suggestions:
                    output.append(f"    - {suggestion}")

        return "\n".join(output)

    @mcp.tool()
    def esp_check_project() -> str:
        """Run project structure validation.

        PURPOSE:
            Validate current directory is a valid ESP-IDF project.

        DESCRIPTION:
            Checks for CMakeLists.txt, validates project structure,
            and provides suggestions if issues are found.

        RETURNS:
            str: Validation result with status and suggestions.
        """
        report = checker_registry.run_check("project_structure", project.root)

        status = "PASS" if report.is_pass() else "FAIL" if report.is_fail() else "WARNING"
        output = [
            f"Project Structure Check: {status}",
            "-" * 40,
            report.message,
        ]

        if report.details:
            output.append(f"\nDetails: {report.details}")

        if report.suggestions:
            output.append("\nSuggestions:")
            for suggestion in report.suggestions:
                output.append(f"  - {suggestion}")

        return "\n".join(output)

    @mcp.tool()
    def esp_check_build() -> str:
        """Run build artifacts validation.

        PURPOSE:
            Verify build artifacts exist and are valid.

        DESCRIPTION:
            Checks build/ directory for firmware binaries and
            validates build completion.

        RETURNS:
            str: Validation result with status.
        """
        report = checker_registry.run_check("build_artifacts", project.root)

        status = "PASS" if report.is_pass() else "FAIL"
        output = [
            f"Build Artifacts Check: {status}",
            "-" * 40,
            report.message,
        ]

        if report.details:
            output.append(f"\nDetails: {report.details}")

        if report.suggestions:
            output.append("\nSuggestions:")
            for suggestion in report.suggestions:
                output.append(f"  - {suggestion}")

        return "\n".join(output)

    @mcp.tool()
    def esp_check_target() -> str:
        """Run target chip configuration validation.

        PURPOSE:
            Verify ESP-IDF target chip is configured.

        DESCRIPTION:
            Checks sdkconfig for target chip configuration.
            Suggests set-target if not configured.

        RETURNS:
            str: Validation result with status and suggestions.
        """
        report = checker_registry.run_check("target_config", project.root)

        status = "PASS" if report.is_pass() else "WARNING"
        output = [
            f"Target Config Check: {status}",
            "-" * 40,
            report.message,
        ]

        if report.details:
            output.append(f"\nDetails: {report.details}")

        if report.suggestions:
            output.append("\nSuggestions:")
            for suggestion in report.suggestions:
                output.append(f"  - {suggestion}")

        return "\n".join(output)

    @mcp.tool()
    def esp_workflow_guide() -> str:
        """Get workflow usage guide.

        PURPOSE:
            Display comprehensive guide for using ESP-IDF workflow tools.

        DESCRIPTION:
            Shows how to use workflow tools for structured ESP-IDF development,
            including stage progression and validation.

        RETURNS:
            str: Usage guide and examples.
        """
        return """ESP-IDF MCP Workflow Guide

The workflow system provides structured ESP-IDF development with validation.

Quick Start:

1. Check Project Status
   Call: esp_check_project()
   Validates project structure

2. View Workflow Stages
   Call: esp_workflow_list()
   Shows all available stages

3. Get Next Stage
   Call: esp_workflow_next()
   Identifies next step

4. Validate Current Stage
   Call: esp_workflow_validate(stage="init")
   Runs checkers for the stage

5. Check Progress
   Call: esp_workflow_status()
   Shows overall progress

Workflow Stages:

  init      - Project initialization and validation
  config    - Target chip configuration
  build     - Build firmware
  flash     - Flash firmware to device
  monitor   - Monitor device output

Validation Tools:

  esp_check_project() - Validate project structure
  esp_check_target()  - Check target configuration
  esp_check_build()   - Verify build artifacts

Typical Workflow:

  1. esp_check_project()       - Ensure project is valid
  2. esp_check_target()        - Verify target is set
  3. esp_set_target(...)       - Set target if needed
  4. esp_build()               - Build firmware
  5. esp_check_build()         - Verify build artifacts
  6. esp_flash(port="...")     - Flash to device
  7. esp_monitor(port="...")   - Monitor output
"""

    return mcp
