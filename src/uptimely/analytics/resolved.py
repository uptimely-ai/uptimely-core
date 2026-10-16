"""Derived callable models resolved from analytics declarations."""

from __future__ import annotations

import dataclasses
import typing

import pydantic

from .model import common, dataset

if typing.TYPE_CHECKING:
    from . import model


class Call(common.StrictModel):
    """One invocation of a Function, including its dependencies."""

    function: str
    entity: str
    feature: str
    args: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    depends_on_features: list[str] = pydantic.Field(default_factory=list)

    def __str__(self) -> str:
        return self.function

    def __repr__(self) -> str:
        return self.function


class Function(common.StrictModel):
    """A vectorize function's resolved signature."""

    id: str
    type: str
    return_type: str | None = None
    info: dict[str, str | None]
    entrypoint: str | None = None
    args: list[common.Argument] = pydantic.Field(default_factory=list)
    role: str | None = None
    calculations: list[dataset.Feature] = pydantic.Field(
        default_factory=list, repr=False, exclude=True
    )
    callables: list[Call] = pydantic.Field(default_factory=list, repr=False, exclude=True)

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return self.id


@dataclasses.dataclass(frozen=True)
class PreparedAnalytics:
    """An analytics document paired with its resolved and validated analysis."""

    document: model.Analytics
    functions: list[Function]
    calls: list[Call]
