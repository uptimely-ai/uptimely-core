"""Shared argument configuration for project-aware CLI commands."""

import argparse
import contextlib
import logging
import pathlib
from collections.abc import Iterator

LOG_LEVELS = ("debug", "info", "warning", "error", "critical")


def configure_project_root_arguments(parser: argparse.ArgumentParser, *, option_help: str) -> None:
    """Add optional positional and explicit project-root arguments."""
    parser.add_argument(
        "project_root_argument",
        nargs="?",
        type=pathlib.Path,
        metavar="PROJECT_ROOT",
        help="Project directory (default: current working directory)",
    )
    parser.add_argument(
        "--project-root",
        type=pathlib.Path,
        help=option_help,
    )


def resolve_project_root(args: argparse.Namespace, parser: argparse.ArgumentParser) -> pathlib.Path:
    """Resolve the project root and reject passing both supported forms."""
    positional = args.project_root_argument
    option = args.project_root
    if positional is not None and option is not None:
        parser.error("project root may be provided positionally or with --project-root, not both")
    return positional or option or pathlib.Path.cwd()


def configure_project_arguments(parser: argparse.ArgumentParser) -> None:
    """Add spec, project-root, feature-selection, and logging options."""
    parser.add_argument(
        "--spec",
        type=pathlib.Path,
        help="Spec JSON to inspect (default: spec from the active project build)",
    )
    configure_project_root_arguments(
        parser,
        option_help="Root for resolving project paths",
    )
    parser.add_argument(
        "--features", nargs="+", help="Select output features and their dependencies"
    )
    configure_log_level_argument(parser)


def configure_log_level_argument(parser: argparse.ArgumentParser) -> None:
    """Add the standard Uptimely log-level option."""
    parser.add_argument(
        "--log-level",
        choices=LOG_LEVELS,
        default="info",
        help="Set Uptimely logging verbosity (default: info)",
    )


@contextlib.contextmanager
def apply_log_level(level: str) -> Iterator[None]:
    """Apply a log level to Uptimely loggers and restore it afterward."""
    uptimely_logger = logging.getLogger("uptimely")
    previous_level = uptimely_logger.level
    uptimely_logger.setLevel(level.upper())
    try:
        yield
    finally:
        uptimely_logger.setLevel(previous_level)
