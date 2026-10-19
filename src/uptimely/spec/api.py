"""Build and load validated spec through explicit application operations."""

from __future__ import annotations

import pathlib

from . import model, validation
from .json import codec
from .python import conversion


def load_spec(path: str | pathlib.Path) -> model.Spec:
    """Load and semantically validate a spec JSON file or directory.

    Args:
        path: A JSON document or a directory containing ``spec.json``.

    Returns:
        A validated spec document without attached derived state.

    Raises:
        OSError: The JSON document cannot be read.
        ValueError: The document or its spec declarations are invalid.
    """
    document = model.Spec.model_validate(codec.load_document(path))
    validation.validate_spec(document)
    return document


def from_python(
    datasets: conversion.Datasets | None = None,
    functions: conversion.Functions | None = None,
    name: str | None = None,
    dimensions: conversion.Dimensions | None = None,
    *,
    entities: conversion.Entities | None = None,
) -> model.Spec:
    """Convert Python declarations and semantically validate the resulting model.

    Args:
        datasets: Dataset declarations wrapped in a single entity.
        functions: Explicit catalog, or infer it from Python declarations.
        name: Optional spec name and synthetic entity identifier.
        dimensions: Global dimension declarations.
        entities: Explicit entity declarations, mutually exclusive with datasets.

    Returns:
        A validated spec document without attached derived state.

    Raises:
        TypeError: Declarations have unsupported types.
        ValueError: Declarations conflict or spec semantics are invalid.
    """
    document = conversion.to_model(
        datasets=datasets,
        functions=functions,
        name=name,
        dimensions=dimensions,
        entities=entities,
    )
    validation.validate_spec(document)
    return document
