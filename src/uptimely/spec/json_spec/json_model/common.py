"""Shared types for canonical specification models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base model that rejects fields outside the specification contract."""

    model_config = ConfigDict(extra="forbid")


class SpecificationSource(StrictModel):
    """Describe how a specification document was authored or generated."""

    name: str
    generated: bool


class Dimension(StrictModel):
    """A globally defined grain under `dimensions`."""

    id: str = Field(exclude=True)
    type: str
    description: str | None = None
    parent: str | None = None


class Argument(StrictModel):
    """A single argument entry under a function template's `args`."""

    id: str = Field(exclude=True)
    type: str
    comment: str | None = None


BindingArgument = dict[str, Any] | list[Any] | str | int | float | bool | None


class Binding(StrictModel):
    """Wires an operation to a catalog function and its arguments."""

    function: str
    args: dict[str, BindingArgument] = Field(default_factory=dict)
