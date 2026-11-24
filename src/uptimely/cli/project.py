"""Command-line orchestration for building generated project resources."""

import argparse
import logging
import pathlib
import time

import polars as pl

from uptimely.application import BuildBundle, BuildError, BuildLockError, ProjectBuildError
from uptimely.cli import common
from uptimely.test import models as test_models
from uptimely.test import runner as test_runner

logger = logging.getLogger(__name__)


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
    common.configure_project_config_argument(parser)
    parser.add_argument(
        "--features",
        nargs="+",
        metavar="FEATURE",
        help="Select output features and their dependencies",
    )
    common.configure_log_level_argument(parser)


def configure_test_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the project test command."""
    common.configure_project_root_arguments(
        parser,
        option_help="Root for resolving the test folder",
    )
    common.configure_project_config_argument(parser)
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build and publish the project before running tests",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show all input and expected output rows for each test case",
    )
    common.configure_log_level_argument(parser)


def run_test(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Run isolated operator cases against the active build."""
    root = common.resolve_project_root(args, parser)
    with common.apply_log_level(args.log_level):
        try:
            app = common.create_project(root, args.config)
            if args.build:
                logger.info("Start building the project bundle")
                bundle = app.build()
                logger.info("Build files created to %s", bundle.root)
            report = test_runner.TestRunner(app).run(on_case=_show_case if args.show else None)
            for case in report.cases:
                if case.status != "passed":
                    logger.error(
                        "%s/%s/%s: %s", case.profile, case.operator, case.case, case.message
                    )
            passed = sum(case.status == "passed" for case in report.cases)
            logger.info("Test cases: %d passed, %d failed", passed, len(report.cases) - passed)
            logger.info("Test report saved to %s", app.root / test_runner.REPORT_PATH)
            if report.status != "passed":
                parser.exit(1)
        except (
            BuildError,
            BuildLockError,
            ProjectBuildError,
            OSError,
            ValueError,
            TypeError,
        ) as error:
            common.exit_with_error(parser, error)


def _show_case(result: test_models.CaseResult, case: test_models.Case) -> None:
    """Print fixture inputs and expected output as dataframes."""
    rows = [*case.inputs.values(), case.expected.return_]
    string_length = max(
        (len(str(value)) for frame in rows for row in frame for value in row.values()),
        default=32,
    )
    print(f"\nCase: {result.profile}/{result.operator}/{result.case} ({result.status})")
    with pl.Config(
        tbl_rows=-1,
        tbl_cols=-1,
        tbl_width_chars=-1,
        fmt_str_lengths=max(32, string_length),
        fmt_table_cell_list_len=-1,
    ):
        print("Inputs:")
        for name, frame_rows in case.inputs.items():
            print(f"{name}:\n{_format_case_frame(frame_rows)}")
        print(f"Expected output:\n{_format_case_frame(case.expected.return_)}")


def _format_case_frame(rows: list[dict[str, object]]) -> str:
    """Format fixture rows, reporting invalid dataframe values explicitly."""
    try:
        return str(pl.DataFrame(rows))
    except (pl.exceptions.PolarsError, TypeError, ValueError, OverflowError) as error:
        return f"Cannot display dataframe: {type(error).__name__}: {error}"


def _log_build_details(
    bundle: BuildBundle,
    duration: float,
) -> None:
    """Log build details and full-spec counts alongside the compiled plan."""
    definition = bundle.spec_definition
    spec_source = bundle.manifest.spec_source or str(bundle.spec_path)
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
            app = common.create_project(root, args.config)
            bundle = app.build(
                python_spec=args.python_spec,
                json_spec=args.json_spec,
                features=args.features,
                src_path=args.src_path,
            )
            duration = time.perf_counter() - started
            if logger.isEnabledFor(logging.DEBUG):
                _log_build_details(bundle, duration)
            logger.info("Build files created to %s", bundle.root)
        except (
            BuildLockError,
            ProjectBuildError,
            OSError,
            ValueError,
        ) as error:
            common.exit_with_error(parser, error)
