"""JSON serialization helpers for specification models."""

import json
import pathlib
import typing

if typing.TYPE_CHECKING:
    from . import json_model


class SpecificationSerializer:
    """Serialize specification models to JSON documents."""

    @staticmethod
    def to_json(specification: "json_model.Specification", path: str | pathlib.Path) -> str:
        """Write the specification document to disk and return its path."""
        target = pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = specification.model_dump(exclude_none=False)
        for category in ("collapse", "expand", "conform"):
            if not payload["functions"].get(category):
                payload["functions"].pop(category, None)
        for entity_id, entity in specification.entities.items():
            serialized_entity = payload["entities"][entity_id]
            for index, dataset in enumerate(entity.datasets):
                serialized_entity["datasets"][index]["id"] = dataset.id
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        specification.path = str(target)
        return str(target)


__all__ = ["SpecificationSerializer"]
