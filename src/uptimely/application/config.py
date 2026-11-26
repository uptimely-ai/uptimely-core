"""Validated configuration for an analytics project."""

from __future__ import annotations

import math
import re
import typing

import pydantic

from uptimely.engine import config as engine_config
from uptimely.project import config as project_config
from uptimely.project import defaults as project_defaults


class Params(pydantic.RootModel[dict[str, typing.Any]]):
    """Flat map of required global parameter values."""

    model_config = pydantic.ConfigDict(strict=True, frozen=True)

    @pydantic.model_validator(mode="before")
    @classmethod
    def validate_values(cls, value: object) -> object:
        """Require Python-identifier keys and scalar values."""
        if not isinstance(value, dict):
            raise ValueError("Parameter configuration must be a flat TOML table")
        for name, parameter in value.items():
            if not isinstance(name, str) or re.fullmatch(r"[A-Za-z_]\w*", name) is None:
                raise ValueError(f"Invalid parameter name: {name!r}")
            if parameter is not None and type(parameter) not in {str, int, float, bool}:
                raise ValueError(
                    f"Parameter {name} must be a scalar (string, number, boolean, or null)"
                )
            if isinstance(parameter, float) and not math.isfinite(parameter):
                raise ValueError(f"Parameter {name} must be a finite number")
        return value


class Paths(pydantic.RootModel[dict[str, str]]):
    """Project-relative or absolute paths available to function bindings."""

    model_config = pydantic.ConfigDict(strict=True, frozen=True)

    @pydantic.model_validator(mode="before")
    @classmethod
    def validate_values(cls, value: object) -> object:
        """Require a flat mapping of Python identifiers to path strings."""
        if not isinstance(value, dict):
            raise ValueError("Path configuration must be a flat TOML table")
        for name, path in value.items():
            if not isinstance(name, str) or re.fullmatch(r"[A-Za-z_]\w*", name) is None:
                raise ValueError(f"Invalid path name: {name!r}")
            if not isinstance(path, str):
                raise ValueError(f"Path {name} must be a string")
        return value


class ProjectSettings(pydantic.BaseModel):
    """Project-level defaults for specification sources and execution."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    python_spec: str | None = pydantic.Field(default=None, min_length=1)
    json_spec: str | None = pydantic.Field(default=None, min_length=1)
    yaml_spec: str | None = pydantic.Field(default=None, min_length=1)

    @pydantic.model_validator(mode="after")
    def validate_spec_source(self) -> ProjectSettings:
        """Require specification sources to be mutually exclusive."""
        if (
            sum(value is not None for value in (self.python_spec, self.json_spec, self.yaml_spec))
            > 1
        ):
            raise ValueError(
                "Specify either application.python_spec, application.json_spec, "
                "or application.yaml_spec, not multiple sources"
            )
        return self


class PythonCodeSettings(project_config.CodeSettings):
    """Project code settings supported by the Python application."""

    language: typing.Literal["python"] = "python"


class TestSettings(pydantic.BaseModel):
    """Settings for project tests."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    path: str = pydantic.Field(default=project_defaults.DEFAULT_TEST_PATH, min_length=1)


class ProjectConfig(pydantic.BaseModel):
    """Project configuration with settings for individual components."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    application: ProjectSettings = pydantic.Field(default_factory=ProjectSettings)
    engine: engine_config.EngineConfig = pydantic.Field(default_factory=engine_config.EngineConfig)
    params: Params = pydantic.Field(default_factory=lambda: Params(root={}))
    paths: Paths = pydantic.Field(default_factory=lambda: Paths(root={}))
    code: PythonCodeSettings = pydantic.Field(default_factory=PythonCodeSettings)
    test: TestSettings = pydantic.Field(default_factory=TestSettings)

    @pydantic.model_validator(mode="before")
    @classmethod
    def reject_legacy_runtimes(cls, value: object) -> object:
        """Report renamed code configuration instead of ignoring it."""
        if isinstance(value, dict) and ("runtime" in value or "runtimes" in value):
            raise ValueError(
                "Use [code] instead of [runtime] or [runtimes] in project configuration"
            )
        return value
