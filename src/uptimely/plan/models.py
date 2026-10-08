"""Portable execution-plan data transfer objects."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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

    @property
    def function_id(self) -> str:
        """Return the declared operation function identifier."""
        parts = self.id.split(":")
        return parts[2] if len(parts) > 2 and parts[0] == "callable" else self.id

    @property
    def operation_type(self) -> str:
        """Compatibility name for the operation kind."""
        return self.kind

    @property
    def feature(self) -> str | None:
        """Compatibility name for the operation output."""
        return self.output if self.kind == "vectorize" else None

    @property
    def entity(self) -> str:
        """Compatibility name for the entity identifier."""
        return self.entity_id


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
    def callables(self) -> list[Operation]:
        """Compatibility name for the portable operation collection."""
        return self.operations

    @property
    def execution_stages(self) -> list[list[Operation]]:
        """Return staged operations resolved from stage identifiers."""
        by_id = {operation.id: operation for operation in self.operations}
        return [[by_id[operation_id] for operation_id in stage] for stage in self.plan.stages]

    @property
    def execution_order(self) -> list[Operation]:
        """Return staged operations as a flat compatibility view."""
        return [operation for stage in self.execution_stages for operation in stage]

    @property
    def callable_graph(self) -> object:
        """Return a lightweight callable collection for legacy inspection APIs."""
        return _PortableCallableView(self.operations)

    @property
    def specification(self) -> object:
        """Return a version-only compatibility view for legacy constructors."""
        from uptimely.spec.json_spec.json_model import Specification

        return Specification.model_construct(version=self.plan.specification_version)

    def to_dict(self) -> dict[str, Any]:
        """Return the portable plan as plain JSON-compatible data."""
        payload = self.plan.to_dict()
        positions = {
            operation.id: position
            for position, operation in enumerate(self.execution_order, start=1)
        }
        steps = [
            self._legacy_step(position, operation)
            for position, operation in enumerate(self.execution_order, start=1)
        ]
        payload.update(
            {
                "spec_path": None,
                "spec_version": self.plan.specification_version,
                "callable_count": len(self.operations),
                "execution_stages": [
                    {
                        "stage": stage_number,
                        "steps": [
                            self._legacy_step(positions[operation.id], operation)
                            for operation in stage
                        ],
                    }
                    for stage_number, stage in enumerate(self.execution_stages, start=1)
                ],
                "execution_order": steps,
            }
        )
        return payload

    def _legacy_step(self, position: int, operation: Operation) -> dict[str, Any]:
        """Return the former report shape for existing renderers and consumers."""

        def display_value(value: object) -> object:
            if isinstance(value, dict):
                if "type" in value and "value" in value:
                    return display_value(value["value"])
                return {name: display_value(item) for name, item in value.items()}
            if isinstance(value, list):
                return [display_value(item) for item in value]
            return value

        return {
            "position": position,
            "function": operation.function_id,
            "operation_type": operation.kind,
            "callable_type": operation.kind,
            "title": operation.function_id.replace("_", " ").capitalize(),
            "entrypoint": operation.entrypoint,
            "entity": operation.entity_id,
            "dataset": operation.dataset_id,
            "feature": operation.feature,
            "depends_on_callables": [
                {
                    "function": dependency.split(":")[2]
                    if dependency.startswith("callable:")
                    else dependency
                }
                for dependency in operation.dependency_ids
            ],
            "args": {
                name: {
                    "type": {
                        "binding": value.get("type") if isinstance(value, dict) else None,
                        "function": None,
                        "engine": None,
                    },
                    "value": display_value(
                        value.get("value") if isinstance(value, dict) and "type" in value else value
                    ),
                }
                for name, value in operation.arguments.items()
            },
            "returns": {
                "type": {"engine": self.plan.resources.get("signatures", {}).get(operation.id)}
            },
        }

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

    def export_html(self, path: str | Path | None = None) -> Path:
        """Export a plan report using the existing renderer."""
        from uptimely.compile.render import _render_execution_plan

        return (
            _render_execution_plan(self, path) if path is not None else _render_execution_plan(self)
        )


@dataclass(frozen=True)
class _PortableCallableView:
    """Minimal graph-compatible view that is intentionally not serialized."""

    callables: list[Operation]
