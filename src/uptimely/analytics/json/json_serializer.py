"""JSON serialization helpers for analytics models."""

import json
import pathlib
import typing

if typing.TYPE_CHECKING:
    from . import json_model


class AnalyticsSerializer:
    """Serialize analytics models to JSON documents."""

    @staticmethod
    def to_json(analytics_definition: "json_model.Analytics", path: str | pathlib.Path) -> str:
        """Write the analytics document to disk and return its path."""
        target = pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = analytics_definition.model_dump(exclude_none=False)
        for category in ("collapse", "expand", "conform"):
            if not payload["functions"].get(category):
                payload["functions"].pop(category, None)
        for entity_id, entity in analytics_definition.entities.items():
            serialized_entity = payload["entities"][entity_id]
            for index, dataset in enumerate(entity.datasets):
                serialized_entity["datasets"][index]["id"] = dataset.id
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        analytics_definition.path = str(target)
        return str(target)


__all__ = ["AnalyticsSerializer"]
