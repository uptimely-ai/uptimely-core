"""Portable execution-plan data transfer objects."""

from __future__ import annotations

import functools
import typing

import pydantic

from uptimely import entrypoint as entrypoint_module
from uptimely.spec import function_kinds as functions
from uptimely.spec import row_context as uptimely_row_context

PLAN_VERSION = 6
NonEmptyString = typing.Annotated[str, pydantic.Field(min_length=1)]


class _PlanModel(pydantic.BaseModel):
    """Strict immutable base for portable plan metadata."""

    model_config = pydantic.ConfigDict(extra="forbid", strict=True, frozen=True)

    def __replace__(self, **changes: typing.Any) -> typing.Self:
        """Return a revalidated copy with selected fields replaced."""
        values = {name: getattr(self, name) for name in type(self).model_fields}
        return type(self).model_validate({**values, **changes})


class Invocation(_PlanModel):
    """One executable function invocation in a portable plan."""

    id: NonEmptyString
    function_kind: functions.FunctionKindId
    entrypoint: NonEmptyString
    function_id: NonEmptyString
    operator_id: NonEmptyString
    dataset_id: NonEmptyString | None
    arguments: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    dependency_ids: list[NonEmptyString] = pydantic.Field(default_factory=list)
    output_features: list[NonEmptyString] = pydantic.Field(default_factory=list)
    input_features: list[NonEmptyString] = pydantic.Field(default_factory=list)
    row_context: uptimely_row_context.RowContext | None = None
    id_columns: list[NonEmptyString] = pydantic.Field(default_factory=list)
    column_types: dict[NonEmptyString, NonEmptyString] = pydantic.Field(default_factory=dict)
    argument_types: dict[NonEmptyString, NonEmptyString] = pydantic.Field(default_factory=dict)

    @pydantic.field_validator("entrypoint", "function_id", "operator_id", mode="before")
    @classmethod
    def require_declared_identifier(cls, value: object, info: pydantic.ValidationInfo) -> object:
        """Keep declaration-specific errors clear for required invocation strings."""
        if not isinstance(value, str) or not value:
            field_name = {
                "entrypoint": "an entrypoint",
                "function_id": "a function_id",
                "operator_id": "an operator_id",
            }[info.field_name]
            raise ValueError(f"Invocations must declare {field_name}")
        return value

    @pydantic.model_validator(mode="after")
    def validate_output_features(self) -> typing.Self:
        """Require distinct outputs and outputs for collapse invocations."""
        if len(set(self.output_features)) != len(self.output_features):
            raise ValueError("Invocation output_features must be unique")
        if self.function_kind == functions.COLLAPSE and not self.output_features:
            raise ValueError("Collapse must declare output_features")
        return self


