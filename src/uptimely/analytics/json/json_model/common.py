"""Shared types for canonical analytics models."""

from __future__ import annotations

import typing

import pydantic


class StrictModel(pydantic.BaseModel):
    """Base model that rejects fields outside the analytics contract."""

    model_config = pydantic.ConfigDict(extra="forbid")


class AnalyticsSource(StrictModel):
    """Describe how an analytics document was authored or generated."""

    name: str
    generated: bool


class Dimension(StrictModel):
    """A globally defined grain under `dimensions`."""

    id: str = pydantic.Field(exclude=True)
    type: str
    description: str | None = None
    parent: str | None = None


class Argument(StrictModel):
    """A single argument entry under a function template's `args`."""

    id: str = pydantic.Field(exclude=True)
    type: str
    comment: str | None = None


BindingArgument = dict[str, typing.Any] | list[typing.Any] | str | int | float | bool | None


class Binding(StrictModel):
    """Wires an operation to a catalog function and its arguments."""

    function: str
    args: dict[str, BindingArgument] = pydantic.Field(default_factory=dict)
