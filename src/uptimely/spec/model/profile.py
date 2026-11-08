"""Profile models for spec documents."""

from __future__ import annotations

import functools
import typing

import pydantic

from uptimely.spec import function_kinds as functions
from uptimely.spec import row_context as uptimely_row_context
from uptimely.spec import selectors

from . import base, binding, binding_argument, merge


class Feature(base.StrictModel):
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
            self.name = base.humanize_identifier(self.id)
        return self


class Interface(base.StrictModel):
    """Explicit data prerequisites and produced features for one operator."""

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
            raise ValueError("Operator interface must use $features.<id> references")
        if len(values) != len(set(values)):
            raise ValueError("Operator interface references must not repeat")
        return values


class Operator(base.StrictModel):
    """A computation with declared feature inputs, outputs, and optional merge."""

    id: str = pydantic.Field(exclude=True)
    interface: Interface = pydantic.Field(default_factory=Interface)
    row_context: uptimely_row_context.RowContext | None = None
    compute: binding.Binding
    merge: binding.Binding | None = None

    def bind_default_merge(self) -> None:
        """Attach the builtin merge binding when no merge is declared."""
        if self.merge is None:
            self.merge = merge.DEFAULT_BINDING.model_copy(deep=True)

    @property
    def bindings(self) -> dict[str, binding.Binding]:
        """Return compute and optional merge bindings in declaration order."""
        return {"compute": self.compute} | ({"merge": self.merge} if self.merge is not None else {})

    @property
    def input_features(self) -> list[str]:
        """Return identifiers of declared feature dependencies."""
        return self.interface.input_ids

    @property
    def output_features(self) -> list[str]:
        """Return identifiers of declared logical feature outputs."""
        return self.interface.output_ids

    @property
    def arguments(self) -> dict[str, binding_argument.BindingArgument]:
        """Return this operator's bound argument objects."""
        return self.compute.args

    def resolve_args(
        self,
        function_id: str,
        function_kind: functions.FunctionKindId,
        profile_id: str,
        grain_keys_by_profile: typing.Mapping[str, typing.Sequence[str]],
        resources: binding_argument.BindingResources,
        id_columns: typing.Sequence[str],
    ) -> dict[str, object]:
        """Resolve the matching binding's arguments in this operator's context."""
        if function_id == self.compute.function:
            selected_binding = self.compute
            kind = functions.FUNCTION_KINDS[function_kind]
            output_features = [
                feature
                for feature in self.output_features
                if kind.dimension_change != "remove" or feature not in id_columns
            ]
            feature_id = output_features[0] if len(output_features) == 1 else None
        elif self.merge is not None and function_id == self.merge.function:
            selected_binding = self.merge
            feature_id = None
        else:
            raise ValueError(f"Function {function_id} is not bound by operator {self.id}")
        return selected_binding.resolve_args(
            profile_id,
            feature_id,
            grain_keys_by_profile,
            resources,
            row_context=self.row_context,
        )

    @functools.cached_property
    def profile_references(self) -> tuple[str, ...]:
        """Return normalized profile IDs in reference order, retaining duplicates."""
        return tuple(
            profile_id
            for profile_id, _ in self.compute.references_by_prefix[selectors.PROFILE_PREFIX]
        )

    @functools.cached_property
    def feature_selectors(self) -> tuple[str, ...]:
        """Return normalized compute feature IDs in reference order, retaining duplicates."""
        return self.compute.feature_references

    @property
    def dimension_reference_paths(self) -> tuple[tuple[str, tuple[str | int, ...]], ...]:
        """Return normalized dimension IDs and relative compute argument paths."""
        return self.compute.references_by_prefix[selectors.DIMENSION_PREFIX]

    @functools.cached_property
    def dimensions_references(self) -> tuple[str, ...]:
        """Return normalized binding dimension IDs in order, retaining duplicates."""
        return tuple(dimension for dimension, _ in self.dimension_reference_paths)


class Grain(base.StrictModel):
    """A selected resolution that contributes keys to a profile's grain."""

    dimension: str
    resolution: str


class Order(Grain):
    """One logical profile ordering key, without a physical row-order guarantee."""

    direction: typing.Literal["asc", "desc"]


class Profile(base.StrictModel):
    """An entry under the top-level ID-keyed `profiles` object."""

    id: str = pydantic.Field(exclude=True)
    name: str | None = None
    description: str | None = None
    category: str | None = None
    scope: str | None = None
    grain: list[Grain] = pydantic.Field(default_factory=list)
    features: dict[str, Feature] = pydantic.Field(default_factory=dict)
    assembly: dict[str, Operator] = pydantic.Field(default_factory=dict)
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
            self.name = base.humanize_identifier(self.id)
        return self

    @property
    def all_features(self) -> dict[str, Feature]:
        """Return the declared feature metadata for this profile."""
        return self.features

    @functools.cached_property
    def arguments(self) -> dict[tuple[str, str], binding_argument.BindingArgument]:
        """Return compute arguments keyed by operator key and argument name."""
        return {
            (operator_id, name): value
            for operator_id, operator in self.assembly.items()
            for name, value in operator.arguments.items()
        }

    @functools.cached_property
    def feature_producers(self) -> dict[str, tuple[tuple[str, Operator], ...]]:
        """Return all declared output operators per feature, retaining aliases."""
        producers: dict[str, list[tuple[str, Operator]]] = {}
        for operator_id, operator in self.assembly.items():
            for feature_id in operator.output_features:
                producers.setdefault(feature_id, []).append((operator_id, operator))
        return {feature: tuple(operators) for feature, operators in producers.items()}

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
