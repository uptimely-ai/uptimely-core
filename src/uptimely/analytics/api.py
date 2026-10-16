"""Build and load validated analytics through explicit application operations."""

from __future__ import annotations

import pathlib

from . import model, resolution, resolved, validation
from .json import codec
from .python import conversion


def prepare_analytics(document: model.Analytics) -> resolved.PreparedAnalytics:
    """Resolve and validate a document without adding derived state to it.

    Preparation uses declarative metadata, not executable Python signatures.
    Rebuild the result after changing the document; it is not an automatic cache.

    Args:
        document: Structurally valid canonical analytics.

    Returns:
        The document paired with its resolved functions and calls.

    Raises:
        ValueError: Analytics references, mappings, or dependencies are invalid.
    """
    functions, calls = resolution.resolve_functions(document)
    validation.validate_prepared(document, functions, calls)
    return resolved.PreparedAnalytics(document=document, functions=functions, calls=calls)


def load_analytics(path: str | pathlib.Path) -> model.Analytics:
    """Load and semantically validate an analytics JSON file or directory.

    Args:
        path: A JSON document or a directory containing ``analytics.json``.

    Returns:
        Validated canonical analytics without attached derived state.

    Raises:
        OSError: The JSON document cannot be read.
        ValueError: The document or its analytics declarations are invalid.
    """
    document = model.Analytics.model_validate(codec.load_document(path))
    prepare_analytics(document)
    return document


def from_python(
    datasets: conversion.Datasets | None = None,
    functions: conversion.Functions | None = None,
    name: str | None = None,
    dimensions: conversion.Dimensions | None = None,
    *,
    entities: conversion.Entities | None = None,
) -> model.Analytics:
    """Convert Python declarations and semantically validate the resulting model.

    Args:
        datasets: Dataset declarations wrapped in a single entity.
        functions: Explicit catalog, or infer it from Python declarations.
        name: Optional analytics name and synthetic entity identifier.
        dimensions: Global dimension declarations.
        entities: Explicit entity declarations, mutually exclusive with datasets.

    Returns:
        Validated canonical analytics without attached derived state.

    Raises:
        TypeError: Declarations have unsupported types.
        ValueError: Declarations conflict or analytics semantics are invalid.
    """
    document = conversion.to_model(
        datasets=datasets,
        functions=functions,
        name=name,
        dimensions=dimensions,
        entities=entities,
    )
    prepare_analytics(document)
    return document
