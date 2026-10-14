"""Command-line tools for inspecting specification feature graphs."""

import argparse
import pathlib

from uptimely.analytics import feature_graph
from uptimely.cli import common


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the spec feature-graph action."""
    actions = parser.add_subparsers(dest="action", required=True)
    graph = actions.add_parser("feature-graph", help="Inspect feature dependencies")
    common.configure_project_arguments(graph)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Print feature graph summaries and optionally dependency trees."""
    spec = common.project_path(args.spec, args.project_root, common.GENERATED_SPEC_PATH)
    try:
        specification = common.load_specification(spec, args.project_root or pathlib.Path.cwd())
        graph = feature_graph.FeatureGraph(specification)
        subset = graph.subset(args.features) if args.features is not None else None
        print(f"Feature graph: {len(graph.feature_names)} features")
        if subset is not None:
            print(f"Selected feature subset: {len(subset.feature_names)} features")
        if args.verbose:
            print("\nFeature graph")
            graph.print_graph()
            if subset is not None:
                print("\nSelected feature subset")
                subset.print_graph()
    except (OSError, ValueError, ImportError, AttributeError, TypeError) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
