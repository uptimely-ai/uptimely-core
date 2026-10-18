"""Command-line tools for exporting and inspecting analytics."""

import argparse
import importlib
import pathlib

from uptimely import analytics, project
from uptimely.analytics import feature_graph
from uptimely.analytics import python as python_analytics
from uptimely.cli import common


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure analytics export and feature-graph actions."""
    actions = parser.add_subparsers(dest="action", required=True)
    export = actions.add_parser("export", help="Export Python analytics to JSON")
    export.add_argument(
        "--module",
        required=True,
        help="Importable module exposing a PythonAnalytics named python_analytics",
    )
    export.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Root added to the import path and used to resolve the default output",
    )
    export.add_argument(
        "--output",
        type=pathlib.Path,
        help=f"JSON output (default: {project.ANALYTICS_JSON_FILE} under --project-root)",
    )
    graph = actions.add_parser("feature-graph", help="Inspect feature dependencies")
    common.configure_project_arguments(graph)


def export_analytics(module: str, output: pathlib.Path, project_root: pathlib.Path) -> str:
    """Export a module's Python declaration in the analytics JSON format.

    Args:
        module: Importable module exposing ``python_analytics``.
        output: Destination for analytics JSON.
        project_root: Directory added to the Python import path.

    Returns:
        The written analytics path.

    Raises:
        ImportError: The declaration module or a dependency cannot be imported.
        AttributeError: The module does not expose ``python_analytics``.
        TypeError: The declaration is not a PythonAnalytics.
        ValueError: The analytics declaration is invalid.
        OSError: The output cannot be written.
    """
    common.prepare_project_root(project_root)
    declaration = importlib.import_module(module).python_analytics
    if not isinstance(declaration, python_analytics.PythonAnalytics):
        raise TypeError(f"{module}.python_analytics must be a PythonAnalytics")
    analytics_definition = analytics.from_python(
        entities=declaration.entities,
        dimensions=declaration.dimensions,
        name=declaration.name,
    )
    return analytics.write_document(analytics_definition, output)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Export analytics or print feature graph summaries and trees."""
    if args.action == "export":
        output = common.project_path(args.output, args.project_root, project.ANALYTICS_JSON_FILE)
        try:
            path = export_analytics(args.module, output, args.project_root or pathlib.Path.cwd())
        except (OSError, ValueError, ImportError, AttributeError, TypeError) as error:
            parser.exit(1, f"uptimely: error: {error}\n")
        print(f"Analytics written to {path}")
        return
    analytics_definition = common.project_path(
        args.analytics, args.project_root, project.ANALYTICS_JSON_FILE
    )
    try:
        analytics_definition = common.load_analytics(
            analytics_definition, args.project_root or pathlib.Path.cwd()
        )
        graph = feature_graph.FeatureGraph(analytics_definition)
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
