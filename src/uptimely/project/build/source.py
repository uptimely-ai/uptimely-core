"""Loading and preparing project specification sources."""

from __future__ import annotations

import importlib
import pathlib
import sys

from uptimely import spec
from uptimely.project import paths
from uptimely.spec import python as python_spec_api

JsonSourceInput = str | pathlib.Path | None


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


class PythonSource:
    """Resolve and load a Python spec declaration for a project."""

    def __init__(self, spec_source: SpecSource) -> None:
        self._spec_source = spec_source

    @property
    def path(self) -> pathlib.Path:
        """Return the conventional Python spec entrypoint path."""
        return self._spec_source.project_root / paths.SPEC_PYTHON_ENTRY_FILE

    def is_available(self) -> bool:
        """Return whether the conventional Python spec entrypoint exists."""
        return self.path.is_file()

    def _default_entrypoint(self) -> str:
        module = ".".join(
            self.path.resolve()
            .relative_to(project_import_root(self._spec_source.project_root))
            .with_suffix("")
            .parts
        )
        return f"{module}:{paths.DEFAULT_SPEC_ATTRIBUTE}"

    def load(self, python_spec: str | None = None) -> spec.Spec:
        """Validate and load a Python spec declaration."""
        if python_spec is None:
            python_spec = self._default_entrypoint()
        module, separator, attribute = python_spec.partition(":")
        if (
            not separator
            or not all(part.isidentifier() for part in module.split("."))
            or not attribute.isidentifier()
        ):
            raise ValueError(
                f"Invalid spec entrypoint: {python_spec!r}. Expected 'module:attribute'."
            )

        declaration = getattr(importlib.import_module(module), attribute)
        if not isinstance(declaration, python_spec_api.PythonSpec):
            raise TypeError(f"{python_spec} must be a PythonSpec")
        return spec.from_python(
            entities=declaration.entities,
            dimensions=declaration.dimensions,
            name=declaration.name,
        )


class JsonSource:
    """Resolve and load a JSON spec source for a project."""

    def __init__(self, spec_source: SpecSource) -> None:
        self._spec_source = spec_source

    @property
    def path(self) -> pathlib.Path:
        """Return the conventional JSON spec entrypoint path."""
        return self._spec_source.project_root / paths.SPEC_JSON_ENTRY_FILE

    def is_available(self) -> bool:
        """Return whether the conventional JSON spec entrypoint exists."""
        return self.path.is_file()

    def load(self, json_spec: JsonSourceInput = None) -> spec.Spec:
        """Load an explicit or conventional JSON spec source."""
        return spec.load_spec(self.path if json_spec is None else json_spec)


class SpecSource:
    """Select and load an explicit or discovered project specification."""

    def __init__(self, project_root: pathlib.Path) -> None:
        self.project_root = project_root
        self.python = PythonSource(self)
        self.json = JsonSource(self)

    def load(
        self,
        python_spec: str | None = None,
        json_spec: JsonSourceInput = None,
    ) -> spec.Spec:
        """Resolve and load an explicit or discovered Python or JSON spec source."""
        if python_spec is not None and json_spec is not None:
            raise ValueError("Specify either a Python entrypoint or a spec JSON source, not both")
        prepare_project_root(self.project_root)

        if json_spec is not None:
            return self.json.load(json_spec)
        if python_spec is not None:
            return self.python.load(python_spec)

        python_available = self.python.is_available()
        json_available = self.json.is_available()
        if python_available and json_available:
            raise ValueError(
                f"Ambiguous spec sources: {self.python.path} and {self.json.path}. "
                "Select one with --python-spec or --json-spec."
            )
        if python_available:
            return self.python.load()
        if json_available:
            return self.json.load()
        raise FileNotFoundError(
            f"No spec source found. Expected {self.python.path} or {self.json.path}. "
            "Alternatively, specify --python-spec or --json-spec."
        )


def load_spec_source(
    python_spec: str | None,
    project_root: pathlib.Path,
    json_spec: JsonSourceInput = None,
) -> spec.Spec:
    """Load an explicit or discovered Python or JSON spec source."""
    return SpecSource(project_root).load(python_spec, json_spec)
