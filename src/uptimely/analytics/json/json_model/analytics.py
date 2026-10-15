"""The canonical analytics document model."""

from __future__ import annotations

import pathlib
import typing

import pydantic

from .. import json_parser, json_serializer
from . import common, resolved
from . import dataset as dataset_module
from . import functions as functions_module

SUPPORTED_ANALYTICS_VERSION = "0.2.0"


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


class Analytics(common.StrictModel):
    """The complete JSON analytics document."""

    path: str | None = pydantic.Field(default=None, exclude=True)
    name: str | None = None
    version: typing.Literal["0.2.0"] = SUPPORTED_ANALYTICS_VERSION
    source: common.AnalyticsSource = pydantic.Field(
        default_factory=lambda: common.AnalyticsSource(name="manual", generated=False)
    )
    dimensions: dict[str, common.Dimension] = pydantic.Field(default_factory=dict)
    functions: functions_module.FunctionCatalog = pydantic.Field(
        default_factory=functions_module.FunctionCatalog
    )
    entities: dict[str, dataset_module.Entity] = pydantic.Field(default_factory=dict)
    resolved_functions: list[resolved.Function] = pydantic.Field(default_factory=list, exclude=True)
    calls: list[resolved.Call] = pydantic.Field(default_factory=list, exclude=True)

    def __init__(self, *, json: str | pathlib.Path | None = None, **data: typing.Any) -> None:
        """Create an analytics model, optionally loading its definition from JSON.

        Args:
            json: Path to a JSON analytics file or directory containing ``analytics.json``.
            **data: Analytics model fields. Cannot be combined with ``json``.

        Raises:
            ValueError: If ``json`` is combined with model fields or the document is invalid.
            OSError: If the JSON file cannot be read.
        """
        if json is not None:
            if data:
                raise ValueError("Provide either json or analytics fields, not both")
            parsed = json_parser.AnalyticsParser.from_json(json)
            data = parsed.__dict__.copy()
            data["path"] = parsed.path
        super().__init__(**data)

    @property
    def function_catalog(self) -> functions_module.FunctionCatalog:
        """Return the declared function catalog."""
        return self.functions

    @classmethod
    def from_python(
        cls,
        datasets: object | None = None,
        functions: object | None = None,
        name: str | None = None,
        dimensions: dict[str, common.Dimension] | list[common.Dimension] | None = None,
        *,
        entities: object | None = None,
    ) -> Analytics:
        """Create analytics from Python authoring models."""
        return json_parser.AnalyticsParser.from_python(
            datasets=datasets,
            functions=functions,
            name=name,
            dimensions=dimensions,
            entities=entities,
        )

    def to_json(self, path: str | pathlib.Path) -> str:
        """Write the analytics document to disk and return its path."""
        return json_serializer.AnalyticsSerializer.to_json(self, path)

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
            for dataset in entity.get("datasets", []) or []:
                if isinstance(dataset, dict):
                    dataset["features"] = _with_mapping_ids(dataset.get("features", {}) or {})
                    dataset["mappings"] = _with_mapping_ids(dataset.get("mappings", {}) or {})
        return normalized
