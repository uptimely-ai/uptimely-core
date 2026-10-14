"""Run the example workflows in a useful demonstration order."""

import sys
from pathlib import Path


def main() -> None:
    """Run both example workflows in sequence."""
    repository_root = Path(__file__).parent.parent
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))

    from examples.pump_analytics.run_engine import main as execute_engine
    from examples.pump_analytics.run_execution_plan import main as create_plan
    from examples.pump_analytics.run_export_spec import main as export_spec
    from examples.pump_analytics.run_feature_graph import main as create_graph
    from examples.simple_analytics.run_export_spec import main as export_python_spec

    workflows = (
        ("Pump analytics: specification", export_spec),
        ("Pump analytics: execution plan", create_plan),
        ("Pump analytics: feature graph", create_graph),
        ("Pump analytics: engine", execute_engine),
        ("Simple analytics: export Python specification", export_python_spec),
    )
    for title, workflow in workflows:
        print(f"\n=== {title} ===")
        workflow()


if __name__ == "__main__":
    main()
