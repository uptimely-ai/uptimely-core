"""Command-line tools for building and serving the analytics explorer."""

import argparse
import logging
import pathlib

from uptimely import project
from uptimely.cli import common
from uptimely.explorer import export as explorer_export
from uptimely.explorer import server as explorer_server

logger = logging.getLogger(__name__)


def serve_explorer(
    project_root: pathlib.Path,
    host: str = "127.0.0.1",
    port: int = 8001,
    scope: str = "all features",
) -> None:
    """Serve the packaged analytics explorer frontend for local preview.

    Args:
        project_root: Project root containing the generated Explorer snapshot.
        host: Address to bind; defaults to localhost.
        port: TCP port; defaults to 8001. Zero selects an available port.
        scope: Human-readable scope of the saved execution plan.

    Raises:
        NotADirectoryError: The project root does not exist or is not a directory.
        FileNotFoundError: Packaged Explorer assets are missing.
        ValueError: The port is outside the valid TCP range.
        OSError: The server cannot bind to the requested address.
    """
    explorer_server.serve_explorer(project_root, host=host, port=port, scope=scope)


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
    """Configure Explorer commands."""
    actions = parser.add_subparsers(dest="action", required=True)
    serve = actions.add_parser("serve", help="Serve the active build's Explorer data")
    configure_serve_parser(serve)
    export = actions.add_parser("export", help="Export the static frontend and Explorer snapshot")
    configure_export_parser(export)


def configure_serve_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the Explorer serve command."""
    common.configure_project_root_arguments(
        parser,
        option_help="Project root containing the active build",
    )
    common.configure_src_path_argument(parser)
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build and publish the project snapshot once before serving it",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument(
        "--port", type=_port, default=8001, help="TCP port (default: 8001; 0 selects a free port)"
    )


def configure_export_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the static Explorer export command."""
    common.configure_project_root_arguments(
        parser,
        option_help="Project root containing the Explorer snapshot",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        required=True,
        help="Output directory or ZIP file (a .zip suffix selects ZIP output)",
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Run an Explorer command."""
    project_root = common.resolve_project_root(args, parser).resolve()
    if getattr(args, "action", "serve") == "export":
        try:
            output = explorer_export.export_static(project_root, args.output)
            logger.info("Explorer export created at %s", output)
        except (OSError, ValueError, RuntimeError) as error:
            common.exit_with_error(parser, error)
        return

    try:
        if args.build:
            bundle = project.build(project_root, src_path=args.src_path)
            logger.info("Build files created to %s", bundle.root)
        bundle = project.load_build_bundle(project_root)
        scope = (
            "all features"
            if bundle.manifest.features is None
            else f"selected features: {', '.join(bundle.manifest.features)}"
        )
        serve_explorer(project_root, args.host, args.port, scope)
    except (OSError, ValueError, RuntimeError) as error:
        common.exit_with_error(parser, error)
