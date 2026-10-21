"""Loading and preparing project specification sources."""

from __future__ import annotations

import pathlib

from uptimely import entrypoint as entrypoint_module
from uptimely import spec
from uptimely.project import imports, paths
from uptimely.spec import python as python_spec_api

JsonSourceInput = str | pathlib.Path | None


class PythonSource:
    """Resolve and load a Python spec declaration for a project."""

    def __init__(self, project_root: pathlib.Path, python_spec: str | None = None) -> None:
        self.project_root = project_root
        self.path = project_root / paths.SPEC_PYTHON_ENTRY_FILE
        self.entrypoint = entrypoint_module.Entrypoint(
            self._default_entrypoint() if python_spec is None else python_spec,
            root=imports.project_import_root(project_root),
        )

    def is_available(self) -> bool:
        """Return whether the conventional Python spec entrypoint exists."""
        return self.path.is_file()

    def _default_entrypoint(self) -> str:
        module = ".".join(
            self.path.resolve()
            .relative_to(imports.project_import_root(self.project_root))
            .with_suffix("")
            .parts
        )
        return f"{module}:{paths.DEFAULT_SPEC_ATTRIBUTE}"

    def load(self) -> spec.Spec:
        """Validate and load a Python spec declaration."""
        module = self.entrypoint.module.load()
        name = self.entrypoint.function.name
        declaration = getattr(module, name)
        if not isinstance(declaration, python_spec_api.PythonSpec):
            raise TypeError(f"{self.entrypoint.module.location}:{name} must be a PythonSpec")
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
        if self.json_spec is not None:
            return pathlib.Path(self.json_spec)
        return self.project_root / paths.SPEC_JSON_ENTRY_FILE

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

        imports.prepare_project_root(self.project_root)
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
