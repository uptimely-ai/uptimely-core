"""Canonical function-catalog models."""

from __future__ import annotations

import typing

import pydantic

from . import common

FUNCTION_TYPES = ["sql_query", "python_function"]
FUNCTION_CATEGORIES = (
    "read",
    "write",
    "vectorize",
    "collapse",
    "expand",
    "conform",
)


class FunctionTemplate(common.StrictModel):
    """Common declaration fields for a catalog function template."""

    id: str = pydantic.Field(exclude=True)
    entrypoint: str
    args: dict[str, common.Argument] = pydantic.Field(default_factory=dict)


class ReadFunction(FunctionTemplate):
    """A function template under `functions.read`."""


class WriteFunction(FunctionTemplate):
    """A function template under `functions.write`."""


class VectorizeFunction(FunctionTemplate):
    """A function template under `functions.vectorize`."""

    description: str | None = None
    partitioning: typing.Literal["none", "by_entity_dimensions", "custom"] | None = None


class CollapseFunction(FunctionTemplate):
    """A reducer returning one expression or a mapping of output expressions."""


class ExpandFunction(FunctionTemplate):
    """A function that creates a fragment by expanding data."""


class ConformFunction(FunctionTemplate):
    """A function that creates a fragment from another dataset in the same entity.

    The fragment is adapted to the target dataset's row scope.
    """


class FunctionCatalog(common.StrictModel):
    """The top-level `functions` block."""

    read: dict[str, ReadFunction] = pydantic.Field(default_factory=dict)
    write: dict[str, WriteFunction] = pydantic.Field(default_factory=dict)
    vectorize: dict[str, VectorizeFunction] = pydantic.Field(default_factory=dict)
    collapse: dict[str, CollapseFunction] = pydantic.Field(default_factory=dict)
    expand: dict[str, ExpandFunction] = pydantic.Field(default_factory=dict)
    conform: dict[str, ConformFunction] = pydantic.Field(default_factory=dict)
