"""Command-line tools for executing analytics workflows."""

import argparse
import logging
import pathlib
import time

from uptimely import engine as engine_module
from uptimely import project
from uptimely.project import imports

logger = logging.getLogger(__name__)


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the engine run action."""
    actions = parser.add_subparsers(dest="action", required=True)
    execute = actions.add_parser("run", help="Execute the active project's saved build")
    execute.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Project root containing the active build and function entrypoints",
    )
    execute.add_argument(
        "--verbose",
        action="store_true",
        help="Log resource statistics, stages, and dataset details",
    )
    execute.add_argument(
        "--config",
        type=pathlib.Path,
        help=(
            "Backend settings and runtime bindings "
            f"(default: {project.ENGINE_CONFIG_FILE} under --project-root)"
        ),
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Execute the active saved plan and report failures explicitly."""
    root = args.project_root or pathlib.Path.cwd()
    config = project.resolve_path(args.config, args.project_root, project.ENGINE_CONFIG_FILE)
    try:
        imports.prepare_imports(root)
        with project.read_build_bundle(root) as bundle:
            settings = engine_module.EngineConfig.model_validate_json(
                config.read_text(encoding="utf-8")
            )
            execution_plan = bundle.execution_plan
            engine = engine_module.Engine(bundle, settings)
            started = time.perf_counter()
            result = engine.execute()
            duration = time.perf_counter() - started
            if result.failures:
                failures = "; ".join(result.failures.values())
                raise RuntimeError(f"Engine flow failed: {failures}")
    except (OSError, ValueError, ImportError, AttributeError, TypeError, RuntimeError) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
    logger.info(
        "\nEngine completed in %.3f s: %d datasets processed", duration, len(result.datasets)
    )
    if args.verbose:
        scope = (
            "all features"
            if bundle.manifest.features is None
            else f"selected features: {', '.join(bundle.manifest.features)}"
        )
        logger.info("\nScope: %s", scope)

        resources = execution_plan.plan.resources
        datasets = resources.get("datasets", {})
        logger.info("\nProcessed datasets:")
        for entity_id, dataset_id in dict.fromkeys(
            (callable.entity_id, callable.dataset_id) for callable in execution_plan.callables
        ):
            dataset = datasets.get(dataset_id)
            if dataset is None:
                logger.info("Dataset(%s, %s): feature metadata unavailable", entity_id, dataset_id)
                continue
            logger.info(
                "- Dataset(%s, %s): %d features", entity_id, dataset_id, len(dataset["features"])
            )
