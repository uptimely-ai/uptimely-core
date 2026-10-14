"""Shared project paths and specification loading for CLI commands."""

import argparse
import pathlib
import sys

from uptimely import spec

GENERATED_SPEC_PATH = pathlib.Path("_generated/spec/spec.json")
GENERATED_PLAN_PATH = pathlib.Path("_generated/compile/execution_plan.json")
ENGINE_CONFIG_PATH = pathlib.Path("engine.json")


def configure_project_arguments(parser: argparse.ArgumentParser) -> None:
    """Add specification, import-root, feature-selection, and diagnostic options."""
    parser.add_argument(
        "--spec",
        type=pathlib.Path,
        help="JSON specification (default: _generated/spec/spec.json under --project-root)",
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


def prepare_project_root(project_root: pathlib.Path) -> None:
    """Make project function entrypoints importable without changing directories."""
    root = str(project_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)


def load_specification(path: pathlib.Path, project_root: pathlib.Path) -> spec.Specification:
    """Load a JSON specification with its project functions on the import path."""
    prepare_project_root(project_root)
    return spec.Specification.from_json(path)
