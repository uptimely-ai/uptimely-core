"""Portable execution-plan data transfer objects."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from uptimely.row_context import RowContext


@dataclass(frozen=True)
class Operation:
    """One executable operation in a portable plan."""

    id: str
    kind: str
    entrypoint: str
    entity_id: str
    dataset_id: str | None
    output: str | None
    arguments: dict[str, Any] = field(default_factory=dict)
    dependency_ids: list[str] = field(default_factory=list)
    row_context: RowContext | None = None

    def __post_init__(self) -> None:
        """Validate context metadata, including operations loaded from JSON."""
        if self.row_context is not None:
            if self.kind != "vectorize":
                raise ValueError("Only vectorize operations can declare row context")
            object.__setattr__(self, "row_context", RowContext.model_validate(self.row_context))

    @property
    def function_id(self) -> str:
        """Return the declared operation function identifier."""
        parts = self.id.split(":")
        return parts[2] if len(parts) > 2 and parts[0] == "callable" else self.id


@dataclass(frozen=True)
class Plan:
    """Portable, JSON-serializable execution plan."""

    plan_version: str
    specification_version: str | None
    required_backend: str
    resources: dict[str, Any]
    operations: list[Operation]
    stages: list[list[str]]

    def to_dict(self) -> dict[str, Any]:
        """Return the plan as JSON-compatible data."""
        return {
            "plan_version": self.plan_version,
            "specification_version": self.specification_version,
            "required_backend": self.required_backend,
            "resources": self.resources,
            "operations": [
                {
                    "id": operation.id,
                    "kind": operation.kind,
                    "entrypoint": operation.entrypoint,
                    "entity_id": operation.entity_id,
                    "dataset_id": operation.dataset_id,
                    "output": operation.output,
                    "arguments": operation.arguments,
                    "dependency_ids": operation.dependency_ids,
                    "row_context": (
                        operation.row_context.to_dict()
                        if operation.row_context is not None
                        else None
                    ),
                }
                for operation in self.operations
            ],
            "stages": self.stages,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Plan:
        """Load a portable plan from a decoded JSON object."""
        required = {
            "plan_version",
            "specification_version",
            "required_backend",
            "resources",
            "operations",
            "stages",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise ValueError("Plan is missing required fields: " + ", ".join(missing))
        unexpected = sorted(payload.keys() - required)
        if unexpected:
            raise ValueError("Plan contains unknown fields: " + ", ".join(unexpected))
        operations = [Operation(**operation) for operation in payload["operations"]]
        operation_ids = {operation.id for operation in operations}
        if len(operation_ids) != len(operations):
            raise ValueError("Plan contains duplicate operation ids")
        referenced = {
            dependency_id for operation in operations for dependency_id in operation.dependency_ids
        }
        staged_operations = [operation_id for stage in payload["stages"] for operation_id in stage]
        staged = set(staged_operations)
        unknown = (referenced | staged) - operation_ids
        if unknown:
            raise ValueError("Plan references unknown operation(s): " + ", ".join(sorted(unknown)))
        if len(staged_operations) != len(operations) or staged != operation_ids:
            raise ValueError("Plan must stage every operation exactly once")
        stage_by_operation = {
            operation_id: stage_number
            for stage_number, stage in enumerate(payload["stages"])
            for operation_id in stage
        }
        for operation in operations:
            if any(
                stage_by_operation[dependency_id] >= stage_by_operation[operation.id]
                for dependency_id in operation.dependency_ids
            ):
                raise ValueError(
                    f"Dependencies for operation {operation.id} must be scheduled before it"
                )
        return cls(
            plan_version=payload["plan_version"],
            specification_version=payload["specification_version"],
            required_backend=payload["required_backend"],
            resources=payload["resources"],
            operations=operations,
            stages=payload["stages"],
        )


@dataclass(frozen=True)
class ExecutionPlan:
    """Portable execution plan with JSON round-trip support."""

    plan: Plan

    @property
    def operations(self) -> list[Operation]:
        """Return operations in their serialized order."""
        return self.plan.operations

    @property
    def execution_stages(self) -> list[list[Operation]]:
        """Return staged operations resolved from stage identifiers."""
        by_id = {operation.id: operation for operation in self.operations}
        return [[by_id[operation_id] for operation_id in stage] for stage in self.plan.stages]

    def to_dict(self) -> dict[str, Any]:
        """Return the portable plan as plain JSON-compatible data."""
        return self.plan.to_dict()

    def export_json(self, path: str | Path) -> Path:
        """Write the portable plan to JSON."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target

    @classmethod
    def from_json(cls, path: str | Path) -> ExecutionPlan:
        """Load a portable plan without loading or recompiling its specification."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(Plan.from_dict(payload))

    def export_html(
        self, path: str | Path | None = None, *, include_navigation: bool = False
    ) -> Path:
        """Export an execution plan report as HTML.

        Args:
            path: Output file; defaults to ``_generated/compile/execution_plan.html``.
            include_navigation: Generate linked Overview, 2D graph, 3D graph,
                and Stages pages. The overview uses ``path``; callable graph and
                stage pages are written alongside it. Without navigation, the
                summary, 3D callable graph, and stages remain in a single report.

        Returns:
            The path to the rendered report.
        """
        from uptimely.compile.render import _render_execution_plan

        return (
            _render_execution_plan(self, path, include_navigation=include_navigation)
            if path is not None
            else _render_execution_plan(self, include_navigation=include_navigation)
        )
