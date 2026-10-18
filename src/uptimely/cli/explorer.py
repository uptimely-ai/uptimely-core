"""Command-line tools for building and serving the analytics explorer."""

import argparse
import functools
import pathlib
from http import server as http_server

import jinja2

from uptimely import project
from uptimely.cli import common
from uptimely.compiler import plan as plan_module
from uptimely.explorer import explorer as explorer_module


def build_explorer(
    analytics_definition: pathlib.Path,
    output: pathlib.Path,
    project_root: pathlib.Path,
    include_generated_at: bool = False,
    *,
    plan_path: pathlib.Path | None = None,
) -> pathlib.Path:
    """Build the static analytics explorer website.

    Args:
        analytics_definition: Path to the JSON analytics document.
        output: Directory for the website index and report pages.
        project_root: Directory added to the import path for function entrypoints.
        include_generated_at: Include a timestamp on the analytics page.
        plan_path: Saved plan JSON; defaults to the standard path under project_root.

    Returns:
        The path to the website index.
    """
    analytics_definition = common.load_analytics(analytics_definition, project_root)
    execution_plan = plan_module.ExecutionPlan.from_json(
        plan_path if plan_path is not None else project_root / project.EXECUTION_PLAN_FILE
    )
    return explorer_module.Explorer(analytics_definition, plan=execution_plan).create_html(
        output / project.EXPLORER_INDEX_FILE.name, include_generated_at=include_generated_at
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
    index = directory / project.EXPLORER_INDEX_FILE.name
    if not index.is_file():
        raise FileNotFoundError(
            f"Website index not found: {index}. Run 'uptimely explorer build' first."
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
        "--analytics",
        type=pathlib.Path,
        help=(
            "Analytics JSON path (required unless --project-root is set; "
            f"then defaults to {project.ANALYTICS_JSON_FILE} under that root)"
        ),
    )
    build.add_argument(
        "--output",
        type=pathlib.Path,
        help=(
            f"Website directory (defaults to {project.EXPLORER_OUTPUT_DIR} under --project-root, "
            f"or {project.EXPLORER_OUTPUT_DIR} otherwise)"
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
        "--analytics",
        type=pathlib.Path,
        help=(
            f"Analytics JSON path (defaults to {project.ANALYTICS_JSON_FILE} under "
            f"--project-root, or {project.ANALYTICS_JSON_FILE} otherwise)"
        ),
    )
    serve.add_argument(
        "--directory",
        type=pathlib.Path,
        help=(
            f"Website directory (defaults to {project.EXPLORER_OUTPUT_DIR} under --project-root, "
            f"or {project.EXPLORER_OUTPUT_DIR} otherwise)"
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
    for action in (build, serve):
        action.add_argument(
            "--plan",
            type=pathlib.Path,
            help=f"Saved plan JSON (default: {project.EXECUTION_PLAN_FILE} under --project-root)",
        )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Build or serve the analytics explorer using parsed command-line arguments."""
    project_root = args.project_root or pathlib.Path.cwd()
    project_path = args.project_root or pathlib.Path()
    default_analytics_path = project_path / project.ANALYTICS_JSON_FILE
    default_output = project_path / project.EXPLORER_OUTPUT_DIR
    plan_path = args.plan or project_path / project.EXECUTION_PLAN_FILE
    if args.action == "serve":
        analytics_definition = args.analytics or default_analytics_path
        directory = args.directory or default_output
        try:
            build_explorer(analytics_definition, directory, project_root, plan_path=plan_path)
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
    if args.analytics is None and args.project_root is None:
        parser.error("explorer build requires --analytics unless --project-root is set")
    analytics_definition = args.analytics or default_analytics_path
    output = args.output or default_output
    try:
        index = build_explorer(
            analytics_definition,
            output,
            project_root,
            args.include_generated_at,
            plan_path=plan_path,
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
