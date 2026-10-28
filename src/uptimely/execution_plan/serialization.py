"""JSON serialization and file I/O for portable execution plans."""

from __future__ import annotations

import json
import pathlib
import typing

from . import models


def to_dict(plan: models.ExecutionPlan) -> dict[str, typing.Any]:
    """Return a plan as JSON-compatible data."""
    return {
        "plan_version": plan.plan_version,
        "required_backend": plan.required_backend,
        "resources": plan.resources,
        "invocations": [
            {
                "id": invocation.id,
                "function_kind": invocation.function_kind,
                "entrypoint": invocation.entrypoint,
                "function_id": invocation.function_id,
                "mapping_id": invocation.mapping_id,
                "entity_id": invocation.entity_id,
                "dataset_id": invocation.dataset_id,
                "arguments": invocation.arguments,
                "dependency_ids": invocation.dependency_ids,
                "output_features": invocation.output_features,
                "input_features": invocation.input_features,
                "row_context": (
                    invocation.row_context.to_dict() if invocation.row_context is not None else None
                ),
            }
            for invocation in plan.invocations
        ],
        "stages": plan.stages,
    }


def from_dict(payload: dict[str, typing.Any]) -> models.ExecutionPlan:
    """Load a plan from a decoded JSON object."""
    if "plan_version" in payload:
        models._validate_plan_version(payload["plan_version"])
    required = {
        "plan_version",
        "required_backend",
        "resources",
        "invocations",
        "stages",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError("Plan is missing required fields: " + ", ".join(missing))
    unexpected = sorted(payload.keys() - required)
    if unexpected:
        raise ValueError("Plan contains unknown fields: " + ", ".join(unexpected))
    invocations = [models.Invocation(**invocation) for invocation in payload["invocations"]]
    return models.ExecutionPlan(
        plan_version=payload["plan_version"],
        required_backend=payload["required_backend"],
        resources=payload["resources"],
        invocations=invocations,
        stages=payload["stages"],
    )


def export_json(plan: models.ExecutionPlan, path: str | pathlib.Path) -> pathlib.Path:
    """Serialize a plan to a JSON file."""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(to_dict(plan), indent=2), encoding="utf-8")
    return target


def from_json(path: str | pathlib.Path) -> models.ExecutionPlan:
    """Deserialize a plan from a JSON file."""
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    return from_dict(payload)
