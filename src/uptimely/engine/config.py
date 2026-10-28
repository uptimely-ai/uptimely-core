"""Runtime configuration for project plan execution."""

from __future__ import annotations

import math
import re
import typing

import pydantic


class EngineBackendConfig(pydantic.BaseModel):
    """Backend options used by an execution engine."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    type: str = "python_venv"
    definition: str | None = None
    dataframe: str = "polars"
    validate_lazy_frames: bool = True
    evaluation: str = "eager"
    batch_size: int | str | None = None

    @pydantic.field_validator("batch_size", mode="before")
    @classmethod
    def validate_batch_size(cls, value: object) -> object:
        """Validate the reserved batch-size setting."""
        if value is None or value == "*":
            return value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        raise ValueError("batch_size must be a positive integer, '*', or None")


class EngineConfig(pydantic.BaseModel):
    """Runtime backend configuration.

    ``evaluation`` and ``batch_size`` are reserved and do not currently affect
    execution.
    """

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    backend: EngineBackendConfig = pydantic.Field(default_factory=EngineBackendConfig)


class ParameterConfig(pydantic.RootModel[dict[str, typing.Any]]):
    """Flat map of required global parameter values loaded from project config."""

    model_config = pydantic.ConfigDict(strict=True, frozen=True)

    @pydantic.model_validator(mode="before")
    @classmethod
    def validate_values(cls, value: object) -> object:
        """Require Python-identifier keys and scalar JSON values."""
        if not isinstance(value, dict):
            raise ValueError("Parameter configuration must be a flat JSON object")
        for name, parameter in value.items():
            if not isinstance(name, str) or re.fullmatch(r"[A-Za-z_]\w*", name) is None:
                raise ValueError(f"Invalid parameter name: {name!r}")
            if parameter is not None and type(parameter) not in {str, int, float, bool}:
                raise ValueError(
                    f"Parameter {name} must be a JSON scalar (string, number, boolean, or null)"
                )
            if isinstance(parameter, float) and not math.isfinite(parameter):
                raise ValueError(f"Parameter {name} must be a finite number")
        return value
