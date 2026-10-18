"""Command-line tools for compiling portable execution plans."""

import argparse
import pathlib

from uptimely import compiler, project
from uptimely.cli import common
from uptimely.compiler import plan as plan_module


def compile_plan(
    spec_definition: pathlib.Path,
    project_root: pathlib.Path,
    features: list[str] | None = None,
) -> plan_module.ExecutionPlan:
    """Compile spec, optionally selecting features and their dependencies."""
    spec_definition = common.load_spec(spec_definition, project_root)
    return compiler.Compiler(spec_definition, features=features).compile()


def print_stages(plan: plan_module.ExecutionPlan) -> None:
    """Print execution stages and their function dependencies."""
    callables_by_id = {callable.id: callable for callable in plan.callables}
    print("\nExecution stages")
    for stage_number, stage in enumerate(plan.execution_stages, 1):
        print(f"Stage {stage_number}")
        for callable in stage:
            dependencies = [
                callables_by_id[dependency_id].function_id
                for dependency_id in callable.dependency_ids
            ]
            suffix = f" <- [{', '.join(dependencies)}]" if dependencies else ""
            print(f"  {callable.function_id}({callable.entity_id}) -> {callable.output}{suffix}")


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the plan build action."""
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser("build", help="Compile spec into an execution-plan JSON")
    common.configure_project_arguments(build)
    build.add_argument(
        "--output",
        type=pathlib.Path,
        help=f"Plan JSON (default: {project.EXECUTION_PLAN_FILE} under --project-root)",
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Compile and export a plan using parsed command-line arguments."""
    spec_definition = common.project_path(args.spec, args.project_root, project.SPEC_JSON_FILE)
    output = common.project_path(args.output, args.project_root, project.EXECUTION_PLAN_FILE)
    try:
        plan = compile_plan(spec_definition, args.project_root or pathlib.Path.cwd(), args.features)
        json_path = plan.export_json(output)
    except (OSError, ValueError, ImportError, AttributeError, TypeError) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
    print(f"Compiled {len(plan.callables)} callables from {spec_definition}")
    print(f"Execution plan: {json_path}")
    if args.verbose:
        print_stages(plan)
