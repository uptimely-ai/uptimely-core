"""Command-line tools for inspecting spec features."""

import argparse
import pathlib

from uptimely import project
from uptimely.cli import common
from uptimely.spec import feature_graph


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure spec feature-graph inspection."""
    actions = parser.add_subparsers(dest="action", required=True)
    graph = actions.add_parser("feature-graph", help="Inspect feature dependencies")
    common.configure_project_arguments(graph)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Print feature graph summaries and trees."""
    project_root = args.project_root or pathlib.Path.cwd()
    try:
        if args.spec is None:
            with project.read_build_bundle(project_root) as bundle:
                spec_definition = common.load_spec(bundle.spec_path, project_root)
        else:
            spec_definition = common.load_spec(args.spec, project_root)
        graph = feature_graph.FeatureGraph(spec_definition)
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
    except (OSError, ValueError, ImportError, AttributeError, TypeError, RuntimeError) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
