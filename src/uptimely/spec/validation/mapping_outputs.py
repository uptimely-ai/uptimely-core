"""Atomic output declaration, ownership, and producer checks."""

from __future__ import annotations

from .. import operations, selectors
from . import context as context_module


def validate_output_presence(
    item: context_module.MappingFacts, mapping_id: str
) -> context_module.ValidationResult:
    """Require a producing mapping to declare at least one output."""
    if not item.outputs:
        return ValueError(f"Mapping {mapping_id} must declare one or more features")
    return None


def validate_calculation_features(
    item: context_module.MappingFacts,
) -> context_module.ValidationResult:
    """Require calculated outputs to be declared in the target dataset."""
    unknown = sorted(set(item.outputs) - item.location.dataset.features.keys())
    if unknown:
        return ValueError(
            f"Mapping {item.location.mapping.id} references unknown feature: " + ", ".join(unknown)
        )
    return None


def validate_function_id(item: context_module.MappingFacts) -> context_module.ValidationResult:
    """Require a calculation function ID to be nonempty."""
    if item.function is not None and not item.function.id.strip():
        return ValueError("Every function must define a non-empty string id")
    return None


def validate_output_names(item: context_module.MappingFacts) -> context_module.ValidationResult:
    """Require calculated output names to be nonempty."""
    if any(not feature.strip() for feature in item.outputs):
        return ValueError("Every calculation must define a non-empty output feature name")
    return None


def validate_feature_ownership(duplicate: str | None) -> context_module.ValidationResult:
    """Require a unique owner for each non-dimension feature."""
    if duplicate is not None:
        return ValueError(f"Duplicate feature name: {duplicate}")
    return None


def validate_dimension_collision(
    item: context_module.MappingFacts, dimension_ids: frozenset[str]
) -> context_module.ValidationResult:
    """Reject calculated feature names that collide with dimensions."""
    collisions = set(item.outputs) & dimension_ids
    if item.operation == operations.VECTORIZE and collisions:
        return ValueError(
            "Calculated feature names cannot duplicate entity dimensions: "
            + ", ".join(sorted(collisions))
        )
    return None


def validate_function_reference(
    item: context_module.MappingFacts,
) -> context_module.ValidationResult:
    """Require a mapping's function to be declared."""
    if item.function is None:
        return ValueError(
            f"Dataset {item.location.dataset.id} mappings reference unknown functions: "
            f"{item.location.mapping.binding.function}"
        )
    return None


def validate_write_outputs(item: context_module.MappingFacts) -> context_module.ValidationResult:
    """Reject output features on a write mapping."""
    if item.outputs:
        return ValueError(f"Write mapping {item.location.mapping_id} cannot produce features")
    return None


def validate_output_feature(
    item: context_module.MappingFacts, feature: str
) -> context_module.ValidationResult:
    """Require an output feature to be declared in the target dataset."""
    if feature not in item.location.dataset.features:
        return ValueError(
            f"Mapping {item.location.mapping_id} references unknown feature: {feature}"
        )
    return None


def validate_unique_producer(
    item: context_module.MappingFacts, feature: str, previous: str | None
) -> context_module.ValidationResult:
    """Reject multiple producers for a non-dimension feature."""
    if feature not in item.dimensions and previous is not None:
        return ValueError(
            f"Feature {feature} is produced by multiple mappings: "
            f"{previous}, {item.location.mapping_id}"
        )
    return None


def validate_collapse_output(item: context_module.MappingFacts) -> context_module.ValidationResult:
    """Require collapse to produce a non-dimension feature."""
    if item.operation == operations.COLLAPSE and not set(item.outputs) - item.dimensions:
        return ValueError(
            f"Collapse mapping {item.location.mapping_id} must produce a non-dimension feature"
        )
    return None


def validate_current_feature_selector(
    item: context_module.MappingFacts,
) -> context_module.ValidationResult:
    """Reject ambiguous current-feature selectors on multi-output calculations."""
    if item.operation not in {operations.VECTORIZE, operations.COLLAPSE}:
        return None
    count = (
        len(set(item.outputs) - item.dimensions)
        if item.operation == operations.COLLAPSE
        else len(item.outputs)
    )
    if count > 1 and selectors.CURRENT_ID in item.feature_references:
        return ValueError(
            f"{item.operation.capitalize()} mapping {item.location.mapping_id} "
            "cannot use $features.@ when it produces multiple features"
        )
    return None
