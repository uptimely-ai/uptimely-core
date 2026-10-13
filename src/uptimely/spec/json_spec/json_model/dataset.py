"""Canonical dataset and entity models."""

from __future__ import annotations

import typing

import pydantic

from uptimely import row_context as uptimely_row_context

from . import common


class Feature(common.StrictModel):
    """A dataset feature's logical metadata."""

    id: str = pydantic.Field(exclude=True)
    description: str | None = None
    type: str | None = None
    unit: str | None = None


class MappingFeatures(common.StrictModel):
    """Explicit data prerequisites and produced features for one mapping."""

    inputs: list[str] = pydantic.Field(default_factory=list)
    outputs: list[str] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("inputs", "outputs")
    @classmethod
    def validate_references(cls, values: list[str]) -> list[str]:
        """Require distinct feature references without value selectors."""
        if any(
            not value.startswith("$features.")
            or "." in value[10:]
            or not value[10:]
            or value[10:] == "@"
            for value in values
        ):
            raise ValueError("Mapping features must use $features.<id> references")
        if len(values) != len(set(values)):
            raise ValueError("Mapping feature references must not repeat")
        return values


class Mapping(common.StrictModel):
    """A function binding with declared feature inputs, outputs, and row context."""

    id: str = pydantic.Field(exclude=True)
    binding: common.Binding
    features: MappingFeatures = pydantic.Field(default_factory=MappingFeatures)
    row_context: uptimely_row_context.RowContext | None = None

    @property
    def input_features(self) -> list[str]:
        """Return identifiers of required materialized features."""
        return [value.removeprefix("$features.") for value in self.features.inputs]

    @property
    def output_features(self) -> list[str]:
        """Return identifiers of produced features."""
        return [value.removeprefix("$features.") for value in self.features.outputs]


class Order(common.StrictModel):
    """One logical dataset ordering key, without a physical row-order guarantee."""

    dimension: str = pydantic.Field(pattern=r"^\$dimensions\..+$")
    direction: typing.Literal["asc", "desc"]


class RowScope(common.StrictModel):
    """The conceptual row subset represented by a dataset."""

    grain: str = ""
    filtering: str = ""
    coverage: str = ""


class Dataset(common.StrictModel):
    """An entry under an entity's `datasets` list."""

    id: str = pydantic.Field(exclude=True)
    description: str | None = None
    row_scope: RowScope = pydantic.Field(default_factory=RowScope)
    features: dict[str, Feature] = pydantic.Field(default_factory=dict)
    mappings: dict[str, Mapping] = pydantic.Field(default_factory=dict)
    order: list[Order] = pydantic.Field(default_factory=list)

    @property
    def all_features(self) -> dict[str, Feature]:
        """Return the declared feature metadata for this dataset."""
        return self.features


class Entity(common.StrictModel):
    """An entry under the top-level `entities` block."""

    id: str = pydantic.Field(exclude=True)
    name: str
    description: str | None = None
    dimensions: list[str] = pydantic.Field(default_factory=list)
    datasets: list[Dataset] = pydantic.Field(default_factory=list)
