"""Portable execution-plan data transfer objects."""

from __future__ import annotations

import dataclasses
import typing

from uptimely import row_context as uptimely_row_context
from uptimely.spec import functions

PLAN_VERSION = 3


@dataclasses.dataclass(frozen=True)
class Invocation:
    """One executable function invocation in a portable plan."""

    id: str
    function_kind: str
    entrypoint: str
    function_id: str
    mapping_id: str
    entity_id: str
    dataset_id: str | None
    arguments: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    dependency_ids: list[str] = dataclasses.field(default_factory=list)
    output_features: list[str] = dataclasses.field(default_factory=list)
    input_features: list[str] = dataclasses.field(default_factory=list)
    row_context: uptimely_row_context.RowContext | None = None

    def __post_init__(self) -> None:
        """Validate invocation and context contracts during construction."""
        if len(set(self.output_features)) != len(self.output_features):
            raise ValueError("Invocation output_features must be unique")
        if not isinstance(self.entrypoint, str) or not self.entrypoint:
            raise ValueError("Invocations must declare an entrypoint")
        if not self.function_id:
            raise ValueError("Invocations must declare a function_id")
        if not self.mapping_id:
            raise ValueError("Invocations must declare a mapping_id")
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
        return {invocation.id: invocation for invocation in self.invocations}

    @property
    def execution_stages(self) -> list[list[Invocation]]:
        """Return staged invocations resolved from stage identifiers."""
        by_id = self.invocations_by_id
        return [[by_id[invocation_id] for invocation_id in stage] for stage in self.stages]


def _validate_plan_version(version: object) -> None:
    """Reject plan versions this runtime cannot load."""
    if type(version) is not int or version != PLAN_VERSION:
        raise ValueError(
            f"Unsupported plan version: {version!r}. Supported version is {PLAN_VERSION}."
        )
