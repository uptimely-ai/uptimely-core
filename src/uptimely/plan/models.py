"""Portable execution-plan data transfer objects."""

from __future__ import annotations

import dataclasses
import json
import pathlib
import typing

from uptimely import row_context as uptimely_row_context


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
        if self.operation == "collapse" and not self.output_features:
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
class Plan:
    """Portable, JSON-serializable execution plan."""

    plan_version: str
    analytics_version: str | None
    required_backend: str
    resources: dict[str, typing.Any]
    callables: list[Callable]
    stages: list[list[str]]

    def to_dict(self) -> dict[str, typing.Any]:
        """Return the plan as JSON-compatible data."""
        return {
            "plan_version": self.plan_version,
            "analytics_version": self.analytics_version,
            "required_backend": self.required_backend,
            "resources": self.resources,
            "callables": [
                {
                    "id": callable.id,
                    "operation": callable.operation,
                    "entrypoint": callable.entrypoint,
                    "entity_id": callable.entity_id,
                    "dataset_id": callable.dataset_id,
                    "output": callable.output,
                    "arguments": callable.arguments,
                    "dependency_ids": callable.dependency_ids,
                    "output_features": callable.output_features,
                    "input_features": callable.input_features,
                    "row_context": (
                        callable.row_context.to_dict() if callable.row_context is not None else None
                    ),
                }
                for callable in self.callables
            ],
            "stages": self.stages,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, typing.Any]) -> Plan:
        """Load a portable plan from a decoded JSON object."""
        required = {
            "plan_version",
            "analytics_version",
            "required_backend",
            "resources",
            "callables",
            "stages",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise ValueError("Plan is missing required fields: " + ", ".join(missing))
        unexpected = sorted(payload.keys() - required)
        if unexpected:
            raise ValueError("Plan contains unknown fields: " + ", ".join(unexpected))
        callables = [Callable(**callable) for callable in payload["callables"]]
        callable_ids = {callable.id for callable in callables}
        if len(callable_ids) != len(callables):
            raise ValueError("Plan contains duplicate callable ids")
        referenced = {
            dependency_id for callable in callables for dependency_id in callable.dependency_ids
        }
        staged_callables = [callable_id for stage in payload["stages"] for callable_id in stage]
        staged = set(staged_callables)
        unknown = (referenced | staged) - callable_ids
        if unknown:
            raise ValueError("Plan references unknown callable(s): " + ", ".join(sorted(unknown)))
        if len(staged_callables) != len(callables) or staged != callable_ids:
            raise ValueError("Plan must stage every callable exactly once")
        stage_by_callable = {
            callable_id: stage_number
            for stage_number, stage in enumerate(payload["stages"])
            for callable_id in stage
        }
        for callable in callables:
            if any(
                stage_by_callable[dependency_id] >= stage_by_callable[callable.id]
                for dependency_id in callable.dependency_ids
            ):
                raise ValueError(
                    f"Dependencies for callable {callable.id} must be scheduled before it"
                )
        return cls(
            plan_version=payload["plan_version"],
            analytics_version=payload["analytics_version"],
            required_backend=payload["required_backend"],
            resources=payload["resources"],
            callables=callables,
            stages=payload["stages"],
        )


@dataclasses.dataclass(frozen=True)
class ExecutionPlan:
    """Portable execution plan with JSON round-trip support."""

    plan: Plan

    @property
    def callables(self) -> list[Callable]:
        """Return callables in their serialized order."""
        return self.plan.callables

    @property
    def execution_stages(self) -> list[list[Callable]]:
        """Return staged callables resolved from stage identifiers."""
        by_id = {callable.id: callable for callable in self.callables}
        return [[by_id[callable_id] for callable_id in stage] for stage in self.plan.stages]

    def to_dict(self) -> dict[str, typing.Any]:
        """Return the portable plan as plain JSON-compatible data."""
        return self.plan.to_dict()

    def export_json(self, path: str | pathlib.Path) -> pathlib.Path:
        """Write the portable plan to JSON."""
        target = pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target

    @classmethod
    def from_json(cls, path: str | pathlib.Path) -> ExecutionPlan:
        """Load a portable plan without loading or recompiling Analytics."""
        payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return cls(Plan.from_dict(payload))
