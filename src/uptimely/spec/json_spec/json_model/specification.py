"""The canonical specification document model."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import Dimension, SpecificationSource, StrictModel
from .dataset import Entity
from .functions import FUNCTION_CATEGORIES, FunctionCatalog
from .resolved import Call, Function

SUPPORTED_SPECIFICATION_VERSION = "0.1.0"


def _with_mapping_ids(value: Any) -> Any:
    """Add mapping keys as ids before Pydantic validates resources."""
    if not isinstance(value, dict):
        return value
    return {
        key: dict(item) | {"id": key} if isinstance(item, dict) else item
        for key, item in value.items()
    }


def _normalize_nested_mappings(value: Any, fields: tuple[str, ...]) -> Any:
    """Normalize ID-keyed mappings nested within each mapping resource."""
    normalized = _with_mapping_ids(value)
    if not isinstance(normalized, dict):
        return normalized
    for item in normalized.values():
        if isinstance(item, dict):
            for field in fields:
                item[field] = _with_mapping_ids(item.get(field, {}) or {})
    return normalized


class Specification(StrictModel):
    """The complete JSON specification document."""

    path: str | None = Field(default=None, exclude=True)
    name: str | None = None
    version: Literal["0.1.0"] = SUPPORTED_SPECIFICATION_VERSION
    source: SpecificationSource = Field(
        default_factory=lambda: SpecificationSource(name="manual", generated=False)
    )
    dimensions: dict[str, Dimension] = Field(default_factory=dict)
    functions: FunctionCatalog = Field(default_factory=FunctionCatalog)
    entities: dict[str, Entity] = Field(default_factory=dict)
    resolved_functions: list[Function] = Field(default_factory=list, exclude=True)
    calls: list[Call] = Field(default_factory=list, exclude=True)

    @property
    def function_catalog(self) -> FunctionCatalog:
        """Return the declared function catalog."""
        return self.functions

    @classmethod
    def from_json(cls, path: str | Path) -> Specification:
        """Create a specification from a JSON file."""
        from ..json_parser import SpecificationParser

        return SpecificationParser.from_json(path)

    @classmethod
    def from_python(
        cls,
        datasets: object | None = None,
        functions: object | None = None,
        name: str | None = None,
        dimensions: dict[str, Dimension] | list[Dimension] | None = None,
        *,
        entities: object | None = None,
    ) -> Specification:
        """Create a specification from Python authoring models."""
        from ..json_parser import SpecificationParser

        return SpecificationParser.from_python(
            datasets=datasets,
            functions=functions,
            name=name,
            dimensions=dimensions,
            entities=entities,
        )

    def to_json(self, path: str | Path) -> str:
        """Write the specification document to disk and return its path."""
        from ..json_serializer import SpecificationSerializer

        return SpecificationSerializer.to_json(self, path)

    def create_html(
        self,
        output_path: str | Path | None = None,
        include_generated_at: bool = False,
        *,
        include_navigation: bool = False,
    ) -> Path:
        """Export reference documentation for this specification as HTML.

        Args:
            output_path: Output file; defaults to ``_generated/spec/spec.html``.
            include_generated_at: Include a build timestamp; disabled for reproducibility.
            include_navigation: Link to sibling pages in a generated documentation website.

        Returns:
            The path to the rendered specification page.
        """
        from uptimely.spec.render import create_html

        return create_html(
            self,
            output_path,
            include_generated_at,
            include_navigation=include_navigation,
        )

    @model_validator(mode="before")
    @classmethod
    def normalize_resource_ids(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized["dimensions"] = _with_mapping_ids(normalized.get("dimensions", {}) or {})

        if "functions" in normalized:
            functions = dict(normalized.get("functions", {}) or {})
            for category in FUNCTION_CATEGORIES:
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
                    dataset["write"] = _with_mapping_ids(dataset.get("write", {}) or {})
        return normalized
