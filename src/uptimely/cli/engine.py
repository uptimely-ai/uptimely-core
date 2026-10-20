"""Command-line tools for executing analytics workflows."""

import argparse
import pathlib
import typing

import pydantic

from uptimely import engine as engine_module
from uptimely import project
from uptimely.cli import common, plan
from uptimely.project import imports


class EngineSettings(pydantic.BaseModel):
    """Validated engine.json backend configuration and runtime bindings."""

    model_config = pydantic.ConfigDict(extra="forbid")

    backend: engine_module.EngineConfig = pydantic.Field(default_factory=engine_module.EngineConfig)
    bind: dict[str, dict[str, dict[str, typing.Any]]] = pydantic.Field(default_factory=dict)


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
        "--verbose", action="store_true", help="Print execution stages and dataset details"
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
    config = common.project_path(args.config, args.project_root, project.ENGINE_CONFIG_FILE)
    try:
        imports.prepare_project_root(root)
        with project.read_build_bundle(root) as bundle:
            settings = EngineSettings.model_validate_json(config.read_text(encoding="utf-8"))
            execution_plan = bundle.execution_plan
            result = engine_module.Engine(
                execution_plan, config=settings.backend, bind=settings.bind
            ).execute()
            if result.failures:
                failures = "; ".join(result.failures.values())
                raise RuntimeError(f"Engine flow failed: {failures}")
    except (OSError, ValueError, ImportError, AttributeError, TypeError, RuntimeError) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
    calculated_features = sorted({feature_id for _, _, feature_id in result.calculated_outputs})
    scope = (
        "all features"
        if bundle.manifest.features is None
        else f"selected features: {', '.join(bundle.manifest.features)}"
    )
    print("Engine completed the flow")
    print(f"Build scope: {scope}")
    print(f"{len(execution_plan.callables)} callables")
    print("Calculated features: " + ", ".join(calculated_features))
    if args.verbose:
        plan.print_stages(execution_plan)
        print("\nDataset registry")
        datasets = execution_plan.plan.resources.get("datasets", {})
        for entity_id, dataset_id in dict.fromkeys(
            (callable.entity_id, callable.dataset_id) for callable in execution_plan.callables
        ):
            dataset = datasets.get(dataset_id)
            if dataset is None:
                print(f"Dataset({entity_id}, {dataset_id}): feature metadata unavailable")
                continue
            print(f"Dataset({entity_id}, {dataset_id}): {len(dataset['features'])} features")
