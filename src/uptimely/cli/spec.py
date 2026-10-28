"""Command-line tools for inspecting spec features."""

import argparse
import logging

from uptimely import project, spec
from uptimely.cli import common
from uptimely.spec import feature_graph as feature_graph_module

logger = logging.getLogger(__name__)


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the spec feature-graph command."""
    actions = parser.add_subparsers(dest="action", required=True)
    feature_graph_parser = actions.add_parser("feature-graph", help="Inspect feature dependencies")
    common.configure_project_arguments(feature_graph_parser)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Log feature-graph summaries and trees."""
    project_root = common.resolve_project_root(args, parser)
    try:
        if args.spec is None:
            with project.read_build_bundle(project_root) as bundle:
                spec_definition = spec.load_spec(bundle.spec_path)
        else:
            spec_definition = spec.load_spec(args.spec)
        feature_graph = feature_graph_module.FeatureGraph(spec_definition)
        subset = feature_graph.subset(args.features) if args.features is not None else None
        logger.info("Feature graph: %d features", len(feature_graph.feature_names))
        if subset is not None:
            logger.info("Selected feature subset: %d features", len(subset.feature_names))
        if args.verbose:
            logger.info("\nFeature graph\n%s", feature_graph.render_graph())
            if subset is not None:
                logger.info("\nSelected feature subset\n%s", subset.render_graph())
    except (OSError, ValueError, ImportError, AttributeError, TypeError, RuntimeError) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
