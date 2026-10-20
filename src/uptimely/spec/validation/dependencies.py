"""Atomic local dependency scope and mapping-cycle checks."""

from __future__ import annotations

from . import context as context_module


def validate_calculation_dependency(
    item: context_module.MappingFacts,
    feature: str,
    owner: context_module.DatasetLocation | None,
) -> context_module.ValidationResult:
    """Require a vectorize input owner to match the target dataset."""
    if owner is not None and owner.key != item.location.key[:2]:
        return ValueError(
            f"Calculation {item.outputs[0]} cannot read feature {feature} "
            "from another dataset; use a source resource "
            "operation to transfer features between datasets"
        )
    return None


def validate_write_dependencies(
    item: context_module.MappingFacts, foreign: tuple[str, ...]
) -> context_module.ValidationResult:
    """Require write inputs to belong to their target dataset."""
    if foreign:
        return ValueError(
            f"Write mapping {item.location.mapping.id} cannot read features from "
            "another dataset: " + ", ".join(foreign)
        )
    return None


def validate_mapping_cycle(
    cycle: context_module.MappingKey | None,
) -> context_module.ValidationResult:
    """Reject a prepared mapping dependency cycle."""
    if cycle is not None:
        return ValueError(f"Mapping feature dependency cycle: {cycle[0]}.{cycle[1]}")
    return None
