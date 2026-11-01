"""Dataset and entity models for spec documents."""

from __future__ import annotations

import functools
import re
import typing

import pydantic

from uptimely import row_context as uptimely_row_context
from uptimely.spec import selectors

from . import common


class Feature(common.StrictModel):
    """A dataset feature's logical metadata."""

    id: str = pydantic.Field(exclude=True)
    name: str | None = None
    description: str | None = None
    type: str | None = None
    unit: str | None = None

    @pydantic.model_validator(mode="after")
    def generate_name(self) -> typing.Self:
        """Generate a display name from the feature ID when one is not supplied."""
        if self.name is None:
            self.name = common.humanize_identifier(self.id)
        return self


class ActionFeatures(common.StrictModel):
    """Explicit data prerequisites and produced features for one action."""

    inputs: list[str] = pydantic.Field(default_factory=list)
    outputs: list[str] = pydantic.Field(default_factory=list)

    @functools.cached_property
    def input_ids(self) -> list[str]:
        """Return normalized input feature IDs once."""
        return [value.removeprefix(selectors.FEATURE_PREFIX) for value in self.inputs]

    @functools.cached_property
    def output_ids(self) -> list[str]:
        """Return normalized output feature IDs once."""
        return [value.removeprefix(selectors.FEATURE_PREFIX) for value in self.outputs]

    @pydantic.field_validator("inputs", "outputs")
    @classmethod
    def validate_references(cls, values: list[str]) -> list[str]:
        """Require distinct feature references without value selectors."""
        if any(
            not value.startswith(selectors.FEATURE_PREFIX)
            or "." in value[len(selectors.FEATURE_PREFIX) :]
            or not value[len(selectors.FEATURE_PREFIX) :]
            or value[len(selectors.FEATURE_PREFIX) :] == selectors.CURRENT_ID
            for value in values
        ):
            raise ValueError("Action features must use $features.<id> references")
        if len(values) != len(set(values)):
            raise ValueError("Action feature references must not repeat")
        return values


class Action(common.StrictModel):
    """A function binding with declared feature inputs, outputs, and row context."""

    id: str
    binding: common.Binding
    features: ActionFeatures = pydantic.Field(default_factory=ActionFeatures)
    row_context: uptimely_row_context.RowContext | None = None

    @property
    def input_features(self) -> list[str]:
        """Return identifiers of declared feature dependencies."""
        return self.features.input_ids

    @property
    def output_features(self) -> list[str]:
        """Return identifiers of declared logical feature outputs."""
        return self.features.output_ids

    @property
    def arguments(self) -> dict[str, common.BindingArgument]:
        """Return this action's supplied argument values."""
        return self.binding.args

    @functools.cached_property
    def dataset_references(self) -> tuple[str, ...]:
        """Return normalized binding dataset IDs in reference order, retaining duplicates."""
        return tuple(
            dataset for dataset, _ in self.binding.references_by_prefix[selectors.DATASET_PREFIX]
        )

    @functools.cached_property
    def feature_selectors(self) -> tuple[str, ...]:
        """Return normalized binding feature IDs in reference order, retaining duplicates."""
        return tuple(
            feature for feature, _ in self.binding.references_by_prefix[selectors.FEATURE_PREFIX]
        )

    @property
    def dimension_reference_paths(self) -> tuple[tuple[str, tuple[str | int, ...]], ...]:
        """Return normalized dimension IDs and relative binding argument paths."""
        return self.binding.references_by_prefix[selectors.DIMENSION_PREFIX]

    @functools.cached_property
    def dimensions_references(self) -> tuple[str, ...]:
        """Return normalized binding dimension IDs in order, retaining duplicates."""
        return tuple(dimension for dimension, _ in self.dimension_reference_paths)


class Order(common.StrictModel):
    """One logical dataset ordering key, without a physical row-order guarantee."""

    dimension: str = pydantic.Field(pattern=rf"^{re.escape(selectors.DIMENSION_PREFIX)}.+$")
    direction: typing.Literal["asc", "desc"]


class RowScope(common.StrictModel):
    """The conceptual row subset represented by a dataset."""

    grain: str = ""
    filtering: str = ""
    coverage: str = ""


