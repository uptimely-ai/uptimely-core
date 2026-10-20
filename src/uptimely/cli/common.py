"""Shared project paths and spec loading for CLI commands."""

import argparse
import pathlib

from uptimely import spec
from uptimely.project import imports


def configure_project_arguments(parser: argparse.ArgumentParser) -> None:
    """Add spec, import-root, feature-selection, and diagnostic options."""
    parser.add_argument(
        "--spec",
        type=pathlib.Path,
        help="Spec JSON to inspect (default: spec from the active project build)",
    )
    parser.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Root for importing function entrypoints and resolving default paths",
    )
    parser.add_argument(
        "--features", nargs="+", help="Select output features and their dependencies"
    )
    parser.add_argument("--verbose", action="store_true", help="Print diagnostic details")


def project_path(
    path: pathlib.Path | None, project_root: pathlib.Path | None, default: pathlib.Path
) -> pathlib.Path:
    """Resolve a default beneath the project root, preserving explicit paths."""
    return path if path is not None else (project_root or pathlib.Path()) / default


def load_spec(path: pathlib.Path, project_root: pathlib.Path) -> spec.Spec:
    """Load a spec document with project functions on the import path."""
    imports.prepare_project_root(project_root)
    return spec.load_spec(path)
