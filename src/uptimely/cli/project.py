"""Command-line orchestration for building generated project resources."""

import argparse
import logging
import pathlib
import time

from uptimely import spec
from uptimely.cli import common
from uptimely.project import build as project_build
from uptimely.project.build import source as build_source

logger = logging.getLogger(__name__)


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure project commands."""
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser(
        "build",
        help="Build and publish a complete project bundle without running workflows",
    )
    configure_build_parser(build)


def configure_build_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the project build command."""
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--python-spec",
        metavar="MODULE:ATTRIBUTE",
        help="Importable module and attribute containing a Spec instance",
    )
    source.add_argument(
        "--json-spec",
        type=pathlib.Path,
        help="Source spec JSON path (overrides standard source discovery)",
    )
    common.configure_project_root_arguments(
        parser,
        option_help="Root added to the import path and used to resolve the output bundle",
    )
    parser.add_argument(
        "--features",
        nargs="+",
        metavar="FEATURE",
        help="Select output features and their dependencies",
    )
    common.configure_log_level_argument(parser)


def _log_build_details(
    bundle: project_build.BuildBundle,
    root: pathlib.Path,
    args: argparse.Namespace,
    duration: float,
) -> None:
    """Log build details and full-spec counts alongside the compiled plan."""
    definition = spec.load_spec(bundle.spec_path)
    source = build_source.SpecSource(root.resolve()).resolve(
        python_spec=args.python_spec, json_spec=args.json_spec
    )
    if isinstance(source, build_source.PythonSource):
        source_file = source.entrypoint.module.source_file
    else:
        source_file = str(source.path.resolve())
    scope = (
        "all features" if bundle.manifest.features is None else ", ".join(bundle.manifest.features)
    )
    logger.debug("\n")
    logger.debug("Build")
    logger.debug("  Duration: %.3f s", duration)
    logger.debug("  Output folder: %s", bundle.root)
    logger.debug("  Build scope: %s", scope)
    logger.debug("\nSpec")
    logger.debug("  Spec source file: %s", source_file)
    logger.debug("  Number of functions: %d", len(definition.functions))
    logger.debug(
        "  Number of datasets: %d",
        len(definition.datasets),
    )
    logger.debug(
        "  Number of features: %d",
        sum(len(dataset.features) for dataset in definition.datasets.values()),
    )
    logger.debug("\nPlan")
    logger.debug("  Number of stages: %d", len(bundle.execution_plan.stages))
    logger.debug("  Number of invocations: %d", len(bundle.execution_plan.invocations))


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Build and publish a complete project bundle."""
    root = common.resolve_project_root(args, parser)
    started = time.perf_counter()
    with common.apply_log_level(args.log_level):
        try:
            bundle = project_build.build_project(
                root,
                python_spec=args.python_spec,
                json_spec=args.json_spec,
                features=args.features,
            )
            duration = time.perf_counter() - started
            if logger.isEnabledFor(logging.DEBUG):
                _log_build_details(bundle, root, args, duration)
            logger.info("Build files created to %s", bundle.root)
        except (
            project_build.BuildLockError,
            project_build.ProjectBuildError,
            OSError,
            ValueError,
        ) as error:
            parser.exit(1, f"uptimely: error: {error}\n")
