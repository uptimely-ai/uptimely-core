"""Normalize keyed spec resources before model validation."""

from __future__ import annotations

import typing


def normalize_spec_document(value: typing.Any) -> typing.Any:
    """Add resource IDs and expand entity dimension names in a raw spec document."""
    if not isinstance(value, dict):
        return value

    normalized = dict(value)
    normalized["dimensions"] = _with_mapping_ids(normalized.get("dimensions", {}) or {})
    if "functions" in normalized:
        normalized["functions"] = _normalize_functions(normalized["functions"] or {})
    if "entities" in normalized:
        normalized["entities"] = _normalize_entities(
            normalized["entities"] or {}, normalized["dimensions"]
        )
    return normalized


def _normalize_functions(value: typing.Any) -> typing.Any:
    """Add function and argument IDs to the keyed function catalog."""
    functions = _with_mapping_ids(value)
    if isinstance(functions, dict):
        for function in functions.values():
            if isinstance(function, dict):
                function["args"] = _with_mapping_ids(function.get("args", {}) or {})
    return functions


def _normalize_entities(value: typing.Any, dimensions: typing.Any) -> typing.Any:
    """Add entity IDs and normalize each entity's dimensions and datasets."""
    entities = _with_mapping_ids(value)
    if isinstance(entities, dict):
        for entity in entities.values():
            if isinstance(entity, dict):
                _normalize_entity(entity, dimensions)
    return entities


def _normalize_entity(entity: dict[str, typing.Any], dimensions: typing.Any) -> None:
    """Expand dimension IDs and normalize the entity's dataset registry."""
    entity["dimensions"] = [
        dimensions.get(dimension, dimension) if isinstance(dimension, str) else dimension
        for dimension in entity.get("dimensions", []) or []
    ]
    datasets = entity.get("datasets", {})
    if not isinstance(datasets, dict):
        return
    for dataset_id, dataset in datasets.items():
        if isinstance(dataset, dict) and "id" in dataset:
            raise ValueError(
                f"Dataset {dataset_id} must use its object key as identifier, not an 'id' attribute"
            )
    entity["datasets"] = _normalize_datasets(datasets)


def _normalize_datasets(value: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Add dataset IDs and normalize each dataset's feature and mapping registries."""
    datasets = _with_mapping_ids(value)
    for dataset in datasets.values():
        if isinstance(dataset, dict):
            dataset["features"] = _with_mapping_ids(dataset.get("features", {}) or {})
            dataset["mappings"] = _with_mapping_ids(dataset.get("mappings", {}) or {})
    return datasets


def _with_mapping_ids(value: typing.Any) -> typing.Any:
    """Add mapping keys as IDs before Pydantic validates resources."""
    if not isinstance(value, dict):
        return value
    return {
        key: dict(item) | {"id": key} if isinstance(item, dict) else item
        for key, item in value.items()
    }
