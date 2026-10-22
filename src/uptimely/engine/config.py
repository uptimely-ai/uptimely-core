"""Runtime configuration for project plan execution."""

from __future__ import annotations

import typing

import pydantic


class EngineBackendConfig(pydantic.BaseModel):
    """Backend options used by an execution engine."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    type: str = "python_venv"
    definition: str | None = None
    dataframe: str = "polars"
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
    """Runtime backend configuration and environment-specific bindings.

    ``evaluation`` and ``batch_size`` are reserved and do not currently affect
    execution.
    """

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    backend: EngineBackendConfig = pydantic.Field(default_factory=EngineBackendConfig)
    bind: dict[str, dict[str, dict[str, typing.Any]]] = pydantic.Field(default_factory=dict)
