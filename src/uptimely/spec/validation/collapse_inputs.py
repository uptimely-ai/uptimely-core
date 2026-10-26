"""Atomic collapse source inference and source scope checks."""

from __future__ import annotations

from . import context as context_module


def validate_source_feature(item: context_module.CollapseInputs) -> context_module.ValidationResult:
    """Require collapse to reference a source feature."""
    if not item.candidates:
        return ValueError(
            f"Collapse {item.mapping.location.mapping.id} must reference a source feature"
        )
    return None


def validate_feature_owner(
    mapping_id: str, feature: str, owners: tuple[context_module.DatasetLocation, ...]
) -> context_module.ValidationResult:
    """Require a collapse source feature to have exactly one owner."""
    if not owners:
        return ValueError(f"Collapse {mapping_id} references unknown input feature: {feature}")
    if len(owners) != 1:
        return ValueError(f"Collapse {mapping_id} has ambiguous input feature: {feature}")
    return None


def validate_source_count(item: context_module.CollapseInputs) -> context_module.ValidationResult:
    """Require all collapse source features to belong to one dataset."""
    if len(item.sources) != 1:
        return ValueError(
            f"Collapse {item.mapping.location.mapping.id} input features must belong to one "
            "dataset; use expand to combine inputs from different datasets"
        )
    return None


def validate_source_target(item: context_module.CollapseInputs) -> context_module.ValidationResult:
    """Reject the target dataset as a collapse source."""
    if item.source is not None and item.source.dataset.id == item.mapping.location.dataset.id:
        return ValueError(
            f"Collapse {item.mapping.location.mapping.id} cannot use its target dataset as source"
        )
    return None


def validate_grouping_dimensions(
    item: context_module.CollapseInputs,
) -> context_module.ValidationResult:
    """Require grouping dimensions to exist in the collapse source."""
    if item.source is not None and not item.mapping.dimensions.issubset(item.source_dimensions):
        return ValueError(
            f"Collapse {item.mapping.location.mapping.id} grouping dimensions must exist in "
            f"source {item.source.dataset.id}"
        )
    return None


def validate_source_features(
    item: context_module.CollapseInputs,
) -> context_module.ValidationResult:
    """Require collapse input features to belong to its source."""
    unknown = sorted(set(item.mapping.inputs) - item.source_features)
    if item.source is not None and unknown:
        return ValueError(
            f"Collapse {item.mapping.location.mapping.id} references features outside source "
            f"{item.source.dataset.id}: " + ", ".join(unknown)
        )
    return None


def validate_source_dimensions(
    item: context_module.CollapseInputs, dimension_ids: frozenset[str]
) -> context_module.ValidationResult:
    """Require structural dimension references to belong to the source."""
    unknown = sorted(
        (set(item.mapping.dimension_references) & dimension_ids) - item.source_dimensions
    )
    if unknown:
        return ValueError(
            f"Collapse {item.mapping.location.mapping.id} references unknown source dimensions: "
            + ", ".join(unknown)
        )
    return None
