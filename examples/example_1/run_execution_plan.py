"""Compile a specification and export its execution plan as JSON and HTML."""

from examples.example_1.common import (
    GENERATED_DIR,
    SPEC_PATH,
    load_specification,
    verbose_requested,
)

from uptimely.compile import Compiler


def main(verbose: bool | None = None) -> None:
    """Compile the specification, export its plan, and optionally print diagnostics."""
    verbose = verbose_requested() if verbose is None else verbose
    plan = Compiler(load_specification()).compile()

    output_dir = GENERATED_DIR / "compile"
    json_path = plan.export_json(output_dir / "execution_plan.json")
    html_path = plan.export_html(output_dir / "execution_plan.html")

    print(f"Compiled {len(plan.callables)} callables from {SPEC_PATH}")
    print(f"Execution plan: {json_path}")
    print(f"Execution plan report: {html_path}")

    if verbose:
        print("\nCallable dependency graph")
        plan.callable_graph.print_graph()
        print("\nExecution stages")
        for stage_number, stage in enumerate(plan.execution_stages, 1):
            print(f"Stage {stage_number}")
            for node in stage:
                dependencies = [
                    dependency.function_id for dependency in plan.callable_graph.dependencies(node)
                ]
                suffix = f" <- [{', '.join(dependencies)}]" if dependencies else ""
                print(f"  {node.function_id}({node.entity}) -> {node.feature}{suffix}")


if __name__ == "__main__":
    main()
