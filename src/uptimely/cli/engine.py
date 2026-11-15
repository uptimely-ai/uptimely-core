"""Command-line tools for executing analytics workflows."""

import argparse
import logging
import shlex
import time

import polars as pl

from uptimely import application
from uptimely import engine as engine_module
from uptimely.cli import common

logger = logging.getLogger(__name__)


class _PreviewAction(argparse.Action):
    """Track whether preview output was requested separately from its row count."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: int | None,
        option_string: str | None = None,
    ) -> None:
        """Store an optional row count and mark console previews as requested."""
        setattr(namespace, self.dest, values)
        namespace.preview_requested = True


def configure_run_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the engine run command."""
    common.configure_project_root_arguments(
        parser,
        option_help="Project root containing the active build and function entrypoints",
    )
    common.configure_src_path_argument(parser)
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build and publish the project before executing it",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate inputs and dataframe contracts at each execution step",
    )
    common.configure_log_level_argument(parser)
    parser.add_argument(
        "--preview",
        action=_PreviewAction,
        nargs="?",
        type=int,
        default=None,
        metavar="ROWS",
        help=(
            "Log the first ROWS rows of each resulting profile "
            "using engine.preview_rows when ROWS is omitted"
        ),
    )
    parser.set_defaults(preview_requested=False)
    common.configure_project_config_argument(parser)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Execute the active saved plan and report failures explicitly."""
    if args.preview is not None and args.preview <= 0:
        parser.error("--preview must be a positive integer")
    root = common.resolve_project_root(args, parser)
    with common.apply_log_level(args.log_level):
        logger.info("Start Uptimely engine run")
        try:
            app = common.create_project(root, args.config)
            if args.build:
                logger.info("Start building the project bundle")
                bundle = app.build(src_path=args.src_path)
                logger.info("Build files created to %s", bundle.root)
            src_path = args.src_path
            with app.read_build_bundle() as bundle:
                engine = app.create_engine(bundle)
                started = time.perf_counter()
                if args.preview_requested:
                    preview_rows = (
                        app.config.engine.preview_rows if args.preview is None else args.preview
                    )
                    result = engine.run(
                        validate=args.validate,
                        preview_rows=preview_rows,
                        src_path=src_path,
                    )
                else:
                    result = engine.run(validate=args.validate, src_path=src_path)
                elapsed = time.perf_counter() - started
                duration = (
                    result.duration_seconds if result.duration_seconds is not None else elapsed
                )
                if result.failures:
                    failures = "; ".join(result.failures.values())
                    raise RuntimeError(f"Engine flow failed: {failures}")
                _log_summary(bundle, result, duration)
                if args.preview_requested:
                    _log_previews(result, preview_rows)
            logger.info(
                "View results in Explorer:",
            )
            logger.info(
                shlex.join(["uptimely", "explore", "--project-root", str(root.resolve())]),
            )
        except (
            OSError,
            ValueError,
            ImportError,
            AttributeError,
            TypeError,
            RuntimeError,
            pl.exceptions.PolarsError,
        ) as error:
            common.exit_with_error(parser, error)


def _log_summary(
    bundle: application.BuildBundle,
    result: engine_module.ExecutionResult,
    duration: float,
) -> None:
    """Log processed profiles followed by execution totals at info level.

    Args:
        bundle: Saved build used for execution.
        result: Execution result containing the final profile frames.
        duration: Execution duration in seconds.
    """
    for profile_id in result.datasets:
        profile = bundle.spec_definition.profiles.get(profile_id)
        if profile is None:
            logger.info("Processed profile %s", profile_id)
        else:
            logger.info("Processed profile %s: %d features", profile_id, len(profile.features))

    logger.info("Engine processed %d profiles in %.3f s.", len(result.datasets), duration)


def _log_previews(result: engine_module.ExecutionResult, rows: int) -> None:
    """Log bounded profile previews without changing Polars display settings.

    Args:
        result: Execution result containing the final profile frames.
        rows: Positive maximum number of rows to display per profile.
    """
    for profile_id, frame in result.datasets.items():
        if profile_id in result.preview_failures:
            raise RuntimeError(
                f"Cannot preview Profile({profile_id}): {result.preview_failures[profile_id]}"
            )
        frame = result.preview_frames.get(profile_id, frame)
        if not isinstance(frame, (pl.DataFrame, pl.LazyFrame)):
            raise TypeError(
                f"Cannot preview Profile({profile_id}): "
                f"unsupported frame type {type(frame).__name__}"
            )
        preview = frame.head(rows)
        if isinstance(preview, pl.LazyFrame):
            preview = preview.collect()
        with pl.Config(tbl_rows=rows, tbl_cols=-1, tbl_hide_dataframe_shape=True):
            logger.info("\nProfile: %s\n%s", profile_id, preview)
