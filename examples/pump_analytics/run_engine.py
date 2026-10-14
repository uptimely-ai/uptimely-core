"""Execute the selected analytics flow from example 1."""

from examples.pump_analytics.common import SPEC_PATH, load_specification, verbose_requested
from examples.pump_analytics.spec.spec import storage_resources

from uptimely.compile import Compiler
from uptimely.engine import Engine


def main(verbose: bool | None = None) -> list[str]:
    """Execute the selected engine flow and return its calculated feature IDs."""
    verbose = verbose_requested() if verbose is None else verbose
    specification = load_specification()
    # To process a subset, pass to compiler:
    # features=["health_signal_normalized"]
    plan = Compiler(specification).compile()
    engine = Engine(plan, bind={"storage": storage_resources})
    result = engine.execute()
    if result.failures:
        failures = "; ".join(result.failures.values())
        raise RuntimeError(f"Engine flow failed: {failures}")
    calculated_features = sorted({feature_id for _, _, feature_id in result.calculated_outputs})
    print("Engine ran completed the flow")
    print(f"{len(plan.operations)} operations")
    print("Calculated features: " + ", ".join(calculated_features))
    print(f"Specification: {SPEC_PATH}")

    if verbose:
        print("\nOperation execution order")
        for stage in plan.execution_stages:
            for operation in stage:
                print(operation.function_id)
        print("\nDataset registry")
        for entity_id, entity in specification.entities.items():
            for dataset in entity.datasets:
                print(f"Dataset({entity_id}, {dataset.id}): {len(dataset.features)} features")

    return calculated_features


if __name__ == "__main__":
    main()
