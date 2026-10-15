"""Command-line tools for compiling portable execution plans."""

import argparse
import pathlib

from uptimely import compile
from uptimely import plan as plan_module
from uptimely.cli import common


def compile_plan(
    analytics_definition: pathlib.Path,
    project_root: pathlib.Path,
    features: list[str] | None = None,
) -> plan_module.ExecutionPlan:
    """Compile analytics, optionally selecting features and their dependencies."""
    analytics_definition = common.load_analytics(analytics_definition, project_root)
    return compile.Compiler(analytics_definition, features=features).compile()


def print_stages(plan: plan_module.ExecutionPlan) -> None:
    """Print execution stages and their function dependencies."""
    operations_by_id = {operation.id: operation for operation in plan.operations}
    print("\nExecution stages")
    for stage_number, stage in enumerate(plan.execution_stages, 1):
        print(f"Stage {stage_number}")
        for operation in stage:
            dependencies = [
                operations_by_id[dependency_id].function_id
                for dependency_id in operation.dependency_ids
            ]
            suffix = f" <- [{', '.join(dependencies)}]" if dependencies else ""
            print(f"  {operation.function_id}({operation.entity_id}) -> {operation.output}{suffix}")


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the plan build action."""
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser("build", help="Compile analytics into an execution-plan JSON")
    common.configure_project_arguments(build)
    build.add_argument(
        "--output",
        type=pathlib.Path,
        help="Plan JSON (default: _generated/compile/execution_plan.json under --project-root)",
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Compile and export a plan using parsed command-line arguments."""
    analytics_definition = common.project_path(
        args.spec, args.project_root, common.GENERATED_ANALYTICS_PATH
    )
    output = common.project_path(args.output, args.project_root, common.GENERATED_PLAN_PATH)
    try:
        plan = compile_plan(
            analytics_definition, args.project_root or pathlib.Path.cwd(), args.features
        )
        json_path = plan.export_json(output)
    except (OSError, ValueError, ImportError, AttributeError, TypeError) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
    print(f"Compiled {len(plan.operations)} operations from {analytics_definition}")
    print(f"Execution plan: {json_path}")
    if args.verbose:
        print_stages(plan)
