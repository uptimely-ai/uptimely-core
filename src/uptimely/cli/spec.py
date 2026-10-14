"""Command-line tools for exporting and inspecting specifications."""

import argparse
import importlib
import pathlib

from uptimely import spec as spec_module
from uptimely.analytics import feature_graph
from uptimely.cli import common
from uptimely.spec import python_spec


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure specification export and feature-graph actions."""
    actions = parser.add_subparsers(dest="action", required=True)
    export = actions.add_parser("export", help="Export a Python specification to JSON")
    export.add_argument(
        "--module",
        required=True,
        help="Importable module exposing a PythonSpecification named python_specification",
    )
    export.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Root added to the import path and used to resolve the default output",
    )
    export.add_argument(
        "--output",
        type=pathlib.Path,
        help="JSON output (default: _generated/spec/spec.json under --project-root)",
    )
    graph = actions.add_parser("feature-graph", help="Inspect feature dependencies")
    common.configure_project_arguments(graph)


def export_specification(module: str, output: pathlib.Path, project_root: pathlib.Path) -> str:
    """Export a module's Python declaration as a canonical JSON specification.

    Args:
        module: Importable module exposing ``python_specification``.
        output: Destination for the JSON specification.
        project_root: Directory added to the Python import path.

    Returns:
        The written specification path.

    Raises:
        ImportError: The declaration module or a dependency cannot be imported.
        AttributeError: The module does not expose ``python_specification``.
        TypeError: The declaration is not a PythonSpecification.
        ValueError: The specification is invalid.
        OSError: The output cannot be written.
    """
    common.prepare_project_root(project_root)
    declaration = importlib.import_module(module).python_specification
    if not isinstance(declaration, python_spec.PythonSpecification):
        raise TypeError(f"{module}.python_specification must be a PythonSpecification")
    specification = spec_module.Specification.from_python(
        entities=declaration.entities,
        dimensions=declaration.dimensions,
        name=declaration.name,
    )
    return specification.to_json(output)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Export a specification or print feature graph summaries and trees."""
    if args.action == "export":
        output = common.project_path(args.output, args.project_root, common.GENERATED_SPEC_PATH)
        try:
            path = export_specification(
                args.module, output, args.project_root or pathlib.Path.cwd()
            )
        except (OSError, ValueError, ImportError, AttributeError, TypeError) as error:
            parser.exit(1, f"uptimely: error: {error}\n")
        print(f"Specification written to {path}")
        return
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
