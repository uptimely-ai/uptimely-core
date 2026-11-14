"""Command-line orchestration for building generated project resources."""

import argparse
import logging
import pathlib
import time

import polars as pl

from uptimely import project
from uptimely.cli import common
from uptimely.project import BuildBundle, BuildLockError, ProjectBuildError
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
    common.configure_src_path_argument(parser)
    parser.add_argument(
        "--features",
        nargs="+",
        metavar="FEATURE",
        help="Select output features and their dependencies",
    )
    common.configure_log_level_argument(parser)


def _log_build_details(
    bundle: BuildBundle,
    root: pathlib.Path,
    args: argparse.Namespace,
    duration: float,
) -> None:
    """Log build details and full-spec counts alongside the compiled plan."""
    definition = bundle.spec_definition
    source = build_source.SpecSource(root.resolve()).resolve(
        python_spec=args.python_spec, json_spec=args.json_spec
    )
    if isinstance(source, build_source.PythonSource):
        spec_source = str(source.path.resolve()) if args.python_spec is None else args.python_spec
    else:
        spec_source = str(source.path.resolve())
    scope = (
        "all features" if bundle.manifest.features is None else ", ".join(bundle.manifest.features)
    )
    rows = [
        ("Build", "Duration", f"{duration:.3f} s"),
        ("Build", "Output folder", str(bundle.root)),
        ("Build", "Build scope", scope),
        ("Spec", "Spec source", spec_source),
        ("Spec", "Number of functions", str(len(definition.functions))),
        ("Spec", "Number of profiles", str(len(definition.profiles))),
        (
            "Spec",
            "Number of features",
            str(sum(len(profile.features) for profile in definition.profiles.values())),
        ),
        ("Plan", "Number of stages", str(len(bundle.execution_plan.stages))),
        ("Plan", "Number of invocations", str(len(bundle.execution_plan.invocations))),
    ]
    table = pl.DataFrame(rows, schema=["Section", "Detail", "Value"], orient="row")
    with pl.Config(
        tbl_formatting="ASCII_FULL_CONDENSED",
        tbl_hide_dataframe_shape=True,
        tbl_hide_column_data_types=True,
        tbl_rows=-1,
        tbl_cols=-1,
        tbl_width_chars=-1,
        fmt_str_lengths=max(len(value) for row in rows for value in row),
    ):
        logger.debug("\nBuild summary\n%s", table)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Build and publish a complete project bundle."""
    root = common.resolve_project_root(args, parser)
    started = time.perf_counter()
    with common.apply_log_level(args.log_level):
        try:
            bundle = project.build(
                root,
                python_spec=args.python_spec,
                json_spec=args.json_spec,
                features=args.features,
                src_path=args.src_path,
            )
            duration = time.perf_counter() - started
            if logger.isEnabledFor(logging.DEBUG):
                _log_build_details(bundle, root, args, duration)
            logger.info("Build files created to %s", bundle.root)
        except (
            BuildLockError,
            ProjectBuildError,
            OSError,
            ValueError,
        ) as error:
            common.exit_with_error(parser, error)
