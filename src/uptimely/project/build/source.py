"""Loading and preparing project specification sources."""

from __future__ import annotations

import importlib
import pathlib
import sys

from uptimely import spec
from uptimely.project import paths
from uptimely.spec import python as python_spec

SpecSource = str | pathlib.Path | None


def project_import_root(project_root: pathlib.Path) -> pathlib.Path:
    """Find the import root above a project's enclosing regular packages."""
    root = project_root.resolve()
    while (root / "__init__.py").is_file():
        root = root.parent
    return root


def prepare_project_root(project_root: pathlib.Path) -> None:
    """Make project function entrypoints importable without changing directories."""
    for path in (project_import_root(project_root), project_root.resolve()):
        root = str(path)
        if root not in sys.path:
            sys.path.insert(0, root)


def load_spec_source(
    entrypoint: str | None,
    project_root: pathlib.Path,
    *,
    source: SpecSource = None,
) -> spec.Spec:
    """Load and validate an explicit or discovered Python or JSON spec source."""
    if entrypoint is not None and source is not None:
        raise ValueError("Specify either a Python entrypoint or a spec JSON source, not both")
    prepare_project_root(project_root)

    if source is not None:
        return spec.load_spec(source)

    if entrypoint is None:
        python_source = project_root / paths.SPEC_PYTHON_ENTRY_FILE
        json_source = project_root / paths.SPEC_JSON_ENTRY_FILE
        if python_source.is_file() and json_source.is_file():
            raise ValueError(
                f"Ambiguous spec sources: {python_source} and {json_source}. "
                "Select one with --entrypoint or --spec."
            )
        if python_source.is_file():
            module = ".".join(
                python_source.resolve()
                .relative_to(project_import_root(project_root))
                .with_suffix("")
                .parts
            )
            entrypoint = f"{module}:{paths.DEFAULT_SPEC_ATTRIBUTE}"
        elif json_source.is_file():
            return spec.load_spec(json_source)
        else:
            raise FileNotFoundError(
                f"No spec source found. Expected {python_source} or {json_source}. "
                "Alternatively, specify --entrypoint or --spec."
            )

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
    return spec.from_python(
        entities=declaration.entities,
        dimensions=declaration.dimensions,
        name=declaration.name,
    )
