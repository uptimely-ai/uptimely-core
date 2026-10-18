"""The spec document model."""

from __future__ import annotations

import typing

import pydantic

from . import common
from . import dataset as dataset_module
from . import functions as functions_module

SUPPORTED_SPEC_VERSION = "0.2.0"


def _with_mapping_ids(value: typing.Any) -> typing.Any:
    """Add mapping keys as ids before Pydantic validates resources."""
    if not isinstance(value, dict):
        return value
    return {
        key: dict(item) | {"id": key} if isinstance(item, dict) else item
        for key, item in value.items()
    }


def _normalize_nested_mappings(value: typing.Any, fields: tuple[str, ...]) -> typing.Any:
    """Normalize ID-keyed mappings nested within each mapping resource."""
    normalized = _with_mapping_ids(value)
    if not isinstance(normalized, dict):
        return normalized
    for item in normalized.values():
        if isinstance(item, dict):
            for field in fields:
                item[field] = _with_mapping_ids(item.get(field, {}) or {})
    return normalized


class Spec(common.StrictModel):
    """The complete JSON spec document."""

    name: str | None = None
    version: typing.Literal["0.2.0"] = SUPPORTED_SPEC_VERSION
    source: common.SpecSource = pydantic.Field(
        default_factory=lambda: common.SpecSource(name="manual", generated=False)
    )
    dimensions: dict[str, common.Dimension] = pydantic.Field(default_factory=dict)
    functions: functions_module.FunctionCatalog = pydantic.Field(
        default_factory=functions_module.FunctionCatalog
    )
    entities: dict[str, dataset_module.Entity] = pydantic.Field(default_factory=dict)

    @pydantic.model_validator(mode="before")
    @classmethod
    def normalize_resource_ids(cls, value: typing.Any) -> typing.Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized["dimensions"] = _with_mapping_ids(normalized.get("dimensions", {}) or {})

        if "functions" in normalized:
            normalized["functions"] = _normalize_nested_mappings(
                normalized.get("functions", {}) or {}, ("args",)
            )

        if "entities" not in normalized:
            return normalized
        normalized["entities"] = _with_mapping_ids(normalized.get("entities", {}) or {})
        for entity in normalized["entities"].values():
            if not isinstance(entity, dict):
                continue
            entity["dimensions"] = [
                normalized["dimensions"].get(dimension, dimension)
                if isinstance(dimension, str)
                else dimension
                for dimension in entity.get("dimensions", []) or []
            ]
            datasets = [
                dict(dataset) if isinstance(dataset, dict) else dataset
                for dataset in entity.get("datasets", []) or []
            ]
            entity["datasets"] = datasets
            for dataset in datasets:
                if isinstance(dataset, dict):
                    dataset["features"] = _with_mapping_ids(dataset.get("features", {}) or {})
                    dataset["mappings"] = _with_mapping_ids(dataset.get("mappings", {}) or {})
        return normalized
