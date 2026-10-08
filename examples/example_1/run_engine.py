"""Execute the selected analytics flow from example 1."""

from examples.example_1.common import SPEC_PATH, load_specification, verbose_requested
from examples.example_1.spec.spec import storage_resources

from uptimely.compile import Compiler
from uptimely.engine import Engine


def main(verbose: bool | None = None) -> list[str]:
    """Execute the selected engine flow and return its calculated feature IDs."""
    verbose = verbose_requested() if verbose is None else verbose
    specification = load_specification()
    # To process a subset, pass to compiler:
    # features=["health_signal_normalized"]
    plan = Compiler(specification).compile()
    engine = Engine(specification, plan, runtime_resources={"storage": storage_resources})
    result = engine.execute()
    if result.failures:
        failures = "; ".join(result.failures.values())
        raise RuntimeError(f"Engine flow failed: {failures}")
    calculated_features = sorted({feature_id for _, _, feature_id in result.calculated_outputs})
    print("Engine ran completed the flow")
    print(f"{len(engine.callable_order)} callables")
    print("Calculated features: " + ", ".join(calculated_features))
    print(f"Specification: {SPEC_PATH}")

    if verbose:
        print("\nCallable execution order")
        for callable_node in engine.callable_order:
            print(callable_node.function_id)
        print("\nDataset registry")
        for entity_id, entity in engine.specification.entities.items():
            for dataset in entity.datasets:
                print(f"Dataset({entity_id}, {dataset.id}): {len(dataset.features)} features")

    return calculated_features


if __name__ == "__main__":
    main()
