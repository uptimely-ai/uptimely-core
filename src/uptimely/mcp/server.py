"""Start and register the Uptimely MCP server."""

import argparse
import logging
import pathlib
import sys

import fastmcp

from . import analytical, diagnostics, state

logger = logging.getLogger(__name__)

INSTRUCTIONS = (
    "For analytical results, discover bound operators with list_operators "
    "and use execute_operator or execute_function to run only the requested "
    "operator and its prerequisites. Use describe_spec for model counts, "
    "and describe_last_run or read_last_run_logs for existing diagnostics. "
    "Build tools are supporting introspection, not required execution steps. "
    "Do not claim a date scope or data freshness not guaranteed by project sources."
)


def create_server(server_state: state.ServerState) -> fastmcp.FastMCP:
    """Create an MCP server with tools bound to the given project state.

    Args:
        server_state: Project configuration and saved-build cache for this server.

    Returns:
        A configured FastMCP server.
    """
    server = fastmcp.FastMCP("uptimely", instructions=INSTRUCTIONS)
    analytical.AnalyticalTools(server_state).register(server)
    diagnostics.RunDiagnostics(server_state).register(server)
    return server


def main() -> None:
    """Launch the Uptimely MCP server over stdio."""
    parser = argparse.ArgumentParser(description="Uptimely MCP server")
    parser.add_argument(
        "--project-root",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help="Analytics project root containing the last successful build",
    )
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        default=None,
        help="JSON file with engine settings and global parameters",
    )
    args = parser.parse_args()

    # Log to stderr only because stdout is the MCP protocol channel.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    logger.info("Starting uptimely MCP server for project %s", args.project_root)

    runtime_config = state.ServerState.load_config(args.config, args.project_root)
    server_state = state.ServerState(project_root=args.project_root, config=runtime_config)
    create_server(server_state).run()


if __name__ == "__main__":
    sys.exit(main())
