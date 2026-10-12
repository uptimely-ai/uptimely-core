"""Derived callable models resolved from specification declarations."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import Argument, StrictModel
from .dataset import Feature


class Call(StrictModel):
    """One invocation of a Function, including its dependencies."""

    function: str
    entity: str
    feature: str
    args: dict[str, Any] = Field(default_factory=dict)
    depends_on_features: list[str] = Field(default_factory=list)

    def __str__(self) -> str:
        return self.function

    def __repr__(self) -> str:
        return self.function


class Function(StrictModel):
    """A vectorize function's resolved signature."""

    id: str
    type: str
    return_type: str | None = None
    info: dict[str, str | None]
    entrypoint: str | None = None
    args: list[Argument] = Field(default_factory=list)
    role: str | None = None
    calculations: list[Feature] = Field(default_factory=list, repr=False, exclude=True)
    callables: list[Call] = Field(default_factory=list, repr=False, exclude=True)

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return self.id
