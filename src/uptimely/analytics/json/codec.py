"""JSON serialization helpers for analytics models."""

from __future__ import annotations

import json
import pathlib
import typing

from uptimely import project
from uptimely import storage as storage_module

if typing.TYPE_CHECKING:
    from .. import model as analytics_model


def load_document(path: str | pathlib.Path) -> dict[str, typing.Any]:
    """Read one JSON document, rejecting unsupported multi-file definitions."""
    if storage_module.Storage.is_dir(path):
        path = storage_module.Storage.join(path, project.ANALYTICS_JSON_ENTRY_FILE.name)
    analytics_definition = json.loads(storage_module.Storage.read(path))
    if analytics_definition.get("includes", []) or analytics_definition.get("external_specs", []):
        raise ValueError("Analytics must be defined in a single JSON file")
    return analytics_definition


def to_document(analytics_definition: analytics_model.Analytics) -> dict[str, typing.Any]:
    """Encode document models using the analytics document's identifier rules."""
    payload = analytics_definition.model_dump(exclude_none=False)
    for entity_id, entity in analytics_definition.entities.items():
        serialized_entity = payload["entities"][entity_id]
        for index, dataset in enumerate(entity.datasets):
            serialized_entity["datasets"][index]["id"] = dataset.id
    return payload


def write_document(
    analytics_definition: analytics_model.Analytics, path: str | pathlib.Path
) -> str:
    """Write an analytics document without mutating the source model."""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(to_document(analytics_definition), indent=2), encoding="utf-8")
    return str(target)
