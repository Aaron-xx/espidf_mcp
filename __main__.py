#!/usr/bin/env python3
"""ESP-IDF MCP Server - Python module execution entry.

Usage:
    cd /path/to/esp32_project
    source ~/esp-idf/export.sh
    python -m espidf_mcp                         # stdio mode
    python -m espidf_mcp --http --port 8090  # HTTP mode
"""


def main() -> None:
    """Python module execution main entry point.

    Returns:
        None
    """
    from cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
