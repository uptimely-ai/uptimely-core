"""Command-line tools for executing analytics workflows."""

import argparse
import pathlib
import typing

import pydantic

from uptimely import engine as engine_module
from uptimely import plan as plan_module
from uptimely.cli import common, plan


class EngineSettings(pydantic.BaseModel):
    """Validated engine.json backend configuration and runtime bindings."""

    model_config = pydantic.ConfigDict(extra="forbid")

    backend: engine_module.EngineConfig = pydantic.Field(default_factory=engine_module.EngineConfig)
    bind: dict[str, dict[str, dict[str, typing.Any]]] = pydantic.Field(default_factory=dict)


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the engine run action."""
    actions = parser.add_subparsers(dest="action", required=True)
    execute = actions.add_parser("run", help="Compile and execute an analytics workflow")
    common.configure_project_arguments(execute)
    execute.add_argument(
        "--compile",
        choices=["true", "false"],
        default="true",
        help="Compile the specification first (default: true); false loads --plan",
    )
    execute.add_argument(
        "--plan",
        type=pathlib.Path,
        help=(
            "Saved plan JSON (default: _generated/compile/execution_plan.json under --project-root)"
        ),
    )
    execute.add_argument(
        "--config",
        type=pathlib.Path,
        help=(
            "Backend settings and runtime bindings "
            "(default: config/engine.json under --project-root)"
        ),
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Execute a compiled or saved plan and report failures explicitly."""
    if args.compile == "false" and (args.spec is not None or args.features is not None):
        parser.error("--spec and --features require --compile true")
    if args.compile == "true" and args.plan is not None:
        parser.error("--plan requires --compile false")
    root = args.project_root or pathlib.Path.cwd()
    config = common.project_path(args.config, args.project_root, common.ENGINE_CONFIG_PATH)
    spec = common.project_path(args.spec, args.project_root, common.GENERATED_SPEC_PATH)
    plan_path = common.project_path(args.plan, args.project_root, common.GENERATED_PLAN_PATH)
    try:
        common.prepare_project_root(root)
        settings = EngineSettings.model_validate_json(config.read_text(encoding="utf-8"))
        execution_plan = (
            plan.compile_plan(spec, root, args.features)
            if args.compile == "true"
            else plan_module.ExecutionPlan.from_json(plan_path)
        )
        result = engine_module.Engine(
            execution_plan, config=settings.backend, bind=settings.bind
        ).execute()
        if result.failures:
            failures = "; ".join(result.failures.values())
            raise RuntimeError(f"Engine flow failed: {failures}")
    except (OSError, ValueError, ImportError, AttributeError, TypeError, RuntimeError) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
    calculated_features = sorted({feature_id for _, _, feature_id in result.calculated_outputs})
    print("Engine completed the flow")
    print(f"{len(execution_plan.operations)} operations")
    print("Calculated features: " + ", ".join(calculated_features))
    print(f"Specification: {spec}" if args.compile == "true" else f"Execution plan: {plan_path}")
    if args.verbose:
        plan.print_stages(execution_plan)
        print("\nDataset registry")
        datasets = execution_plan.plan.resources.get("datasets", {})
        for entity_id, dataset_id in dict.fromkeys(
            (operation.entity_id, operation.dataset_id) for operation in execution_plan.operations
        ):
            dataset = datasets.get(dataset_id)
            if dataset is None:
                print(f"Dataset({entity_id}, {dataset_id}): feature metadata unavailable")
                continue
            print(f"Dataset({entity_id}, {dataset_id}): {len(dataset['features'])} features")
