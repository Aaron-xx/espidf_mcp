"""ESP-IDF MCP Server - CLI entry point.

Provides command-line interface with automatic project detection
and MCP server startup.
"""

import sys


def main() -> None:
    """Main entry point - called by espidf-mcp command.

    This function:
        1. Parses command-line arguments
        2. Detects ESP-IDF project
        3. Validates project and displays friendly errors/warnings
        4. Starts MCP server (stdio or HTTP mode)

    Returns:
        None
    """
    from project import ProjectInfo
    from server import create_server

    # Parse command-line arguments
    host = "127.0.0.1"
    port = 8090
    http_mode = "--http" in sys.argv

    if http_mode:
        if "--port" in sys.argv:
            port_idx = sys.argv.index("--port")
            if port_idx + 1 < len(sys.argv):
                port = int(sys.argv[port_idx + 1])
        if "--host" in sys.argv:
            host_idx = sys.argv.index("--host")
            if host_idx + 1 < len(sys.argv):
                host = sys.argv[host_idx + 1]

    # Detect project
    project = ProjectInfo.detect()
    is_valid, message = project.validate()

    # Display startup information
    print("=" * 60)
    print("ESP-IDF MCP Server")
    print("=" * 60)

    if not is_valid:
        print("WARNING: Not in an ESP-IDF project directory")
        print(f"Info: {message}")
        print("\nSuggestions:")
        for suggestion in project.get_error_suggestions():
            print(f"  - {suggestion}")
        print("\nStarting server anyway (tools will fail with errors)")
        print("=" * 60)
    else:
        print(f"ESP-IDF project detected: {project.root.name}")
        print(f"Project directory: {project.root}")
        print("=" * 60)

    # Create and start server
    mcp = create_server(project=project, host=host, port=port)

    try:
        if http_mode:
            print(f"Starting HTTP server: http://{host}:{port}/mcp\n")
            mcp.run(transport="streamable-http")
        else:
            print("Starting stdio mode (MCP client connection)\n")
            mcp.run()
    except KeyboardInterrupt:
        # Exit gracefully on Ctrl+C without traceback
        sys.exit(0)
