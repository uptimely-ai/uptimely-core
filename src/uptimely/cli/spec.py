"""Command-line tools for building and inspecting spec."""

import argparse
import importlib
import pathlib

from uptimely import project, spec
from uptimely.cli import common
from uptimely.spec import feature_graph
from uptimely.spec import python as python_spec


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
    if entrypoint is not None and source is not None:
        raise ValueError("Specify either a Python entrypoint or a spec JSON source, not both")
    common.prepare_project_root(project_root)
    if entrypoint is None and source is None:
        python_source = project_root / project.SPEC_PYTHON_ENTRY_FILE
        json_source = project_root / project.SPEC_JSON_ENTRY_FILE
        if python_source.is_file() and json_source.is_file():
            raise ValueError(
                f"Ambiguous spec sources: {python_source} and {json_source}. "
                "Select one with --entrypoint or --spec."
            )
        if python_source.is_file():
            module = ".".join(
                python_source.resolve()
                .relative_to(common.project_import_root(project_root))
                .with_suffix("")
                .parts
            )
            entrypoint = f"{module}:{project.DEFAULT_SPEC_ATTRIBUTE}"
        elif json_source.is_file():
            source = json_source
        else:
            raise FileNotFoundError(
                f"No spec source found. Expected {python_source} or {json_source}. "
                "Alternatively, specify --entrypoint or --spec."
            )
    if source is not None:
        return spec.write_document(spec.load_spec(source), output)
    if entrypoint is None:
        raise ValueError("A spec Python entrypoint or JSON source is required")
    module, separator, attribute = entrypoint.partition(":")
    if (
        not separator
        or not all(part.isidentifier() for part in module.split("."))
        or not attribute.isidentifier()
    ):
        raise ValueError(f"Invalid spec entrypoint: {entrypoint!r}. Expected 'module:attribute'.")
    declaration = getattr(importlib.import_module(module), attribute)
    if not isinstance(declaration, python_spec.PythonSpec):
        raise TypeError(f"{entrypoint} must be a PythonSpec")
    spec_definition = spec.from_python(
        entities=declaration.entities,
        dimensions=declaration.dimensions,
        name=declaration.name,
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
