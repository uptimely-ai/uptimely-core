"""Build and load validated spec through explicit application operations."""

from __future__ import annotations

import pathlib

from . import model, serialization, validation
from .python import conversion


def load_spec(
    path: str | pathlib.Path, *, validate: bool = True, log_structure: bool = True
) -> model.Spec:
    """Load a spec JSON file or directory, optionally validating its semantics.

    Args:
        path: A JSON document or a directory containing ``spec.json``.
        validate: Run semantic checks. Structural parsing is always required.
        log_structure: Emit structural validation debug messages.

    Returns:
        A structurally parsed spec document with reusable resource indexes.

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
    profiles: conversion.Profiles | None = None,
    functions: conversion.Functions | None = None,
    name: str | None = None,
    *,
    validate: bool = True,
) -> model.Spec:
    """Convert Python declarations, optionally validating the model's semantics.

    Args:
        profiles: Profile declarations keyed by their globally unique IDs.
        functions: Explicit catalog, or infer it from Python declarations.
        name: Optional spec name.
        validate: Run semantic checks. Declaration and structural checks always run.

    Returns:
        A structurally parsed spec document with reusable resource indexes.

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
