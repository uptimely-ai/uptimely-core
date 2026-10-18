"""Command-line tools for building and inspecting spec."""

import argparse
import pathlib

from uptimely import project, spec
from uptimely.cli import common
from uptimely.project import build as project_build
from uptimely.spec import feature_graph


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure spec build and feature-graph actions."""
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser(
        "build",
        help="Build spec JSON from project sources",
        description=(
            f"Discover {project.SPEC_PYTHON_ENTRY_FILE} or "
            f"{project.SPEC_JSON_ENTRY_FILE} under the project root, "
            "or select an explicit source."
        ),
    )
    configure_build_source_arguments(build)
    build.add_argument(
        "--output",
        type=pathlib.Path,
        help=f"JSON output (default: {project.SPEC_JSON_FILE} under --project-root)",
    )
    graph = actions.add_parser("feature-graph", help="Inspect feature dependencies")
    common.configure_project_arguments(graph)


def configure_build_source_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared source selection and project-root options for build commands."""
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--entrypoint",
        metavar="MODULE:ATTRIBUTE",
        help="Importable module and attribute containing a PythonSpec instance",
    )
    source.add_argument(
        "--spec",
        type=pathlib.Path,
        help="Source spec JSON path (overrides standard source discovery)",
    )
    parser.add_argument(
        "--project-root",
        type=pathlib.Path,
        help="Root added to the import path and used to resolve the default output",
    )


def build_spec(
    entrypoint: str | None,
    output: pathlib.Path,
    project_root: pathlib.Path,
    *,
    source: pathlib.Path | None = None,
) -> str:
    """Build validated spec JSON from an explicit or discovered source.

    Args:
        entrypoint: ``module:attribute`` exposing a PythonSpec, or discover
            the standard source when neither this nor source is supplied.
        output: Destination for spec JSON.
        project_root: Directory added to the Python import path.
        source: Explicit spec JSON path, mutually exclusive with entrypoint.

    Returns:
        The written spec path.

    Raises:
        ImportError: The declaration module or a dependency cannot be imported.
        AttributeError: The module does not expose the selected attribute.
        TypeError: The declaration is not a PythonSpec.
        ValueError: The source selection is ambiguous or spec is invalid.
        SyntaxError: A Python source cannot be parsed.
        OSError: A source cannot be read or the output cannot be written.
    """
    spec_definition = project_build.load_spec_source(
        entrypoint,
        project_root,
        source=source,
    )
    return spec.write_document(spec_definition, output)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Build spec or print feature graph summaries and trees."""
    if args.action == "build":
        output = common.project_path(args.output, args.project_root, project.SPEC_JSON_FILE)
        try:
            path = build_spec(
                args.entrypoint,
                output,
                args.project_root or pathlib.Path.cwd(),
                source=args.spec,
            )
        except (OSError, ValueError, ImportError, AttributeError, TypeError, SyntaxError) as error:
            parser.exit(1, f"uptimely: error: {error}\n")
        print(f"Spec written to {path}")
        return
    spec_definition = common.project_path(args.spec, args.project_root, project.SPEC_JSON_FILE)
    try:
        spec_definition = common.load_spec(spec_definition, args.project_root or pathlib.Path.cwd())
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
    except (OSError, ValueError, ImportError, AttributeError, TypeError) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
