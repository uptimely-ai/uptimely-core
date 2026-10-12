"""Canonical dataset and entity models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from uptimely.row_context import RowContext

from .common import Binding, StrictModel


class Feature(StrictModel):
    """A dataset feature's logical metadata."""

    id: str = Field(exclude=True)
    description: str | None = None
    type: str | None = None
    unit: str | None = None
    row_context: RowContext | None = None


class FeatureMapping(StrictModel):
    """A shared function binding that produces one or more dataset features."""

    id: str = Field(exclude=True)
    binding: Binding
    features: list[str] = Field(default_factory=list)
    aggregations: dict[str, Binding] = Field(default_factory=dict)


class Sink(StrictModel):
    """A write operation declared by a dataset."""

    id: str = Field(exclude=True)
    binding: Binding


class Order(StrictModel):
    """One logical dataset ordering key, without a physical row-order guarantee."""

    dimension: str = Field(pattern=r"^\$dimensions\..+$")
    direction: Literal["asc", "desc"]


class RowScope(StrictModel):
    """The conceptual row subset represented by a dataset."""

    grain: str = ""
    filtering: str = ""
    coverage: str = ""


class Dataset(StrictModel):
    """An entry under an entity's `datasets` list."""

    id: str = Field(exclude=True)
    description: str | None = None
    row_scope: RowScope = Field(default_factory=RowScope)
    features: dict[str, Feature] = Field(default_factory=dict)
    mappings: dict[str, FeatureMapping] = Field(default_factory=dict)
    write: dict[str, Sink] = Field(default_factory=dict)
    order: list[Order] = Field(default_factory=list)

    @property
    def all_features(self) -> dict[str, Feature]:
        """Return the declared feature metadata for this dataset."""
        return self.features


class Entity(StrictModel):
    """An entry under the top-level `entities` block."""

    id: str = Field(exclude=True)
    name: str
    description: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    datasets: list[Dataset] = Field(default_factory=list)
