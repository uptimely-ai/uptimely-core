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
    row_context: uptimely_row_context.RowContext | None = None


class FeatureMapping(common.StrictModel):
    """A shared function binding that produces one or more dataset features."""

    id: str = pydantic.Field(exclude=True)
    binding: common.Binding
    features: list[str] = pydantic.Field(default_factory=list)


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
    mappings: dict[str, FeatureMapping] = pydantic.Field(default_factory=dict)
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
