"""Command-line tools for building and serving the analytics explorer."""

import argparse
import functools
import logging
import pathlib
from http import server as http_server

from uptimely import project

logger = logging.getLogger(__name__)


def serve_explorer(
    directory: pathlib.Path,
    host: str = "127.0.0.1",
    port: int = 8001,
    scope: str = "all features",
) -> None:
    """Serve a saved analytics explorer website for local preview.

    Args:
        directory: Saved website directory containing an index.html file.
        host: Address to bind; defaults to localhost.
        port: TCP port; defaults to 8001. Zero selects an available port.
        scope: Human-readable scope of the saved execution plan.

    Raises:
        NotADirectoryError: The website directory does not exist or is not a directory.
        FileNotFoundError: The website index is missing.
        ValueError: The port is outside the valid TCP range.
        OSError: The server cannot bind to the requested address.
    """
    directory = directory.resolve()
    if not directory.is_dir():
        raise NotADirectoryError(f"Website directory does not exist: {directory}")
    index = directory / project.EXPLORER_INDEX_FILE.name
    if not index.is_file():
        raise FileNotFoundError(
            f"Website index not found: {index}. Generate it with 'uptimely project build'."
        )
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535.")
    handler = functools.partial(http_server.SimpleHTTPRequestHandler, directory=str(directory))
    with http_server.ThreadingHTTPServer((host, port), handler) as server:
        logger.info(
            "Serving analytics explorer from %s at http://%s:%d/ (build scope: %s; Ctrl+C to stop)",
            directory,
            host,
            server.server_port,
            scope,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Spec explorer server stopped.")


def _port(value: str) -> int:
    """Parse a valid TCP port for the CLI."""
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Port must be an integer.") from error
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 0 and 65535.")
    return port


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the Explorer serve action."""
    actions = parser.add_subparsers(dest="action", required=True)
    serve = actions.add_parser("serve", help="Serve the active build's saved website")
    serve.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Project root containing the active build",
    )
    serve.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    serve.add_argument(
        "--port", type=_port, default=8001, help="TCP port (default: 8001; 0 selects a free port)"
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Serve the active build's validated, saved Explorer website."""
    project_root = (args.project_root or pathlib.Path.cwd()).resolve()
    try:
        with project.read_build_bundle(project_root) as bundle:
            scope = (
                "all features"
                if bundle.manifest.features is None
                else f"selected features: {', '.join(bundle.manifest.features)}"
            )
            serve_explorer(bundle.explorer_path, args.host, args.port, scope)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
