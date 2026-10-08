"""Pydantic models for the OpenAnalytics specification."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from pathlib import Path

FUNCTION_TYPES = ["sql_query", "python_function"]
FUNCTION_CATEGORIES = (
    "read",
    "write",
    "vectorize",
    "aggregate",
    "collapse",
    "expand",
    "conform",
)
SUPPORTED_SPECIFICATION_VERSION = "0.1.0"


class StrictModel(BaseModel):
    """Base model that rejects fields outside the specification contract."""

    model_config = ConfigDict(extra="forbid")


class Dimension(StrictModel):
    """A globally defined grain under `dimensions`."""

    id: str = Field(exclude=True)
    type: str
    description: str | None = None
    parent: str | None = None


class Argument(StrictModel):
    """A single argument entry under a function template's `args`."""

    id: str = Field(exclude=True)
    type: str
    comment: str | None = None


class FunctionTemplate(StrictModel):
    """Common declaration fields for a catalog function template."""

    id: str = Field(exclude=True)
    entrypoint: str
    args: dict[str, Argument] = Field(default_factory=dict)


class ReadFunction(FunctionTemplate):
    """A function template under `functions.read`."""


class WriteFunction(FunctionTemplate):
    """A function template under `functions.write`."""


class VectorizeFunction(FunctionTemplate):
    """A function template under `functions.vectorize`."""

    description: str | None = None
    input_scope: Literal["row", "dataset", "window", "group"] | None = None
    partitioning: Literal["none", "by_entity_dimensions", "custom"] | None = None


class AggregateFunction(FunctionTemplate):
    """A function template evaluated within a collapse operation."""


class CollapseFunction(FunctionTemplate):
    """A function that creates a fragment by collapsing data."""


class ExpandFunction(FunctionTemplate):
    """A function that creates a fragment by expanding data."""


class ConformFunction(FunctionTemplate):
    """A function that creates a fragment from another dataset in the same entity.

    The fragment is adapted to the target dataset's row scope.
    """


class FunctionCatalog(StrictModel):
    """The top-level `functions` block."""

    read: dict[str, ReadFunction] = Field(default_factory=dict)
    write: dict[str, WriteFunction] = Field(default_factory=dict)
    vectorize: dict[str, VectorizeFunction] = Field(default_factory=dict)
    aggregate: dict[str, AggregateFunction] = Field(default_factory=dict)
    collapse: dict[str, CollapseFunction] = Field(default_factory=dict)
    expand: dict[str, ExpandFunction] = Field(default_factory=dict)
    conform: dict[str, ConformFunction] = Field(default_factory=dict)


BindingArgument = dict[str, Any] | list[Any] | str | int | float | bool | None


class Binding(StrictModel):
    """Wires an entity feature to a vectorize function and its arguments."""

    function: str
    args: dict[str, BindingArgument] = Field(default_factory=dict)


class Call(StrictModel):
    """One invocation of a Function, including its dependencies."""

    function: str
    entity: str
    feature: str
    args: dict[str, Any] = Field(default_factory=dict)
    depends_on_features: list[str] = Field(default_factory=list)

    def __str__(self) -> str:
        return self.function

    def __repr__(self) -> str:
        return self.function


class Input(StrictModel):
    """A source-provided column that contributes to an entity's features."""

    id: str = Field(exclude=True)
    description: str | None = None
    type: str | None = None
    unit: str | None = None


class Calculation(StrictModel):
    """A vectorized feature declaration under a dataset's features map."""

    id: str = Field(exclude=True)
    description: str | None = None
    unit: str | None = None
    binding: Binding | None = None
    callable: Call | None = Field(default=None, repr=False, exclude=True)


class FragmentOperation(StrictModel):
    """An operation that returns a dataframe fragment and its feature columns."""

    id: str = Field(exclude=True)
    binding: Binding
    features: dict[str, Input] = Field(default_factory=dict)


class Source(FragmentOperation):
    """A read operation that returns a dataframe fragment."""


class Transform(FragmentOperation):
    """A conform, expand, or collapse operation returning a fragment."""


