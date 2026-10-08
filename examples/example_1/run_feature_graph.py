from examples.example_1.common import GENERATED_DIR, load_specification, verbose_requested

from uptimely.analytics.feature_graph import FeatureGraph


def main(verbose: bool | None = None) -> None:
    """Export the full and health-signal feature graphs."""
    verbose = verbose_requested() if verbose is None else verbose
    specification = load_specification()
    feature_graph = FeatureGraph(specification)

    graph_path = GENERATED_DIR / "graph" / "feature_graph.html"
    feature_graph.export_html(graph_path)

    subset = feature_graph.subset(["health_signal_normalized"])
    subset_path = GENERATED_DIR / "graph" / "subset.html"
    subset.export_html(subset_path)
    print(f"Feature graphs: {graph_path}, {subset_path}")

    if verbose:
        print("\nFeature graph")
        feature_graph.print_graph()
        print("\nHealth signal subset")
        subset.print_graph()


if __name__ == "__main__":
    main()
