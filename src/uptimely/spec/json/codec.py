"""JSON serialization helpers for spec models."""

from __future__ import annotations

import json
import pathlib
import typing

from uptimely import project
from uptimely import storage as storage_module

if typing.TYPE_CHECKING:
    from .. import model as spec_model


def load_document(path: str | pathlib.Path) -> dict[str, typing.Any]:
    """Read one JSON document, rejecting unsupported multi-file definitions."""
    if storage_module.Storage.is_dir(path):
        path = storage_module.Storage.join(path, project.SPEC_JSON_ENTRY_FILE.name)
    spec_definition = json.loads(storage_module.Storage.read(path))
    if spec_definition.get("includes", []) or spec_definition.get("external_specs", []):
        raise ValueError("Spec must be defined in a single JSON file")
    return spec_definition


def to_document(spec_definition: spec_model.Spec) -> dict[str, typing.Any]:
    """Encode document models using the spec document's identifier rules."""
    return spec_definition.model_dump(exclude_none=False)


def write_document(spec_definition: spec_model.Spec, path: str | pathlib.Path) -> str:
    """Write a spec document without mutating the source model."""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(to_document(spec_definition), indent=2), encoding="utf-8")
    return str(target)
