"""Portable execution-plan data transfer objects."""

from __future__ import annotations

import dataclasses
import functools
import typing

from uptimely import entrypoint as entrypoint_module
from uptimely import row_context as uptimely_row_context
from uptimely.spec import functions

PLAN_VERSION = 5


@dataclasses.dataclass(frozen=True)
class Invocation:
    """One executable function invocation in a portable plan."""

    id: str
    function_kind: functions.FunctionKindId
    entrypoint: str
    function_id: str
    operator_id: str
    dataset_id: str | None
    arguments: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    dependency_ids: list[str] = dataclasses.field(default_factory=list)
    output_features: list[str] = dataclasses.field(default_factory=list)
    input_features: list[str] = dataclasses.field(default_factory=list)
    row_context: uptimely_row_context.RowContext | None = None
    id_columns: list[str] = dataclasses.field(default_factory=list)
    column_types: dict[str, str] = dataclasses.field(default_factory=dict)
    argument_types: dict[str, str] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate invocation and context contracts during construction."""
        if len(set(self.output_features)) != len(self.output_features):
            raise ValueError("Invocation output_features must be unique")
        if not isinstance(self.entrypoint, str) or not self.entrypoint:
            raise ValueError("Invocations must declare an entrypoint")
        if not self.function_id:
            raise ValueError("Invocations must declare a function_id")
        if not self.operator_id:
            raise ValueError("Invocations must declare an operator_id")
        if self.function_kind == functions.COLLAPSE and not self.output_features:
            raise ValueError("Collapse must declare output_features")
        if self.row_context is not None:
            object.__setattr__(
                self,
                "row_context",
                uptimely_row_context.RowContext.model_validate(self.row_context),
            )


@dataclasses.dataclass(frozen=True)
class ExecutionPlan:
    """Portable execution plan with validated invocation and staging contracts."""

    plan_version: int
    required_backend: str
    resources: dict[str, typing.Any]
    invocations: list[Invocation]
    stages: list[list[str]]

    def __post_init__(self) -> None:
        """Validate schema version, references, and execution order."""
        _validate_plan_version(self.plan_version)
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

    @property
    def invocations_by_id(self) -> dict[str, Invocation]:
        """Return the plan's invocation index keyed by opaque identifiers."""
        return self._indexes.invocations_by_id

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
    def _indexes(self) -> _PlanResourceIndex:
        indexes = _PlanResourceIndex()
        for invocation in self.invocations:
            indexes.invocations_by_id[invocation.id] = invocation
            indexes.function_ids.add(invocation.function_id)
            indexes.profile_ids.add(invocation.dataset_id)
            indexes.arguments[invocation.id] = invocation.arguments
            indexes.entrypoints.setdefault(invocation.entrypoint, None)
            indexes.invocations_by_kind.setdefault(invocation.function_kind, []).append(invocation)
            for feature in invocation.output_features:
                indexes.features.setdefault(feature, []).append(invocation)
        return indexes

    @property
    def function_ids(self) -> set[str]:
        """Return the distinct functions used by this plan."""
        return self._indexes.function_ids

    @property
    def profile_ids(self) -> set[str | None]:
        """Return the distinct profile IDs used by this plan."""
        return self._indexes.profile_ids

    @property
    def arguments(self) -> dict[str, dict[str, typing.Any]]:
        """Return bound arguments keyed by invocation ID."""
        return self._indexes.arguments

    @property
    def features(self) -> dict[str, list[Invocation]]:
        """Return output feature IDs mapped to all their producing invocations."""
        return self._indexes.features

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

    @property
    def entrypoints(self) -> dict[str, None]:
        """Return distinct entrypoints in invocation declaration order."""
        return self._indexes.entrypoints

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

    @property
    def invocations_by_kind(self) -> dict[functions.FunctionKindId, list[Invocation]]:
        """Return invocations grouped by function kind in declaration order."""
        return self._indexes.invocations_by_kind

    @functools.cached_property
    def count_per_kind(self) -> dict[functions.FunctionKindId, int]:
        """Return invocation counts keyed by function kind, sorted by kind."""
        return {
            kind: len(invocations) for kind, invocations in sorted(self.invocations_by_kind.items())
        }


@dataclasses.dataclass
class _PlanResourceIndex:
    invocations_by_id: dict[str, Invocation] = dataclasses.field(default_factory=dict)
    function_ids: set[str] = dataclasses.field(default_factory=set)
    profile_ids: set[str | None] = dataclasses.field(default_factory=set)
    arguments: dict[str, dict[str, typing.Any]] = dataclasses.field(default_factory=dict)
    features: dict[str, list[Invocation]] = dataclasses.field(default_factory=dict)
    entrypoints: dict[str, None] = dataclasses.field(default_factory=dict)
    invocations_by_kind: dict[functions.FunctionKindId, list[Invocation]] = dataclasses.field(
        default_factory=dict
    )


def _validate_plan_version(version: object) -> None:
    """Reject plan versions this runtime cannot load."""
    if type(version) is not int or version != PLAN_VERSION:
        raise ValueError(
            f"Unsupported plan version: {version!r}. Supported version is {PLAN_VERSION}."
        )
