"""Canonical function-catalog models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Argument, StrictModel

FUNCTION_TYPES = ["sql_query", "python_function"]
FUNCTION_CATEGORIES = (
    "read",
    "write",
    "vectorize",
    "aggregate",
    "collapse",
    "expand",
    "conform",
)


class FunctionTemplate(StrictModel):
    """Common declaration fields for a catalog function template."""

    id: str = Field(exclude=True)
    entrypoint: str
    args: dict[str, Argument] = Field(default_factory=dict)


class ReadFunction(FunctionTemplate):
    """A function template under `functions.read`."""


class WriteFunction(FunctionTemplate):
    """A function template under `functions.write`."""


class VectorizeFunction(FunctionTemplate):
    """A function template under `functions.vectorize`."""

    description: str | None = None
    partitioning: Literal["none", "by_entity_dimensions", "custom"] | None = None


class AggregateFunction(FunctionTemplate):
    """A function template evaluated within a collapse operation."""


class CollapseFunction(FunctionTemplate):
    """A function that creates a fragment by collapsing data."""


class ExpandFunction(FunctionTemplate):
    """A function that creates a fragment by expanding data."""


class ConformFunction(FunctionTemplate):
    """A function that creates a fragment from another dataset in the same entity.

    The fragment is adapted to the target dataset's row scope.
    """


class FunctionCatalog(StrictModel):
    """The top-level `functions` block."""

    read: dict[str, ReadFunction] = Field(default_factory=dict)
    write: dict[str, WriteFunction] = Field(default_factory=dict)
    vectorize: dict[str, VectorizeFunction] = Field(default_factory=dict)
    aggregate: dict[str, AggregateFunction] = Field(default_factory=dict)
    collapse: dict[str, CollapseFunction] = Field(default_factory=dict)
    expand: dict[str, ExpandFunction] = Field(default_factory=dict)
    conform: dict[str, ConformFunction] = Field(default_factory=dict)
