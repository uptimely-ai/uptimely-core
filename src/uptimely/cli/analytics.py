"""Command-line tools for building and inspecting analytics."""

import argparse
import importlib
import pathlib

from uptimely import analytics, project
from uptimely.analytics import feature_graph
from uptimely.analytics import python as python_analytics
from uptimely.cli import common


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure analytics build and feature-graph actions."""
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser(
        "build",
        help="Build analytics JSON from project sources",
        description=(
            f"Discover {project.ANALYTICS_PYTHON_ENTRY_FILE} or "
            f"{project.ANALYTICS_JSON_ENTRY_FILE} under the project root, "
            "or select an explicit source."
        ),
    )
    source = build.add_mutually_exclusive_group()
    source.add_argument(
        "--module",
        help="Importable module exposing a PythonAnalytics named python_analytics",
    )
    source.add_argument(
        "--analytics",
        type=pathlib.Path,
        help="Source analytics JSON path (overrides standard source discovery)",
    )
    build.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Root added to the import path and used to resolve the default output",
    )
    build.add_argument(
        "--output",
        type=pathlib.Path,
        help=f"JSON output (default: {project.ANALYTICS_JSON_FILE} under --project-root)",
    )
    graph = actions.add_parser("feature-graph", help="Inspect feature dependencies")
    common.configure_project_arguments(graph)


def build_analytics(
    module: str | None,
    output: pathlib.Path,
    project_root: pathlib.Path,
    *,
    source: pathlib.Path | None = None,
) -> str:
    """Build validated analytics JSON from an explicit or discovered source.

    Args:
        module: Importable module exposing ``python_analytics``, or discover
            the standard source when neither this nor source is supplied.
        output: Destination for analytics JSON.
        project_root: Directory added to the Python import path.
        source: Explicit analytics JSON path, mutually exclusive with module.

    Returns:
        The written analytics path.

    Raises:
        ImportError: The declaration module or a dependency cannot be imported.
        AttributeError: The module does not expose ``python_analytics``.
        TypeError: The declaration is not a PythonAnalytics.
        ValueError: The source selection is ambiguous or analytics is invalid.
        SyntaxError: A Python source cannot be parsed.
        OSError: A source cannot be read or the output cannot be written.
    """
    if module is not None and source is not None:
        raise ValueError("Specify either a Python module or an analytics JSON source, not both")
    common.prepare_project_root(project_root)
    if module is None and source is None:
        python_source = project_root / project.ANALYTICS_PYTHON_ENTRY_FILE
        json_source = project_root / project.ANALYTICS_JSON_ENTRY_FILE
        if python_source.is_file() and json_source.is_file():
            raise ValueError(
                f"Ambiguous analytics sources: {python_source} and {json_source}. "
                "Select one with --module or --analytics."
            )
        if python_source.is_file():
            module = ".".join(
                python_source.resolve()
                .relative_to(common.project_import_root(project_root))
                .with_suffix("")
                .parts
            )
        elif json_source.is_file():
            source = json_source
        else:
            raise FileNotFoundError(
                f"No analytics source found. Expected {python_source} or {json_source}. "
                "Alternatively, specify --module or --analytics."
            )
    if source is not None:
        return analytics.write_document(analytics.load_analytics(source), output)
    if module is None:
        raise ValueError("An analytics Python module or JSON source is required")
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
    """Build analytics or print feature graph summaries and trees."""
    if args.action == "build":
        output = common.project_path(args.output, args.project_root, project.ANALYTICS_JSON_FILE)
        try:
            path = build_analytics(
                args.module,
                output,
                args.project_root or pathlib.Path.cwd(),
                source=args.analytics,
            )
        except (OSError, ValueError, ImportError, AttributeError, TypeError, SyntaxError) as error:
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
