"""Run the example workflows in a useful demonstration order."""

import sys
from pathlib import Path


def main() -> None:
    """Run setup validation followed by both examples."""
    repository_root = Path(__file__).parent.parent
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))

    from examples.pump_analytics.run_docs import main as create_docs
    from examples.pump_analytics.run_engine import main as execute_engine
    from examples.pump_analytics.run_execution_plan import main as create_plan
    from examples.pump_analytics.run_export_spec import main as export_spec
    from examples.pump_analytics.run_feature_graph import main as create_graph
    from examples.simple_analytics.run_export_spec import main as export_python_spec

    print("=== Checking setup ===")
    from examples.check_setup import main as check_setup

    check_setup()
    workflows = (
        ("Example 1: specification", export_spec),
        ("Example 1: execution plan", create_plan),
        ("Example 1: documentation", create_docs),
        ("Example 1: feature graph", create_graph),
        ("Example 1: engine", execute_engine),
        ("Example 2: export Python specification", export_python_spec),
    )
    for title, workflow in workflows:
        print(f"\n=== {title} ===")
        workflow()


if __name__ == "__main__":
    main()
