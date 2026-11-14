"""Validated configuration for an analytics project."""

import math
import re
import typing

import pydantic

from uptimely.engine import config as engine_config


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


class ProjectConfig(pydantic.BaseModel):
    """Project configuration with settings for individual components."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    engine: engine_config.EngineConfig = pydantic.Field(default_factory=engine_config.EngineConfig)
    params: Params = pydantic.Field(default_factory=lambda: Params(root={}))
    paths: Paths = pydantic.Field(default_factory=lambda: Paths(root={}))
