"""Canonical traversal and resolution helpers for specification bindings."""

from __future__ import annotations

import typing

import pydantic

if typing.TYPE_CHECKING:
    from . import json_model


def mapping_category(mapping: json_model.Mapping, catalog: json_model.FunctionCatalog) -> str:
    """Return the execution kind of a canonical mapping."""
    matches = [
        category
        for category in ("read", "conform", "expand", "collapse", "vectorize", "write")
        if mapping.binding.function in getattr(catalog, category)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Mapping {mapping.id} function {mapping.binding.function} must resolve "
            "to exactly one operation category"
        )
    return matches[0]


def collapse_input_dataset(
    specification: json_model.Analytics, mapping: json_model.Mapping
) -> tuple[json_model.Entity, json_model.Dataset]:
    """Infer one input dataset from a collapse's bound non-dimension features.

    Args:
        specification: Canonical specification containing feature ownership.
        mapping: Collapse binding whose inputs determine the dataset.

    Returns:
        The owning entity and the single inferred input dataset.

    Raises:
        ValueError: Inputs are missing, unknown, ambiguous, or span datasets.
    """
    inputs = [
        feature
        for feature in mapping.input_features
        if feature != "@" and feature not in specification.dimensions
    ]
    if not inputs:
        raise ValueError(f"Collapse {mapping.id} must reference a source feature")
    owners: dict[str, tuple[json_model.Entity, json_model.Dataset]] = {}
    for feature in inputs:
        matches = [
            (entity, dataset)
            for entity in specification.entities.values()
            for dataset in entity.datasets
            if feature in dataset.features
        ]
        if not matches:
            raise ValueError(f"Collapse {mapping.id} references unknown input feature: {feature}")
        if len(matches) != 1:
            raise ValueError(f"Collapse {mapping.id} has ambiguous input feature: {feature}")
        entity, dataset = matches[0]
        owners[dataset.id] = (entity, dataset)
    if len(owners) != 1:
        raise ValueError(
            f"Collapse {mapping.id} input features must belong to one dataset; "
            "use expand to combine inputs from different datasets"
        )
    return next(iter(owners.values()))


def dataset_dependencies(args: dict[str, typing.Any], current_dataset: str) -> list[str]:
    """Return datasets required as dataframe arguments, excluding identifier selectors."""
    references: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str) and value.startswith("$datasets.") and not value.endswith(".id"):
            identifier = value.removeprefix("$datasets.").removesuffix(".dataframe")
            references.append(current_dataset if identifier == "@" else identifier)
        elif isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(args)
    return list(dict.fromkeys(references))


def resolve_binding_args(
    args: dict[str, typing.Any] | None,
    dataset_id: str,
    feature_id: str | None = None,
) -> dict[str, typing.Any]:
    """Resolve structural references to identifiers used by the execution plan."""
    if not isinstance(args, dict):
        return args or {}

    def resolve_value(value: object) -> object:
        value = _as_plain(value)
        if isinstance(value, str):
            return resolve_structural_reference(value, dataset_id, feature_id)
        if isinstance(value, dict):
            return {key: resolve_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [resolve_value(item) for item in value]
        return value

    return {key: resolve_value(value) for key, value in args.items()}


def resolve_structural_reference(
    value: str, current_dataset_id: str, feature_id: str | None = None
) -> str:
    """Return the identifier represented by a structural binding reference."""
    if value in {"$features.@", "$features.@.id"}:
        return feature_id if feature_id is not None else value
    for prefix in ("$features.", "$datasets.", "$dimensions."):
        if value.startswith(prefix):
            identifier = value.removeprefix(prefix)
            if prefix == "$datasets.":
                identifier = identifier.removesuffix(".dataframe").removesuffix(".id")
            else:
                identifier = identifier.removesuffix(".id")
            return (
                current_dataset_id if prefix == "$datasets." and identifier == "@" else identifier
            )
    return value


def _as_plain(value: object) -> object:
    """Convert Pydantic binding models before recursively inspecting them."""
    return value.model_dump() if isinstance(value, pydantic.BaseModel) else value
