"""Profile models for spec documents."""

from __future__ import annotations

import functools
import typing

import pydantic

from uptimely import row_context as uptimely_row_context
from uptimely.spec import selectors

from . import common


class Feature(common.StrictModel):
    """A profile feature's logical metadata."""

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
            dataset for dataset, _ in self.binding.references_by_prefix[selectors.PROFILE_PREFIX]
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


class Grain(common.StrictModel):
    """A selected resolution that contributes keys to a profile's grain."""

    dimension: str
    resolution: str


class Order(Grain):
    """One logical profile ordering key, without a physical row-order guarantee."""

    direction: typing.Literal["asc", "desc"]


class Profile(common.StrictModel):
    """An entry under the top-level ID-keyed `profiles` object."""

    id: str = pydantic.Field(exclude=True)
    name: str | None = None
    description: str | None = None
    category: str | None = None
    scope: str | None = None
    grain: list[Grain] = pydantic.Field(default_factory=list)
    features: dict[str, Feature] = pydantic.Field(default_factory=dict)
    actions: dict[str, Action] = pydantic.Field(default_factory=dict)
    order: list[Order] = pydantic.Field(default_factory=list)

    @functools.cached_property
    def dimension_ids(self) -> list[str]:
        """Return dimension identifiers in profile key order."""
        return [reference.dimension for reference in self.grain]

    @functools.cached_property
    def dimension_id_set(self) -> frozenset[str]:
        """Return dimension IDs for repeated scope checks."""
        return frozenset(self.dimension_ids)

    @pydantic.model_validator(mode="after")
    def generate_name(self) -> typing.Self:
        """Generate a display name from the profile ID when one is not supplied."""
        if self.name is None:
            self.name = common.humanize_identifier(self.id)
        return self

    @property
    def all_features(self) -> dict[str, Feature]:
        """Return the declared feature metadata for this profile."""
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
            dimension_id = key.dimension
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

    @functools.cached_property
    def grain_reference_set(self) -> frozenset[tuple[str, str]]:
        """Return selected dimension-resolution identities."""
        return frozenset((item.dimension, item.resolution) for item in self.grain)
