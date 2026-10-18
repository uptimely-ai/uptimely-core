"""Command-line orchestration for building generated project resources."""

import argparse
import pathlib

from uptimely.cli import spec
from uptimely.project import build as project_build


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the project build action."""
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser(
        "build",
        help="Build and publish a complete project bundle without running workflows",
    )
    spec.configure_build_source_arguments(build)
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
            entrypoint=args.entrypoint,
            source=args.spec,
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
    print(f"Build scope: {scope}")
    print(f"Build bundle: {bundle.root}")
    print(f"Compiled {len(bundle.execution_plan.callables)} callables")
