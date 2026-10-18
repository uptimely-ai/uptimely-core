"""Display execution plan stages in the CLI."""

from uptimely.compiler import plan as plan_module


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
