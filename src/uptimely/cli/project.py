"""Command-line orchestration for building generated project resources."""

import argparse
import logging
import pathlib

from uptimely.project import build as project_build

logger = logging.getLogger(__name__)


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the project build action."""
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser(
        "build",
        help="Build and publish a complete project bundle without running workflows",
    )
    source = build.add_mutually_exclusive_group()
    source.add_argument(
        "--python-spec",
        metavar="MODULE:ATTRIBUTE",
        help="Importable module and attribute containing a PythonSpec instance",
    )
    source.add_argument(
        "--json-spec",
        type=pathlib.Path,
        help="Source spec JSON path (overrides standard source discovery)",
    )
    build.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Root added to the import path and used to resolve the output bundle",
    )
    build.add_argument(
        "--features",
        nargs="+",
        metavar="FEATURE",
        help="Select output features and their dependencies",
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Build and publish a complete project bundle."""
    root = args.project_root or pathlib.Path.cwd()
    try:
        bundle = project_build.build_project(
            root,
            python_spec=args.python_spec,
            json_spec=args.json_spec,
            features=args.features,
        )
    except (
        project_build.BuildLockError,
        project_build.ProjectBuildError,
        OSError,
        ValueError,
    ) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
    scope = (
        "all features" if bundle.manifest.features is None else ", ".join(bundle.manifest.features)
    )
    logger.info("Build scope: %s", scope)
    logger.info("Build bundle: %s", bundle.root)
    logger.info("Compiled %d callables", len(bundle.execution_plan.callables))
