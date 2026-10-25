"""Loading and preparing project specification sources."""

from __future__ import annotations

import pathlib

from uptimely import entrypoint as entrypoint_module
from uptimely import project_paths as paths
from uptimely import spec
from uptimely.project import imports
from uptimely.spec import python as python_spec_api

JsonSourceInput = str | pathlib.Path | None


class PythonSource:
    """Resolve and load a Python spec declaration for a project."""

    def __init__(self, project_root: pathlib.Path, python_spec: str | None = None) -> None:
        self.path = project_root / paths.SPEC_PYTHON_ENTRY_FILE
        if python_spec is None:
            self.entrypoint = entrypoint_module.Entrypoint.from_path(
                self.path,
                imports.project_import_root(project_root),
                paths.DEFAULT_SPEC_ATTRIBUTE,
            )
        else:
            self.entrypoint = entrypoint_module.Entrypoint(python_spec)

    def is_available(self) -> bool:
        """Return whether the conventional Python spec entrypoint exists."""
        return self.path.is_file()

    def load(self) -> spec.Spec:
        """Validate and load a Python spec declaration."""
        declaration = self.entrypoint.resolve()
        if not isinstance(declaration, python_spec_api.PythonSpec):
            raise TypeError(
                f"{self.entrypoint.module.location}:{self.entrypoint.function.name} "
                "must be a PythonSpec"
            )
        return spec.from_python(
            entities=declaration.entities,
            dimensions=declaration.dimensions,
            name=declaration.name,
        )


class JsonSource:
    """Resolve and load a JSON spec source for a project."""

    def __init__(self, project_root: pathlib.Path, json_spec: JsonSourceInput = None) -> None:
        self.project_root = project_root
        self.json_spec = json_spec

    @property
    def path(self) -> pathlib.Path:
        """Return the configured or conventional JSON spec path."""
        configured_path = pathlib.Path(self.json_spec) if self.json_spec is not None else None
        return paths.resolve_path(configured_path, self.project_root, paths.SPEC_JSON_ENTRY_FILE)

    def is_available(self) -> bool:
        """Return whether the configured JSON spec source exists."""
        return self.path.is_file()

    def load(self) -> spec.Spec:
        """Load the configured or conventional JSON spec source."""
        return spec.load_spec(self.path)


class SpecSource:
    """Select and load an explicit or discovered project specification."""

    def __init__(self, project_root: pathlib.Path) -> None:
        self.project_root = project_root

    def load(
        self,
        python_spec: str | None = None,
        json_spec: JsonSourceInput = None,
    ) -> spec.Spec:
        """Resolve and load an explicit or discovered Python or JSON spec source."""
        return self.resolve(python_spec, json_spec).load()

    def resolve(
        self,
        python_spec: str | None = None,
        json_spec: JsonSourceInput = None,
    ) -> PythonSource | JsonSource:
        """Select an explicit or discovered source without loading its declaration."""
        if python_spec is not None and json_spec is not None:
            raise ValueError("Specify either a Python entrypoint or a spec JSON source, not both")

        if json_spec is not None:
            return JsonSource(self.project_root, json_spec)
        if python_spec is not None:
            return PythonSource(self.project_root, python_spec)

        python_source = PythonSource(self.project_root)
        json_source = JsonSource(self.project_root)
        python_available = python_source.is_available()
        json_available = json_source.is_available()

        if python_available and json_available:
            raise ValueError(
                f"Ambiguous spec sources: {python_source.path} and {json_source.path}. "
                "Specify one source explicitly."
            )
        if python_available:
            return python_source
        if json_available:
            return json_source
        raise FileNotFoundError(
            f"No spec source found. Expected {python_source.path} or {json_source.path}. "
            "Specify a Python entrypoint or JSON spec source explicitly."
        )


def load_spec_source(
    python_spec: str | None,
    project_root: pathlib.Path,
    json_spec: JsonSourceInput = None,
) -> spec.Spec:
    """Load an explicit or discovered Python or JSON spec source."""
    return SpecSource(project_root).load(python_spec, json_spec)
