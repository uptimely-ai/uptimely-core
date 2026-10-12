"""The canonical specification document model."""

from __future__ import annotations

import pathlib
import typing

import pydantic

from uptimely.spec import render

from .. import json_parser, json_serializer
from . import common, resolved
from . import dataset as dataset_module
from . import functions as functions_module

SUPPORTED_SPECIFICATION_VERSION = "0.1.0"


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


class Specification(common.StrictModel):
    """The complete JSON specification document."""

    path: str | None = pydantic.Field(default=None, exclude=True)
    name: str | None = None
    version: typing.Literal["0.1.0"] = SUPPORTED_SPECIFICATION_VERSION
    source: common.SpecificationSource = pydantic.Field(
        default_factory=lambda: common.SpecificationSource(name="manual", generated=False)
    )
    dimensions: dict[str, common.Dimension] = pydantic.Field(default_factory=dict)
    functions: functions_module.FunctionCatalog = pydantic.Field(
        default_factory=functions_module.FunctionCatalog
    )
    entities: dict[str, dataset_module.Entity] = pydantic.Field(default_factory=dict)
    resolved_functions: list[resolved.Function] = pydantic.Field(default_factory=list, exclude=True)
    calls: list[resolved.Call] = pydantic.Field(default_factory=list, exclude=True)

    @property
    def function_catalog(self) -> functions_module.FunctionCatalog:
        """Return the declared function catalog."""
        return self.functions

    @classmethod
    def from_json(cls, path: str | pathlib.Path) -> Specification:
        """Create a specification from a JSON file."""
        return json_parser.SpecificationParser.from_json(path)

    @classmethod
    def from_python(
        cls,
        datasets: object | None = None,
        functions: object | None = None,
        name: str | None = None,
        dimensions: dict[str, common.Dimension] | list[common.Dimension] | None = None,
        *,
        entities: object | None = None,
    ) -> Specification:
        """Create a specification from Python authoring models."""
        return json_parser.SpecificationParser.from_python(
            datasets=datasets,
            functions=functions,
            name=name,
            dimensions=dimensions,
            entities=entities,
        )

    def to_json(self, path: str | pathlib.Path) -> str:
        """Write the specification document to disk and return its path."""
        return json_serializer.SpecificationSerializer.to_json(self, path)

    def create_html(
        self,
        output_path: str | pathlib.Path | None = None,
        include_generated_at: bool = False,
        *,
        include_navigation: bool = False,
    ) -> pathlib.Path:
        """Export reference documentation for this specification as HTML.

        Args:
            output_path: Output file; defaults to ``_generated/spec/spec.html``.
            include_generated_at: Include a build timestamp; disabled for reproducibility.
            include_navigation: Link to sibling pages in a generated documentation website.

        Returns:
            The path to the rendered specification page.
        """
        return render.create_html(
            self,
            output_path,
            include_generated_at,
            include_navigation=include_navigation,
        )

    @pydantic.model_validator(mode="before")
    @classmethod
    def normalize_resource_ids(cls, value: typing.Any) -> typing.Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized["dimensions"] = _with_mapping_ids(normalized.get("dimensions", {}) or {})

        if "functions" in normalized:
            functions = dict(normalized.get("functions", {}) or {})
            for category in functions_module.FUNCTION_CATEGORIES:
                functions[category] = _normalize_nested_mappings(
                    functions.get(category, {}) or {}, ("args",)
                )
            normalized["functions"] = functions

        if "entities" not in normalized:
            return normalized
        normalized["entities"] = _with_mapping_ids(normalized.get("entities", {}) or {})
        for entity in normalized["entities"].values():
            if not isinstance(entity, dict):
                continue
            for dataset in entity.get("datasets", []) or []:
                if isinstance(dataset, dict):
                    dataset["features"] = _with_mapping_ids(dataset.get("features", {}) or {})
                    dataset["mappings"] = _with_mapping_ids(dataset.get("mappings", {}) or {})
        return normalized
