"""JSON serialization helpers for specification models."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .json_model import Specification


class SpecificationSerializer:
    """Serialize specification models to JSON documents."""

    @staticmethod
    def to_json(specification: "Specification", path: str | Path) -> str:
        """Write the specification document to disk and return its path."""
        target = Path(path)
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
