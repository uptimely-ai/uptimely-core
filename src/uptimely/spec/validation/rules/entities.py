"""Atomic entity dimension-membership checks."""

from uptimely.spec import model as spec_model


def validate_entity_dimensions(spec: spec_model.Spec) -> None:
    """Require an entity's dimensions to be declared."""
    dimension_ids = frozenset(spec.dimensions)
    for entity_id, entity in spec.entities.items():
        dimensions = entity.dimension_id_set
        if not dimensions.issubset(dimension_ids):
            raise ValueError(
                f"Entity {entity_id} references unknown dimensions: "
                + ", ".join(sorted(dimensions - dimension_ids))
            )
