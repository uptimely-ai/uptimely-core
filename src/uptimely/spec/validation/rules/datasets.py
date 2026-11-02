"""Atomic dataset identity and ordering checks."""

import logging

from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_dataset_ids(spec: spec_model.Spec) -> None:
    """Require globally unique dataset IDs."""
    logger.debug("    - checking globally unique dataset IDs")
    seen: dict[str, str] = {}
    for key, dataset in spec.dataset_items:
        previous = seen.get(dataset.id)
        if previous is not None:
            raise errors.SpecError(
                f"Duplicate dataset id {dataset.id}; already declared by entity {previous}",
                code="duplicate_dataset_id",
                path=("entities", key[0], "datasets", dataset.id),
            )
        seen[dataset.id] = key[0]


def validate_order_dimension(spec: spec_model.Spec) -> None:
    """Require an order dimension to be declared by its entity."""
    logger.debug("    - checking dataset order dimensions belong to the owning entity")
    for key, dataset in spec.dataset_items:
        for index, (dimension, _) in enumerate(dataset.order_dimensions):
            if dimension not in spec.dimensions_by_dataset[key]:
                raise errors.SpecError(
                    f"Dataset {dataset.id} order references a dimension not declared "
                    f"by entity {key[0]}: {dimension}",
                    code="invalid_order_dimension",
                    path=("entities", key[0], "datasets", dataset.id, "order", index, "dimension"),
                )


def validate_unique_order_dimension(spec: spec_model.Spec) -> None:
    """Reject a repeated order dimension."""
    logger.debug("    - checking dataset order dimensions are unique")
    for key, dataset in spec.dataset_items:
        for index, (dimension, preceding) in enumerate(dataset.order_dimensions):
            if dimension in preceding:
                raise errors.SpecError(
                    f"Dataset {dataset.id} order repeats dimension: {dimension}",
                    code="duplicate_order_dimension",
                    path=("entities", key[0], "datasets", dataset.id, "order", index, "dimension"),
                )
