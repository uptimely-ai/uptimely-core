"""Entry point for the Uptimely command-line interface."""

import argparse
import logging
import os
import shutil
import sys
import textwrap
import typing

from uptimely.cli import engine, examples, explorer, project, spec

_LOG_COLORS = {
    logging.DEBUG: "\033[36m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;31m",
}
_RESET_COLOR = "\033[0m"
_LEVEL_COLUMN_WIDTH = 8


def _color_text(text: str, level: int, stream: typing.TextIO) -> str:
    """Color terminal text without changing redirected output."""
    color = _LOG_COLORS.get(level)
    if color is None or os.environ.get("NO_COLOR") or not stream.isatty():
        return text
    return f"{color}{text}{_RESET_COLOR}"


class _ColorFormatter(logging.Formatter):
    """Format CLI logs with a fixed-width level followed by the message."""

    def format(self, record: logging.LogRecord) -> str:
        """Format logs as level and message."""
        message = super().format(record).lstrip("\n")
        if sys.stdout.isatty() and "\n" not in message:
            continuation = " " * _LEVEL_COLUMN_WIDTH + " | "
            width = shutil.get_terminal_size().columns - len(continuation) - 1
            if width > 0:
                message = ("\n" + continuation).join(
                    textwrap.wrap(
                        message,
                        width=width,
                        break_on_hyphens=False,
                        replace_whitespace=False,
                    )
                )
        level_name = record.levelname[:_LEVEL_COLUMN_WIDTH]
        label = (
            level_name
            if record.levelno >= logging.ERROR
            else _color_text(level_name, record.levelno, sys.stdout)
        )
        level_field = label + " " * (_LEVEL_COLUMN_WIDTH - len(level_name))
        if record.levelno >= logging.ERROR:
            return _color_text(f"{level_field} | {message}", record.levelno, sys.stdout)
        return f"{level_field} | {message}"


class _ArgumentParser(argparse.ArgumentParser):
    """Preserve argparse behavior while coloring whole terminal errors."""

    def exit(self, status: int = 0, message: str | None = None) -> typing.NoReturn:
        """Exit with the original status and color the whole error message."""
        if status != 0 and message is not None:
            message = message.replace("uptimely: error: ", f"{'ERROR':{_LEVEL_COLUMN_WIDTH}} | ", 1)
            message = _color_text(message, logging.ERROR, sys.stderr)
        super().exit(status, message)


def main() -> None:
    """Run the Uptimely command-line interface."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ColorFormatter("%(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    parser = _ArgumentParser(prog="uptimely")
    commands = parser.add_subparsers(dest="command", required=True)
    examples.configure_parser(commands.add_parser("examples", help="Manage example projects"))
    explorer.configure_parser(
        commands.add_parser("explorer", help="Explore spec, feature lineage, and execution plans")
    )
    spec.configure_parser(
        commands.add_parser("spec", help="Inspect specs and feature dependencies")
    )
    project.configure_parser(commands.add_parser("project", help="Build project resources"))
    engine.configure_parser(commands.add_parser("engine", help="Run analytics workflows"))
    project.configure_build_parser(
        commands.add_parser("build", help="Build a complete project bundle")
    )
    engine.configure_run_parser(commands.add_parser("run", help="Run an analytics workflow"))
    explorer.configure_serve_parser(
        commands.add_parser("explore", help="Serve the Analytics Explorer frontend")
    )
    args = parser.parse_args()
    if args.command == "examples":
        examples.run(args, parser)
    elif args.command == "explorer":
        explorer.run(args, parser)
    elif args.command == "spec":
        spec.run(args, parser)
    elif args.command == "project":
        project.run(args, parser)
    elif args.command in ("engine", "run"):
        engine.run(args, parser)
    elif args.command == "build":
        project.run(args, parser)
    elif args.command == "explore":
        explorer.run(args, parser)


if __name__ == "__main__":
    main()
