"""Build and load validated spec through explicit application operations."""

from __future__ import annotations

import pathlib
from collections import abc

from uptimely.codebase.python import entrypoint

from . import model, serialization, validation
from .python import conversion, profile
from .python import spec as python_spec


def load_python_spec(source: entrypoint.Entrypoint, *, validate: bool = True) -> model.Spec:
    """Resolve a Python declaration and convert it to a spec document.

    Args:
        source: Entrypoint addressing a Python Spec declaration.
        validate: Run semantic checks. Structural conversion always runs.

    Returns:
        A structurally parsed spec document with reusable cached views.

    Raises:
        TypeError: The entrypoint does not resolve to a Python Spec declaration.
    """
    declaration = source.resolve()
    if not isinstance(declaration, python_spec.Spec):
        raise TypeError(f"{source.module.location}:{source.function.name} must resolve to a Spec")
    return from_python(
        profiles=declaration.profiles,
        name=declaration.name,
        validate=validate,
    )


def load_spec(
    path: str | pathlib.Path, *, validate: bool = True, log_structure: bool = True
) -> model.Spec:
    """Load a spec JSON file or directory, optionally validating its semantics.

    Args:
        path: A JSON document or a directory containing ``spec.json``.
        validate: Run semantic checks. Structural parsing is always required.
        log_structure: Emit structural validation debug messages.

    Returns:
        A structurally parsed spec document with reusable cached views.

    Raises:
        OSError: The JSON document cannot be read.
        ValueError: The document or its spec declarations are invalid.
    """
    document = model.Spec.model_validate(
        serialization.load_document(path), context={"log_structure": log_structure}
    )
    if validate:
        validation.validate_spec(document)
    return document


def from_python(
    profiles: abc.Sequence[profile.Profile] | None = None,
    functions: conversion.Functions | None = None,
    name: str | None = None,
    *,
    validate: bool = True,
) -> model.Spec:
    """Convert Python declarations, optionally validating the model's semantics.

    Args:
        profiles: A sequence of Python profile declarations with globally unique IDs.
        functions: Explicit catalog, or infer it from Python declarations.
        name: Optional spec name.
        validate: Run semantic checks. Declaration and structural checks always run.

    Returns:
        A structurally parsed spec document with reusable cached views.

    Raises:
        TypeError: Declarations have unsupported types.
        ValueError: Declarations conflict or spec semantics are invalid.
    """
    document = conversion.to_model(
        profiles=profiles,
        functions=functions,
        name=name,
    )
    if validate:
        validation.validate_spec(document)
    return document
