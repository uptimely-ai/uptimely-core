"""Document calculation/write scope and mapping dependency cycles."""

from __future__ import annotations

from . import context as context_module


def validate_mapping_cycles(
    dependencies_by_mapping: dict[tuple[str, str], set[tuple[str, str]]],
) -> None:
    """Reject cycles in the graph of mappings that produce required features."""
    visiting: set[tuple[str, str]] = set()
    visited: set[tuple[str, str]] = set()

    def visit_mapping(key: tuple[str, str]) -> None:
        _validate_mapping_dependency_not_active(key, visiting)
        if key in visited:
            return
        visiting.add(key)
        for dependency in dependencies_by_mapping[key]:
            visit_mapping(dependency)
        visiting.remove(key)
        visited.add(key)

    for mapping_key in dependencies_by_mapping:
        visit_mapping(mapping_key)


def validate_calculation_dependencies(
    validation_context: context_module.SpecValidationContext,
) -> None:
    """Validate that vectorize mappings only read from their owning dataset."""
    for location in validation_context.iter_mappings():
        mapping = location.mapping
        function = validation_context.model.functions.get(mapping.binding.function)
        if function is None or function.operation != "vectorize":
            continue
        for dependency in mapping.input_features:
            owner = validation_context.first_feature_owner(dependency)
            dependency_owner = (owner.entity_id, owner.dataset.id) if owner is not None else None
            _validate_calculation_dependency(
                mapping.output_features[0],
                dependency,
                (location.entity_id, location.dataset.id),
                dependency_owner,
            )


def validate_write_dependencies(
    validation_context: context_module.SpecValidationContext,
) -> None:
    """Validate that write mappings use features from their target dataset."""
    for location in validation_context.iter_mappings():
        mapping = location.mapping
        function = validation_context.model.functions.get(mapping.binding.function)
        if function is None or function.operation != "write":
            continue
        dataset_key = (location.entity_id, location.dataset.id)
        foreign_features = sorted(
            feature_id
            for feature_id in set(mapping.input_features) - set(location.entity.dimension_ids)
            if (
                (owner := validation_context.first_feature_owner(feature_id)) is None
                or (owner.entity_id, owner.dataset.id) != dataset_key
            )
        )
        _validate_write_dependencies(mapping.id, foreign_features)


def _validate_mapping_dependency_not_active(
    mapping_key: tuple[str, str], active_mappings: set[tuple[str, str]]
) -> None:
    """Reject graph traversal when the mapping is already on the active path."""
    if mapping_key in active_mappings:
        raise ValueError(f"Mapping feature dependency cycle: {mapping_key[0]}.{mapping_key[1]}")


def _validate_calculation_dependency(
    feature: str,
    dependency: str,
    owner_id: tuple[str, str],
    dependency_owner_id: tuple[str, str] | None,
) -> None:
    """Keep a calculation from reading another dataset's feature."""
    if dependency_owner_id is not None and dependency_owner_id != owner_id:
        raise ValueError(
            f"Calculation {feature} cannot read feature {dependency} "
            "from another dataset; use a source resource "
            "operation to transfer features between datasets"
        )


def _validate_write_dependencies(mapping_id: str, foreign_features: list[str]) -> None:
    """Keep a write mapping from consuming a feature owned by another dataset."""
    if foreign_features:
        raise ValueError(
            f"Write mapping {mapping_id} cannot read features from "
            "another dataset: " + ", ".join(foreign_features)
        )
