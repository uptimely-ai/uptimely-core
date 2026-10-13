from examples.example_1.common import load_specification, verbose_requested

from uptimely.analytics.feature_graph import FeatureGraph


def main(verbose: bool | None = None) -> None:
    """Inspect the full and health-signal feature graphs."""
    verbose = verbose_requested() if verbose is None else verbose
    specification = load_specification()
    feature_graph = FeatureGraph(specification)

    subset = feature_graph.subset(["health_signal_normalized"])
    print(
        f"Feature graph: {len(feature_graph.feature_names)} features; "
        f"health signal subset: {len(subset.feature_names)} features"
    )

    if verbose:
        print("\nFeature graph")
        feature_graph.print_graph()
        print("\nHealth signal subset")
        subset.print_graph()


if __name__ == "__main__":
    main()
