"""Shared argument configuration for project-aware CLI commands."""

import argparse
import pathlib


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
    """Add spec, project-root, feature-selection, and diagnostic options."""
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
    parser.add_argument("--verbose", action="store_true", help="Print diagnostic details")
