"""Command-line tools for building and serving the analytics explorer."""

import argparse
import functools
import pathlib
import shlex
from http import server as http_server

import jinja2

from uptimely import project
from uptimely.cli import common
from uptimely.compiler import plan as plan_module
from uptimely.explorer import explorer as explorer_module


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
            f"Website index not found: {index}. Generate it with 'uptimely project build'."
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
            print("\nSpec explorer server stopped.")


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
    serve = actions.add_parser(
        "serve", help="Build and serve the generated website for local preview"
    )
    serve.add_argument(
        "--spec",
        type=pathlib.Path,
        help=(
            f"Spec JSON path (defaults to {project.SPEC_JSON_FILE} under "
            f"--project-root, or {project.SPEC_JSON_FILE} otherwise)"
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
    serve.add_argument(
        "--plan",
        type=pathlib.Path,
        help=f"Saved plan JSON (default: {project.EXECUTION_PLAN_FILE} under --project-root)",
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Build the analytics explorer for local preview and serve it."""
    project_root = args.project_root or pathlib.Path.cwd()
    project_path = args.project_root or pathlib.Path()
    default_spec_path = project_path / project.SPEC_JSON_FILE
    default_output = project_path / project.EXPLORER_OUTPUT_DIR
    plan_path = args.plan or project_path / project.EXECUTION_PLAN_FILE
    spec_definition = args.spec or default_spec_path
    directory = args.directory or default_output
    inputs = (("Spec JSON", spec_definition), ("Execution plan JSON", plan_path))
    missing = [f"  {label}: {path.resolve()}" for label, path in inputs if not path.exists()]
    if missing:
        command = shlex.join(
            ["uptimely", "project", "build", "--project-root", str(project_root.resolve())]
        )
        parser.exit(
            1,
            "uptimely: error: Missing Explorer input files:\n"
            + "\n".join(missing)
            + f"\nRun {command} to generate the complete active bundle."
            "\nThis Explorer command still requires matching standalone inputs until its "
            "bundle consumer migration is complete."
            "\nIf using custom inputs, check the --spec and --plan paths.\n",
        )
    try:
        spec_model = common.load_spec(spec_definition, project_root)
        execution_plan = plan_module.ExecutionPlan.from_json(plan_path)
        explorer_module.Explorer(spec_model, plan=execution_plan).create_html(
            directory / project.EXPLORER_INDEX_FILE.name
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
    try:
        serve_explorer(directory, args.host, args.port)
    except (OSError, ValueError) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
