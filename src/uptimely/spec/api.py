"""Build and load validated spec through explicit application operations."""

from __future__ import annotations

import pathlib

from . import model, resolution, resolved, validation
from .json import codec
from .python import conversion


def prepare_spec(document: model.Spec) -> resolved.PreparedSpec:
    """Resolve and validate a document without adding derived state to it.

    Preparation uses declarative metadata, not executable Python signatures.
    Rebuild the result after changing the document; it is not an automatic cache.

    Args:
        document: A spec document that conforms to the document model.

    Returns:
        The document paired with its resolved functions and calls.

    Raises:
        ValueError: Spec references, mappings, or dependencies are invalid.
    """
    functions, calls = resolution.resolve_functions(document)
    validation.validate_prepared(document, functions, calls)
    return resolved.PreparedSpec(document=document, functions=functions, calls=calls)


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
    prepare_spec(document)
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
    prepare_spec(document)
    return document
