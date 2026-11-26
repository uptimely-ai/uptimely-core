"""Resolve and load specification sources for an Uptimely project."""

from __future__ import annotations

import dataclasses
import pathlib

from uptimely import spec
from uptimely.codebase.python import entrypoint as entrypoint_module
from uptimely.spec import yaml as yaml_spec_module

from . import defaults, paths

JsonSourceInput = str | pathlib.Path | None
YamlSourceInput = str | pathlib.Path | None


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


@dataclasses.dataclass(frozen=True)
class YamlSpecSource:
    """Describe a YAML Spec file or directory."""

    path: pathlib.Path

    @property
    def display_name(self) -> str:
        """Return the resolved YAML source path."""
        return str(self.path.resolve())


ResolvedSpecSource = PythonSpecSource | JsonSpecSource | YamlSpecSource


class SpecSourceResolver:
    """Resolve explicit or conventional project specification sources."""

    def __init__(self, project_root: pathlib.Path) -> None:
        self.project_root = project_root.resolve()

    def resolve(
        self,
        python_spec: str | None = None,
        json_spec: JsonSourceInput = None,
        yaml_spec: YamlSourceInput = None,
    ) -> ResolvedSpecSource:
        """Select one explicit or discovered source without loading it."""
        if sum(value is not None for value in (python_spec, json_spec, yaml_spec)) > 1:
            raise ValueError("Specify only one Python, JSON, or YAML spec source")

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
        if yaml_spec is not None:
            yaml_path = pathlib.Path(yaml_spec)
            if not yaml_path.is_absolute():
                yaml_path = self.project_root / yaml_path
            return YamlSpecSource(yaml_path)

        python_path = self.project_root / paths.SPEC_PYTHON_ENTRY_FILE
        json_path = self.project_root / paths.SPEC_JSON_ENTRY_FILE
        yaml_path = self.project_root / paths.SPEC_SOURCE_DIR
        python_available = python_path.is_file()
        json_available = json_path.is_file()
        yaml_available = yaml_path.is_dir() and any(
            item.is_file() and item.suffix in {".yaml", ".yml"} for item in yaml_path.rglob("*")
        )
        if sum((python_available, json_available, yaml_available)) > 1:
            raise ValueError(
                f"Ambiguous spec sources in {yaml_path}. Specify one source explicitly."
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
        if yaml_available:
            return YamlSpecSource(yaml_path)
        raise FileNotFoundError(
            f"No spec source found. Expected {python_path}, {json_path}, "
            f"or YAML files in {yaml_path}. Specify a source explicitly."
        )


def load_spec_source(source: ResolvedSpecSource, *, validate: bool = True) -> spec.Spec:
    """Load and convert a resolved specification source."""
    if isinstance(source, PythonSpecSource):
        return spec.load_python_spec(source.entrypoint, validate=validate)
    if isinstance(source, JsonSpecSource):
        return spec.load_spec(source.path, validate=validate)
    return yaml_spec_module.load_spec(source.path, validate=validate)