class Dataset(common.StrictModel):
    """An entry under an entity's ID-keyed `datasets` object."""

    id: str = pydantic.Field(exclude=True)
    name: str | None = None
    description: str | None = None
    row_scope: RowScope = pydantic.Field(default_factory=RowScope)
    features: dict[str, Feature] = pydantic.Field(default_factory=dict)
    actions: dict[str, Action] = pydantic.Field(default_factory=dict)
    order: list[Order] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def generate_name(self) -> typing.Self:
        """Generate a display name from the dataset ID when one is not supplied."""
        if self.name is None:
            self.name = common.humanize_identifier(self.id)
        return self

    @property
    def all_features(self) -> dict[str, Feature]:
        """Return the declared feature metadata for this dataset."""
        return self.features

    @functools.cached_property
    def arguments(self) -> dict[tuple[str, str], common.BindingArgument]:
        """Return bound arguments keyed by action dictionary key and argument name."""
        return {
            (action_id, name): value
            for action_id, action in self.actions.items()
            for name, value in action.arguments.items()
        }

    @functools.cached_property
    def feature_producers(self) -> dict[str, tuple[tuple[str, Action], ...]]:
        """Return all declared output actions per feature, retaining action aliases."""
        producers: dict[str, list[tuple[str, Action]]] = {}
        for action_id, action in self.actions.items():
            for feature_id in action.output_features:
                producers.setdefault(feature_id, []).append((action_id, action))
        return {feature: tuple(actions) for feature, actions in producers.items()}

    @functools.cached_property
    def order_dimensions(self) -> tuple[tuple[str, frozenset[str]], ...]:
        """Return normalized order IDs with preceding keys, retaining duplicates."""
        preceding: set[str] = set()
        items = []
        for key in self.order:
            dimension_id = key.dimension.removeprefix(selectors.DIMENSION_PREFIX)
            items.append((dimension_id, frozenset(preceding)))
            preceding.add(dimension_id)
        return tuple(items)

    @functools.cached_property
    def order_references(self) -> frozenset[str]:
        """Return order dimension references for membership checks."""
        return frozenset(
            f"{selectors.DIMENSION_PREFIX}{dimension_id}"
            for dimension_id, _ in self.order_dimensions
        )


class Entity(common.StrictModel):
    """An entry under the top-level `entities` block."""

    id: str = pydantic.Field(exclude=True)
    name: str
    description: str | None = None
    dimensions: list[common.Dimension] = pydantic.Field(default_factory=list)
    datasets: dict[str, Dataset] = pydantic.Field(default_factory=dict)

    @functools.cached_property
    def dimension_ids(self) -> list[str]:
        """Return the identifiers of dimensions declared by this entity."""
        return [dimension.id for dimension in self.dimensions]

    @functools.cached_property
    def dimension_id_set(self) -> frozenset[str]:
        """Return dimension IDs for repeated scope checks."""
        return frozenset(self.dimension_ids)

    @functools.cached_property
    def features(self) -> dict[str, Feature]:
        """Return feature metadata from all owned datasets, keyed by feature ID."""
        return {
            feature_id: feature
            for dataset in self.datasets.values()
            for feature_id, feature in dataset.features.items()
        }

    @functools.cached_property
    def actions(self) -> dict[tuple[str, str], Action]:
        """Return owned actions keyed by dataset ID and action dictionary key."""
        return {
            (dataset.id, action_id): action
            for dataset in self.datasets.values()
            for action_id, action in dataset.actions.items()
        }

    @functools.cached_property
    def arguments(self) -> dict[tuple[str, str, str], common.BindingArgument]:
        """Return bound arguments keyed by dataset ID, action key, and argument name."""
        return {
            (dataset.id, action_id, name): value
            for dataset in self.datasets.values()
            for (action_id, name), value in dataset.arguments.items()
        }

    @pydantic.field_serializer("dimensions")
    def serialize_dimensions(self, dimensions: list[common.Dimension]) -> list[str]:
        """Serialize entity dimensions as references in the spec document."""
        return [dimension.id for dimension in dimensions]
