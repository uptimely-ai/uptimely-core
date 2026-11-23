"""Resolve and load specification sources for an Uptimely project."""

from __future__ import annotations

import dataclasses
import pathlib

from uptimely import spec
from uptimely.codebase.python import entrypoint as entrypoint_module

from . import defaults, paths

JsonSourceInput = str | pathlib.Path | None


@dataclasses.dataclass(frozen=True)
class PythonSpecSource:
    """Describe a resolved Python spec source."""

    path: pathlib.Path | None
    entrypoint: entrypoint_module.Entrypoint

    @property
    def display_name(self) -> str:
        """Return a path for conventional sources or the explicit entrypoint."""
        if self.path is not None:
            return str(self.path.resolve())
        return entrypoint_module.Entrypoint.format(
            self.entrypoint.module.location, self.entrypoint.function.name
        )


@dataclasses.dataclass(frozen=True)
class JsonSpecSource:
    """Describe a resolved JSON spec source."""

    path: pathlib.Path

    @property
    def display_name(self) -> str:
        """Return the resolved JSON source path."""
        return str(self.path.resolve())


ResolvedSpecSource = PythonSpecSource | JsonSpecSource


class SpecSourceResolver:
    """Resolve explicit or conventional project specification sources."""

    def __init__(self, project_root: pathlib.Path) -> None:
        self.project_root = project_root.resolve()

    def resolve(
        self,
        python_spec: str | None = None,
        json_spec: JsonSourceInput = None,
    ) -> ResolvedSpecSource:
        """Select one explicit or discovered source without loading it."""
        if python_spec is not None and json_spec is not None:
            raise ValueError("Specify either a Python entrypoint or a spec JSON source, not both")

        if python_spec is not None:
            return PythonSpecSource(
                None,
                entrypoint_module.Entrypoint(python_spec),
            )
        if json_spec is not None:
            json_path = pathlib.Path(json_spec)
            if not json_path.is_absolute():
                json_path = self.project_root / json_path
            return JsonSpecSource(json_path)

        python_path = self.project_root / paths.SPEC_PYTHON_ENTRY_FILE
        json_path = self.project_root / paths.SPEC_JSON_ENTRY_FILE
        python_available = python_path.is_file()
        json_available = json_path.is_file()
        if python_available and json_available:
            raise ValueError(
                f"Ambiguous spec sources: {python_path} and {json_path}. "
                "Specify one source explicitly."
            )
        if python_available:
            return PythonSpecSource(
                python_path,
                entrypoint_module.Entrypoint.from_path(
                    python_path,
                    entrypoint_module.Module.find_import_root(self.project_root),
                    defaults.DEFAULT_SPEC_ATTRIBUTE,
                ),
            )
        if json_available:
            return JsonSpecSource(json_path)
        raise FileNotFoundError(
            f"No spec source found. Expected {python_path} or {json_path}. "
            "Specify a Python entrypoint or JSON spec source explicitly."
        )


def load_spec_source(source: ResolvedSpecSource, *, validate: bool = True) -> spec.Spec:
    """Load and convert a resolved specification source."""
    if isinstance(source, PythonSpecSource):
        return spec.load_python_spec(source.entrypoint, validate=validate)
    return spec.load_spec(source.path, validate=validate)
