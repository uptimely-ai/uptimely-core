"""JSON serialization and file I/O for portable execution plans."""

from __future__ import annotations

import json
import pathlib
import typing

from . import models


def to_dict(plan: models.ExecutionPlan) -> dict[str, typing.Any]:
    """Return a plan as JSON-compatible data."""
    return plan.model_dump(mode="json")


def from_dict(payload: dict[str, typing.Any]) -> models.ExecutionPlan:
    """Load a plan from a decoded JSON object."""
    if not isinstance(payload, dict):
        raise ValueError("Plan artifact must contain a JSON object")
    if "plan_version" in payload:
        models._validate_plan_version(payload["plan_version"])
    required = {
        "plan_version",
        "required_backend",
        "invocations",
        "stages",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError("Plan is missing required fields: " + ", ".join(missing))
    unexpected = sorted(payload.keys() - required)
    if unexpected:
        raise ValueError("Plan contains unknown fields: " + ", ".join(unexpected))
    invocations = payload["invocations"]
    if not isinstance(invocations, list):
        raise ValueError("Plan invocations must be a list")
    identifiers: set[str] = set()
    for invocation in invocations:
        if not isinstance(invocation, dict):
            raise ValueError("Plan invocations must be objects")
        invocation_fields = {"id", "entrypoint", "arguments", "semantics"}
        missing_invocation_fields = sorted(invocation_fields - invocation.keys())
        unexpected_invocation_fields = sorted(invocation.keys() - invocation_fields)
        if missing_invocation_fields:
            raise ValueError(
                "Plan invocation is missing fields: " + ", ".join(missing_invocation_fields)
            )
        if unexpected_invocation_fields:
            raise ValueError(
                "Plan invocation contains unknown fields: "
                + ", ".join(unexpected_invocation_fields)
            )
        invocation_id = invocation["id"]
        if not isinstance(invocation_id, str) or invocation_id in identifiers:
            raise ValueError(
                f"Plan contains an invalid or duplicate invocation ID: {invocation_id!r}"
            )
        identifiers.add(invocation_id)
        semantic_data = invocation["semantics"]
        if not isinstance(semantic_data, dict):
            raise ValueError(f"Invocation {invocation_id} semantics must be an object")
        missing_semantics = models._REQUIRED_SEMANTICS_FIELDS - semantic_data.keys()
        if missing_semantics:
            raise ValueError(
                f"Invocation {invocation_id} is missing runtime metadata: "
                + ", ".join(sorted(missing_semantics))
                + ". Recompile the project build."
            )
    return models.ExecutionPlan.model_validate(payload)


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
