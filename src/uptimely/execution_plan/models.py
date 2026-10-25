"""Portable execution-plan data transfer objects."""

from __future__ import annotations

import dataclasses
import typing

from uptimely import row_context as uptimely_row_context
from uptimely.spec import operations

PLAN_VERSION = 1


@dataclasses.dataclass(frozen=True)
class Callable:
    """One executable function invocation in a portable plan."""

    id: str
    operation: str
    entrypoint: str
    entity_id: str
    dataset_id: str | None
    output: str | None
    arguments: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    dependency_ids: list[str] = dataclasses.field(default_factory=list)
    output_features: list[str] = dataclasses.field(default_factory=list)
    input_features: list[str] = dataclasses.field(default_factory=list)
    row_context: uptimely_row_context.RowContext | None = None

    def __post_init__(self) -> None:
        """Validate callable and context contracts during construction."""
        if len(set(self.output_features)) != len(self.output_features):
            raise ValueError("Callable output_features must be unique")
        if not isinstance(self.entrypoint, str) or not self.entrypoint:
            raise ValueError("Callables must declare an entrypoint")
        if self.operation == operations.COLLAPSE and not self.output_features:
            raise ValueError("Collapse must declare output_features")
        if self.row_context is not None:
            object.__setattr__(
                self,
                "row_context",
                uptimely_row_context.RowContext.model_validate(self.row_context),
            )

    @property
    def function_id(self) -> str:
        """Return the function identifier encoded in this callable's id."""
        parts = self.id.split(":")
        return parts[2] if len(parts) > 2 and parts[0] == "callable" else self.id


@dataclasses.dataclass(frozen=True)
class ExecutionPlan:
    """Portable execution plan with validated invocation and staging contracts."""

    plan_version: int
    required_backend: str
    resources: dict[str, typing.Any]
    callables: list[Callable]
    stages: list[list[str]]

    def __post_init__(self) -> None:
        """Validate schema version, references, and execution order."""
        _validate_plan_version(self.plan_version)
        callable_ids = {callable.id for callable in self.callables}
        if len(callable_ids) != len(self.callables):
            raise ValueError("Plan contains duplicate callable ids")
        referenced = {
            dependency_id
            for callable in self.callables
            for dependency_id in callable.dependency_ids
        }
        staged_callables = [callable_id for stage in self.stages for callable_id in stage]
        staged = set(staged_callables)
        unknown = (referenced | staged) - callable_ids
        if unknown:
            raise ValueError("Plan references unknown callable(s): " + ", ".join(sorted(unknown)))
        if len(staged_callables) != len(self.callables) or staged != callable_ids:
            raise ValueError("Plan must stage every callable exactly once")
        stage_by_callable = {
            callable_id: stage_number
            for stage_number, stage in enumerate(self.stages)
            for callable_id in stage
        }
        for callable in self.callables:
            if any(
                stage_by_callable[dependency_id] >= stage_by_callable[callable.id]
                for dependency_id in callable.dependency_ids
            ):
                raise ValueError(
                    f"Dependencies for callable {callable.id} must be scheduled before it"
                )

    @property
    def execution_stages(self) -> list[list[Callable]]:
        """Return staged callables resolved from stage identifiers."""
        by_id = {callable.id: callable for callable in self.callables}
        return [[by_id[callable_id] for callable_id in stage] for stage in self.stages]


def _validate_plan_version(version: object) -> None:
    """Reject plan versions this runtime cannot load."""
    if type(version) is not int or version != PLAN_VERSION:
        raise ValueError(
            f"Unsupported plan version: {version!r}. Supported version is {PLAN_VERSION}."
        )
