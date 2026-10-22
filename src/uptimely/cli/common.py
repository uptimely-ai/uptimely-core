"""Shared argument configuration for project-aware CLI commands."""

import argparse
import pathlib


def configure_project_arguments(parser: argparse.ArgumentParser) -> None:
    """Add spec, project-root, feature-selection, and diagnostic options."""
    parser.add_argument(
        "--spec",
        type=pathlib.Path,
        help="Spec JSON to inspect (default: spec from the active project build)",
    )
    parser.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Root for resolving project paths",
    )
    parser.add_argument(
        "--features", nargs="+", help="Select output features and their dependencies"
    )
    parser.add_argument("--verbose", action="store_true", help="Print diagnostic details")
