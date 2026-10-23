"""Command-line tools for executing analytics workflows."""

import argparse
import logging
import pathlib
import time

import polars as pl

from uptimely import engine as engine_module
from uptimely import project
from uptimely.cli import common
from uptimely.project import imports

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
        "--verbose",
        action="store_true",
        help="Log resource statistics, stages, and dataset details",
    )
    parser.add_argument(
        "--preview",
        nargs="?",
        type=int,
        const=DEFAULT_PREVIEW_ROWS,
        metavar="ROWS",
        help=(
            "Log the first ROWS rows of each resulting dataset "
            f"(default when supplied: {DEFAULT_PREVIEW_ROWS})"
        ),
    )
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        help=(
            "Backend settings and runtime bindings "
            f"(default: {project.ENGINE_CONFIG_FILE} under the project root or current directory)"
        ),
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Execute the active saved plan and report failures explicitly."""
    if args.preview is not None and args.preview <= 0:
        parser.error("--preview must be a positive integer")
    root = common.resolve_project_root(args, parser)
    config = project.resolve_path(args.config, root, project.ENGINE_CONFIG_FILE)
    try:
        imports.prepare_imports(root)
        with project.read_build_bundle(root) as bundle:
            settings = engine_module.EngineConfig.model_validate_json(
                config.read_text(encoding="utf-8")
            )
            engine = engine_module.Engine(bundle, settings)
            started = time.perf_counter()
            result = engine.run()
            duration = time.perf_counter() - started
            if result.failures:
                failures = "; ".join(result.failures.values())
                raise RuntimeError(f"Engine flow failed: {failures}")
            _log_summary(bundle, result, duration, args.verbose)
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
    verbose: bool,
) -> None:
    """Log execution timing, dataset counts, and optional saved-build details.

    Args:
        bundle: Saved build used for execution.
        result: Execution result containing the final datasets.
        duration: Execution duration in seconds.
        verbose: Whether to include scope and dataset feature counts.
    """
    logger.info(
        "\nEngine completed in %.3f s: %d datasets processed",
        duration,
        len(result.datasets),
    )
    if verbose:
        scope = (
            "all features"
            if bundle.manifest.features is None
            else f"selected features: {', '.join(bundle.manifest.features)}"
        )
        logger.info("\nScope: %s", scope)

        logger.info("\nProcessed datasets:")
        for entity in bundle.spec_definition.entities.values():
            for dataset_id, dataset in entity.datasets.items():
                logger.info(
                    "- Dataset: %s - %d features",
                    dataset_id,
                    len(dataset.features),
                )


def _log_previews(result: engine_module.ExecutionResult, rows: int) -> None:
    """Log bounded dataset previews without changing Polars display settings.

    Args:
        result: Execution result containing the final datasets.
        rows: Positive maximum number of rows to display per dataset.
    """
    for dataset_id, frame in result.datasets.items():
        if not isinstance(frame, (pl.DataFrame, pl.LazyFrame)):
            raise TypeError(
                f"Cannot preview Dataset({dataset_id}): "
                f"unsupported frame type {type(frame).__name__}"
            )
        preview = frame.head(rows)
        if isinstance(preview, pl.LazyFrame):
            preview = preview.collect()
        with pl.Config(tbl_rows=rows, tbl_cols=-1, tbl_hide_dataframe_shape=True):
            logger.info("\nDataset: %s\n%s", dataset_id, preview)
