"""Shared function-catalog construction, merging, and serialization."""

from __future__ import annotations

import collections.abc

from . import functions
from . import model as spec_model


def function_template(
    function_id: str,
    kind: functions.FunctionKind,
    entrypoint: str,
    args: dict[str, spec_model.Argument],
    *,
    validate_signature: bool = True,
    description: str | None = None,
) -> spec_model.FunctionTemplate:
    """Create a function template for the spec document from its declarations."""
    return spec_model.FunctionTemplate(
        id=function_id,
        kind=kind,
        returns=functions.KIND_RETURN_KINDS[kind],
        entrypoint=entrypoint,
        validate_signature=validate_signature,
        args=args,
        description=description,
    )


def merge_function_catalogs(
    catalogs: collections.abc.Iterable[spec_model.FunctionCatalog],
) -> dict[str, spec_model.FunctionTemplate]:
    """Merge identical definitions and reject conflicting templates."""
    functions: dict[str, spec_model.FunctionTemplate] = {}
    for catalog in catalogs:
        for function_id, function in catalog.root.items():
            current = functions.get(function_id)
            if current is None:
                functions[function_id] = function
                continue
            if current != function:
                raise ValueError(f"Conflicting function definition for '{function_id}'")
    return functions
