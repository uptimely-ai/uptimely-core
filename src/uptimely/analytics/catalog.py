"""Shared function-catalog construction, merging, and serialization."""

from __future__ import annotations

import collections.abc

from uptimely import contracts

from . import model as analytics_model


def function_template(
    function_id: str,
    operation: contracts.FunctionOperation,
    entrypoint: str,
    args: dict[str, analytics_model.Argument],
) -> analytics_model.FunctionTemplate:
    """Create a function template for the analytics document from its declarations."""
    return analytics_model.FunctionTemplate(
        id=function_id,
        operation=operation,
        returns=contracts.OPERATION_RETURN_KINDS[operation],
        entrypoint=entrypoint,
        args=args,
    )


def merge_function_catalogs(
    catalogs: collections.abc.Iterable[analytics_model.FunctionCatalog],
) -> dict[str, analytics_model.FunctionTemplate]:
    """Merge identical definitions and reject conflicting templates."""
    functions: dict[str, analytics_model.FunctionTemplate] = {}
    for catalog in catalogs:
        for function_id, function in catalog.root.items():
            current = functions.get(function_id)
            if current is None:
                functions[function_id] = function
                continue
            if current != function:
                raise ValueError(f"Conflicting function definition for '{function_id}'")
    return functions
