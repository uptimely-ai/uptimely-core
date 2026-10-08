"""Canonical traversal and resolution helpers for specification bindings."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def is_aggregation_entry(value: object) -> bool:
    """Return whether a value is shaped like one aggregate-function binding."""
    value = _as_plain(value)
    return (
        isinstance(value, dict)
        and set(value) == {"function", "args"}
        and isinstance(value.get("function"), str)
        and isinstance(value.get("args"), dict)
    )


def aggregation_entries(value: object) -> list[dict[str, Any]]:
    """Return aggregation-shaped bindings found anywhere within a value."""
    value = _as_plain(value)
    if isinstance(value, dict):
        matches = [value] if is_aggregation_entry(value) else []
        return matches + [
            match for nested in value.values() for match in aggregation_entries(nested)
        ]
    if isinstance(value, list):
        return [match for nested in value for match in aggregation_entries(nested)]
    return []


def feature_dependencies(args: dict[str, Any] | None) -> list[str]:
    """Return unique feature identifiers consumed by binding arguments."""
    if not isinstance(args, dict):
        return []

    references: list[str] = []

    def collect(value: object) -> None:
        value = _as_plain(value)
        if isinstance(value, str) and value.startswith("$features."):
            references.append(value.removeprefix("$features."))
        elif isinstance(value, dict):
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)

    collect(args)
    return list(dict.fromkeys(references))


def resolve_binding_args(
    args: dict[str, Any] | None,
    dataset_id: str,
    feature_id: str | None = None,
) -> dict[str, Any]:
    """Resolve structural references to identifiers used by the execution plan."""
    if not isinstance(args, dict):
        return args or {}

    def resolve_value(value: object) -> object:
        value = _as_plain(value)
        if isinstance(value, str):
            return resolve_structural_reference(value, dataset_id, feature_id)
        if isinstance(value, dict):
            return {key: resolve_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [resolve_value(item) for item in value]
        return value

    return {key: resolve_value(value) for key, value in args.items()}


def resolve_structural_reference(
    value: str, current_dataset_id: str, feature_id: str | None = None
) -> str:
    """Return the identifier represented by a structural binding reference."""
    if value == "$features.@":
        return feature_id if feature_id is not None else value
    for prefix in ("$features.", "$datasets.", "$dimensions.", "$fragments."):
        if value.startswith(prefix):
            identifier = value.removeprefix(prefix)
            return (
                current_dataset_id if prefix == "$datasets." and identifier == "@" else identifier
            )
    return value


def _as_plain(value: object) -> object:
    """Convert Pydantic binding models before recursively inspecting them."""
    return value.model_dump() if isinstance(value, BaseModel) else value
