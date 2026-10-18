"""Internal helpers for compiling and displaying execution plans."""

import pathlib

from uptimely import compiler
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
