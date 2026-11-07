"""Command-line tools for executing analytics workflows."""

import argparse
import logging
import pathlib
import time

import polars as pl

from uptimely import engine as engine_module
from uptimely import project
from uptimely.cli import common

logger = logging.getLogger(__name__)
DEFAULT_PREVIEW_ROWS = 5


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure engine commands."""
    actions = parser.add_subparsers(dest="action", required=True)
    execute = actions.add_parser("run", help="Execute the active project's saved build")
    configure_run_parser(execute)


def configure_run_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the engine run command."""
    common.configure_project_root_arguments(
        parser,
        option_help="Project root containing the active build and function entrypoints",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate inputs and dataframe contracts at each execution step",
    )
    common.configure_log_level_argument(parser)
    parser.add_argument(
        "--preview",
        nargs="?",
        type=int,
        const=DEFAULT_PREVIEW_ROWS,
        metavar="ROWS",
        help=(
            "Log the first ROWS rows of each resulting profile "
            f"(default when supplied: {DEFAULT_PREVIEW_ROWS})"
        ),
    )
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        help=(
            "Engine settings and global parameters "
            f"(default: {project.CONFIG_FILE} under the project root or current directory)"
        ),
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Execute the active saved plan and report failures explicitly."""
    if args.preview is not None and args.preview <= 0:
        parser.error("--preview must be a positive integer")
    root = common.resolve_project_root(args, parser)
    config = project.resolve_path(args.config, root, project.CONFIG_FILE)
    with common.apply_log_level(args.log_level):
        try:
            with project.read_build_bundle(root) as bundle:
                settings = engine_module.Config.model_validate_json(
                    config.read_text(encoding="utf-8")
                )
                engine = engine_module.Engine(bundle, settings)
                started = time.perf_counter()
                if args.preview is None:
                    result = engine.run(validate=args.validate)
                else:
                    result = engine.run(validate=args.validate, preview_rows=args.preview)
                elapsed = time.perf_counter() - started
                duration = (
                    result.duration_seconds if result.duration_seconds is not None else elapsed
                )
                if result.failures:
                    failures = "; ".join(result.failures.values())
                    raise RuntimeError(f"Engine flow failed: {failures}")
                _log_summary(bundle, result, duration)
                if args.preview is not None:
                    _log_previews(result, args.preview)
        except (
            OSError,
            ValueError,
            ImportError,
            AttributeError,
            TypeError,
            RuntimeError,
            pl.exceptions.PolarsError,
        ) as error:
            parser.exit(1, f"uptimely: error: {error}\n")


def _log_summary(
    bundle: project.BuildBundle,
    result: engine_module.ExecutionResult,
    duration: float,
) -> None:
    """Log execution timing and counts, with saved-build details at debug level.

    Args:
        bundle: Saved build used for execution.
        result: Execution result containing the final profile frames.
        duration: Execution duration in seconds.
    """
    logger.info(
        "\nEngine completed in %.3f s: %d profiles processed",
        duration,
        len(result.datasets),
    )
    if logger.isEnabledFor(logging.DEBUG):
        scope = (
            "all features"
            if bundle.manifest.features is None
            else f"selected features: {', '.join(bundle.manifest.features)}"
        )
        logger.debug("\nScope: %s", scope)

        logger.debug("\nProcessed profiles:")
        for profile_id, profile in bundle.spec_definition.profiles.items():
            logger.debug(
                "- Profile: %s - %d features",
                profile_id,
                len(profile.features),
            )


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