class ExecutionPlan(_PlanModel):
    """Portable execution plan with validated invocation and staging contracts."""

    plan_version: typing.Literal[6]
    required_backend: NonEmptyString
    resources: dict[str, typing.Any]
    invocations: list[Invocation]
    stages: list[list[NonEmptyString]]

    @pydantic.model_validator(mode="before")
    @classmethod
    def validate_supported_version(cls, value: object) -> object:
        """Reject incompatible plan versions before parsing the versioned schema."""
        if isinstance(value, dict) and "plan_version" in value:
            _validate_plan_version(value["plan_version"])
        return value

    @pydantic.model_validator(mode="after")
    def validate_execution_order(self) -> typing.Self:
        """Validate references and ordering after invocation metadata is parsed."""
        invocation_ids = {invocation.id for invocation in self.invocations}
        if len(invocation_ids) != len(self.invocations):
            raise ValueError("Plan contains duplicate invocation ids")
        referenced = {
            dependency_id
            for invocation in self.invocations
            for dependency_id in invocation.dependency_ids
        }
        staged_invocations = [invocation_id for stage in self.stages for invocation_id in stage]
        staged = set(staged_invocations)
        unknown = (referenced | staged) - invocation_ids
        if unknown:
            raise ValueError("Plan references unknown invocation(s): " + ", ".join(sorted(unknown)))
        if len(staged_invocations) != len(self.invocations) or staged != invocation_ids:
            raise ValueError("Plan must stage every invocation exactly once")
        stage_by_invocation = {
            invocation_id: stage_number
            for stage_number, stage in enumerate(self.stages)
            for invocation_id in stage
        }
        for invocation in self.invocations:
            if any(
                stage_by_invocation[dependency_id] >= stage_by_invocation[invocation.id]
                for dependency_id in invocation.dependency_ids
            ):
                raise ValueError(
                    f"Dependencies for invocation {invocation.id} must be scheduled before it"
                )
        return self

    @functools.cached_property
    def invocations_by_id(self) -> dict[str, Invocation]:
        """Return the plan's invocation index keyed by opaque identifiers."""
        return {invocation.id: invocation for invocation in self.invocations}

    @functools.cached_property
    def execution_stages(self) -> list[list[Invocation]]:
        """Return staged invocations resolved from stage identifiers."""
        by_id = self.invocations_by_id
        return [[by_id[invocation_id] for invocation_id in stage] for stage in self.stages]

    @functools.cached_property
    def execution_invocations(self) -> list[Invocation]:
        """Return invocations in stage order, retaining the order within each stage."""
        return [invocation for stage in self.execution_stages for invocation in stage]

    @functools.cached_property
    def function_ids(self) -> set[str]:
        """Return the distinct functions used by this plan."""
        return {invocation.function_id for invocation in self.invocations}

    @functools.cached_property
    def profile_ids(self) -> set[str | None]:
        """Return the distinct profile IDs used by this plan."""
        return {invocation.dataset_id for invocation in self.invocations}

    @functools.cached_property
    def arguments(self) -> dict[str, dict[str, typing.Any]]:
        """Return bound arguments keyed by invocation ID."""
        return {invocation.id: invocation.arguments for invocation in self.invocations}

    @functools.cached_property
    def features(self) -> dict[str, list[Invocation]]:
        """Return output feature IDs mapped to all their producing invocations."""
        features: dict[str, list[Invocation]] = {}
        for invocation in self.invocations:
            for feature in invocation.output_features:
                features.setdefault(feature, []).append(invocation)
        return features

    @functools.cached_property
    def invocations_by_kind(self) -> dict[functions.FunctionKindId, list[Invocation]]:
        """Return invocations grouped by function kind in declaration order."""
        grouped: dict[functions.FunctionKindId, list[Invocation]] = {}
        for invocation in self.invocations:
            grouped.setdefault(invocation.function_kind, []).append(invocation)
        return grouped

    @functools.cached_property
    def calculated_features(self) -> set[str]:
        """Return distinct feature IDs produced by transformer invocations."""
        return {
            feature
            for kind, invocations in self.invocations_by_kind.items()
            if functions.FUNCTION_KINDS[kind].is_transformer
            for invocation in invocations
            for feature in invocation.output_features
        }

    @functools.cached_property
    def entrypoints(self) -> dict[str, None]:
        """Return distinct entrypoints in invocation declaration order."""
        return dict.fromkeys(invocation.entrypoint for invocation in self.invocations)

    @functools.cached_property
    def entrypoints_by_id(self) -> dict[str, entrypoint_module.Entrypoint]:
        """Return parsed entrypoints with their saved package provenance."""
        packages = self.resources.get("entrypoint_packages", {})
        return {
            location: entrypoint_module.Entrypoint(
                location,
                package=(
                    entrypoint_module.PackageProvenance(**packages[location])
                    if location in packages
                    else None
                ),
            )
            for location in self.entrypoints
        }

    @functools.cached_property
    def count_per_kind(self) -> dict[functions.FunctionKindId, int]:
        """Return invocation counts keyed by function kind, sorted by kind."""
        return {
            kind: len(invocations) for kind, invocations in sorted(self.invocations_by_kind.items())
        }


def _validate_plan_version(version: object) -> None:
    """Reject plan versions this runtime cannot load."""
    if type(version) is not int or version != PLAN_VERSION:
        raise ValueError(
            f"Unsupported plan version: {version!r}. Supported version is {PLAN_VERSION}."
        )