class Sink(StrictModel):
    """A write operation declared by a dataset."""

    id: str = Field(exclude=True)
    binding: Binding


class Dataset(StrictModel):
    """An entry under an entity's `datasets` list."""

    id: str = Field(exclude=True)
    description: str | None = None
    row_scope: RowScope = Field(default_factory=lambda: RowScope())
    read: dict[str, Source] = Field(default_factory=dict)
    conform: dict[str, Transform] = Field(default_factory=dict)
    expand: dict[str, Transform] = Field(default_factory=dict)
    collapse: dict[str, Transform] = Field(default_factory=dict)
    vectorize: dict[str, Calculation] = Field(default_factory=dict)
    write: dict[str, Sink] = Field(default_factory=dict)

    @property
    def fragment_operations(self) -> list[tuple[str, FragmentOperation]]:
        """Return fragment operations paired with their operation category."""
        return [
            (operation_type, fragment)
            for operation_type in ("read", "conform", "expand", "collapse")
            for fragment in getattr(self, operation_type).values()
        ]

    @property
    def all_features(self) -> dict[str, Input | Calculation]:
        """Return fragment-provided and calculated features declared by this dataset."""
        fragment_features: dict[str, Input] = {}
        for _, fragment in self.fragment_operations:
            fragment_features.update(fragment.features)
        return {**fragment_features, **self.vectorize}


class RowScope(StrictModel):
    """The conceptual row subset shared by all dataset fragments."""

    grain: str = ""
    filtering: str = ""
    coverage: str = ""


class Entity(StrictModel):
    """An entry under the top-level `entities` block."""

    id: str = Field(exclude=True)
    name: str
    description: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    datasets: list[Dataset] = Field(default_factory=list)


class Function(StrictModel):
    """A vectorize function's resolved signature."""

    id: str
    type: str
    return_type: str | None = None
    info: dict[str, str | None]
    entrypoint: str | None = None
    args: list[Argument] = Field(default_factory=list)
    role: str | None = None
    calculations: list[Calculation] = Field(default_factory=list, repr=False, exclude=True)
    callables: list[Call] = Field(default_factory=list, repr=False, exclude=True)

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return self.id


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
    version: Literal["0.1.0"] = SUPPORTED_SPECIFICATION_VERSION
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
        from .json_parser import SpecificationParser

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
        from .json_parser import SpecificationParser

        return SpecificationParser.from_python(
            datasets=datasets,
            functions=functions,
            name=name,
            dimensions=dimensions,
            entities=entities,
        )

    def to_json(self, path: str | Path) -> str:
        """Write the specification document to disk and return its path."""
        from .json_serializer import SpecificationSerializer

        return SpecificationSerializer.to_json(self, path)

    @model_validator(mode="before")
    @classmethod
    def normalize_resource_ids(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for resource in ("dimensions",):
            normalized[resource] = _with_mapping_ids(normalized.get(resource, {}) or {})

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
                    if "row_scope" not in dataset:
                        dataset.pop("ordering", None)
                        dataset["row_scope"] = {
                            "grain": dataset.pop("grain", "") or "",
                            "filtering": dataset.pop("filtering", "") or "",
                            "coverage": dataset.pop("coverage", "") or "",
                        }
                    elif isinstance(dataset["row_scope"], dict):
                        dataset["row_scope"] = dict(dataset["row_scope"])
                        dataset["row_scope"].pop("ordering", None)
                    for operation_type in ("read", "conform", "expand", "collapse"):
                        dataset[operation_type] = _with_mapping_ids(
                            dataset.get(operation_type, {}) or {}
                        )
                        for fragment in dataset[operation_type].values():
                            if isinstance(fragment, dict):
                                fragment["features"] = _with_mapping_ids(
                                    fragment.get("features", {}) or {}
                                )
                    dataset["vectorize"] = _with_mapping_ids(
                        dataset.get("vectorize", dataset.get("vectorize", {})) or {}
                    )
                    dataset["write"] = _with_mapping_ids(dataset.get("write", {}) or {})
        return normalized
