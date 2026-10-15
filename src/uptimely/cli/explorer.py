"""Command-line tools for building and serving the analytics explorer."""

import argparse
import functools
import pathlib
from http import server as http_server

import jinja2

from uptimely.cli import common
from uptimely.explorer import explorer as explorer_module

GENERATED_ANALYTICS_PATH: pathlib.Path = common.GENERATED_ANALYTICS_PATH
GENERATED_EXPLORER_PATH: pathlib.Path = pathlib.Path("_generated/explorer")


def build_explorer(
    analytics_definition: pathlib.Path,
    output: pathlib.Path,
    project_root: pathlib.Path,
    include_generated_at: bool = False,
) -> pathlib.Path:
    """Build the static analytics explorer website.

    Args:
        analytics_definition: Path to the JSON analytics document.
        output: Directory for the website index and report pages.
        project_root: Directory added to the import path for function entrypoints.
        include_generated_at: Include a timestamp on the analytics page.

    Returns:
        The path to the website index.
    """
    analytics_definition = common.load_analytics(analytics_definition, project_root)
    return explorer_module.Explorer(analytics_definition).create_html(
        output / "index.html", include_generated_at=include_generated_at
    )


def serve_explorer(directory: pathlib.Path, host: str = "127.0.0.1", port: int = 8001) -> None:
    """Serve an existing analytics explorer website for local preview.

    Args:
        directory: Website directory containing an index.html file.
        host: Address to bind; defaults to localhost.
        port: TCP port; defaults to 8001. Zero selects an available port.

    Raises:
        NotADirectoryError: The website directory does not exist or is not a directory.
        FileNotFoundError: The website index is missing.
        ValueError: The port is outside the valid TCP range.
        OSError: The server cannot bind to the requested address.
    """
    directory = directory.resolve()
    if not directory.is_dir():
        raise NotADirectoryError(f"Website directory does not exist: {directory}")
    if not (directory / "index.html").is_file():
        raise FileNotFoundError(
            f"Website index not found: {directory / 'index.html'}. "
            "Run 'uptimely explorer build' first."
        )
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535.")
    handler = functools.partial(http_server.SimpleHTTPRequestHandler, directory=str(directory))
    with http_server.ThreadingHTTPServer((host, port), handler) as server:
        print(
            f"Serving analytics explorer from {directory} at "
            f"http://{host}:{server.server_port}/ (Ctrl+C to stop)",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nAnalytics explorer server stopped.")


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
    """Configure the explorer command and its build and serve actions."""
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser(
        "build", help="Build the analytics, feature graph, and execution plan website"
    )
    build.add_argument(
        "--spec",
        type=pathlib.Path,
        help=(
            "Analytics JSON path (required unless --project-root is set; "
            "then defaults to _generated/spec/spec.json under that root)"
        ),
    )
    build.add_argument(
        "--output",
        type=pathlib.Path,
        help=(
            "Website directory (defaults to _generated/explorer under --project-root, "
            "or _generated/explorer otherwise)"
        ),
    )
    build.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Root for importing function entrypoints and resolving default paths",
    )
    build.add_argument(
        "--include-generated-at",
        action="store_true",
        help="Include a build timestamp on the analytics page",
    )
    serve = actions.add_parser(
        "serve", help="Build and serve the generated website for local preview"
    )
    serve.add_argument(
        "--spec",
        type=pathlib.Path,
        help=(
            "Analytics JSON path (defaults to _generated/spec/spec.json under "
            "--project-root, or _generated/spec/spec.json otherwise)"
        ),
    )
    serve.add_argument(
        "--directory",
        type=pathlib.Path,
        help=(
            "Website directory (defaults to _generated/explorer under --project-root, "
            "or _generated/explorer otherwise)"
        ),
    )
    serve.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Root for importing function entrypoints and resolving default paths",
    )
    serve.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    serve.add_argument(
        "--port", type=_port, default=8001, help="TCP port (default: 8001; 0 selects a free port)"
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Build or serve the analytics explorer using parsed command-line arguments."""
    project_root = args.project_root or pathlib.Path.cwd()
    project_path = args.project_root or pathlib.Path()
    default_analytics_path = project_path / GENERATED_ANALYTICS_PATH
    default_output = project_path / GENERATED_EXPLORER_PATH
    if args.action == "serve":
        analytics_definition = args.spec or default_analytics_path
        directory = args.directory or default_output
        try:
            build_explorer(analytics_definition, directory, project_root)
        except (
            OSError,
            ValueError,
            ImportError,
            AttributeError,
            TypeError,
            jinja2.TemplateError,
        ) as error:
            parser.exit(1, f"uptimely: error: {error}\n")
        try:
            serve_explorer(directory, args.host, args.port)
        except (OSError, ValueError) as error:
            parser.exit(1, f"uptimely: error: {error}\n")
        return
    if args.spec is None and args.project_root is None:
        parser.error("explorer build requires --spec unless --project-root is set")
    analytics_definition = args.spec or default_analytics_path
    output = args.output or default_output
    try:
        index = build_explorer(
            analytics_definition, output, project_root, args.include_generated_at
        )
    except (
        OSError,
        ValueError,
        ImportError,
        AttributeError,
        TypeError,
        jinja2.TemplateError,
    ) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
    print(f"Analytics explorer built at {index}")
