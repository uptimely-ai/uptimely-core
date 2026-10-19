"""Mapping references, collapse source scope, and row-context validation."""

from __future__ import annotations

from uptimely import contracts
from uptimely.spec import model as spec_model
from uptimely.spec import references as bindings

from . import context as context_module


def validate_collapse(
    validation_context: context_module.SpecValidationContext,
) -> context_module.CollapseSources:
    """Validate source scope and return sources for later validation phases."""
    model = validation_context.model
    feature_owners = {
        feature_id: [(owner.entity, owner.dataset) for owner in owners]
        for feature_id, owners in validation_context.feature_owners.items()
    }
    sources: context_module.CollapseSources = {}
    for location in validation_context.iter_mappings():
        mapping = location.mapping
        if model.functions[mapping.binding.function].operation != "collapse":
            continue
        source_entity, source_dataset = bindings.collapse_input_dataset(
            model, mapping, feature_owners=feature_owners
        )
        source = context_module.CollapseSource(source_entity, source_dataset)
        _validate_collapse_source(location, source)
        sources[location.key] = source
    return sources


def _validate_collapse_source(
    location: context_module.MappingLocation, source: context_module.CollapseSource
) -> None:
    """Require a collapse's inputs and grouping to stay within its source scope."""
    mapping = location.mapping
    _validate_collapse_source_differs_target(mapping.id, source.dataset.id, location.dataset.id)
    _validate_collapse_grouping_dimensions(
        mapping.id,
        location.entity.dimension_ids,
        source.entity.dimension_ids,
        source.dataset.id,
    )
    source_features = set(source.dataset.features) | set(source.entity.dimension_ids)
    _validate_collapse_source_feature_membership(
        mapping.id, mapping.input_features, source_features, source.dataset.id
    )
    referenced_dimensions = set(
        bindings.structural_references(mapping.binding.args, contracts.DIMENSION_PREFIX)
    )
    _validate_collapse_source_dimensions(
        mapping.id, referenced_dimensions, source.entity.dimension_ids
    )


def _validate_input_references(
    location: context_module.MappingLocation,
    operation: str,
    feature_producers: dict[str, tuple[str, str]],
    feature_names: set[str],
    dataset_ids: set[str],
    dimension_ids: set[str],
) -> set[tuple[str, str]]:
    """Validate one mapping's explicit and structural references."""
    mapping = location.mapping
    dependencies: set[tuple[str, str]] = set()
    local_features = set(location.dataset.features) | set(location.entity.dimension_ids)
    for feature_id in mapping.input_features:
        _validate_feature_reference(feature_id, feature_names, mapping.id)
        _validate_dataset_local_inputs(operation, mapping.id, feature_id, local_features)
        producer = feature_producers.get(feature_id)
        if producer is not None:
            dependencies.add(producer)

    for feature_id in bindings.structural_references(
        mapping.binding.args, contracts.FEATURE_PREFIX
    ):
        _validate_referenced_feature(feature_id, mapping.id, feature_names)
    for referenced_dataset in bindings.structural_references(
        mapping.binding.args, contracts.DATASET_PREFIX
    ):
        _validate_referenced_dataset(referenced_dataset, mapping.id, dataset_ids)
    for referenced_dimension in bindings.structural_references(
        mapping.binding.args, contracts.DIMENSION_PREFIX
    ):
        _validate_referenced_dimension(referenced_dimension, mapping.id, dimension_ids)
    return dependencies


def _validate_row_context(
    validation_context: context_module.SpecValidationContext,
    mapping: spec_model.Mapping,
    context_entity: spec_model.Entity,
    context_dataset: spec_model.Dataset,
) -> None:
    """Validate one mapping's row-context requirements against its input dataset."""
    row_context = mapping.row_context
    if row_context is None:
        return

    model = validation_context.model
    _validate_row_context_order_requirement(
        mapping.id, row_context.requires_order, context_dataset.order
    )
    dimension_reference = row_context.dimension
    if dimension_reference is None:
        return

    dimension_id = dimension_reference.removeprefix(contracts.DIMENSION_PREFIX)
    _validate_row_context_dimension_membership(
        mapping.id, dimension_id, context_entity.dimension_ids
    )
    measures = {
        measure
        for direction in (row_context.before, row_context.after)
        if hasattr(direction, "model_dump")
        for measure in direction.model_dump(exclude_none=True)
    }
    expected_type = ("datetime" if "time" in measures else "integer") if measures else None
    _validate_row_context_dimension_type(
        mapping.id, expected_type, model.dimensions[dimension_id].type
    )
    order_dimensions = {key.dimension for key in context_dataset.order}
    _validate_row_context_order_presence(
        mapping.id, dimension_reference, row_context.requires_order, order_dimensions
    )


def validate_inputs(
    validation_context: context_module.SpecValidationContext,
    feature_producers: dict[str, tuple[str, str]],
    collapse_sources: context_module.CollapseSources,
) -> dict[tuple[str, str], set[tuple[str, str]]]:
    """Validate references and row context, returning the mapping dependency graph."""
    model = validation_context.model
    feature_names = set(validation_context.feature_names) | set(validation_context.dimension_ids)
    dataset_ids = set(validation_context.datasets_by_id)
    dimension_ids = set(model.dimensions)
    dependencies_by_mapping: dict[tuple[str, str], set[tuple[str, str]]] = {}

    for location in validation_context.iter_mappings():
        mapping = location.mapping
        operation = bindings.mapping_operation(mapping, model.functions)
        mapping_key = (location.dataset.id, mapping.id)
        dependencies_by_mapping[mapping_key] = _validate_input_references(
            location,
            operation,
            feature_producers,
            feature_names,
            dataset_ids,
            dimension_ids,
        )
        if operation == "collapse":
            source = collapse_sources[location.key]
            context_entity, context_dataset = source.entity, source.dataset
        else:
            context_entity, context_dataset = location.entity, location.dataset
        _validate_row_context(validation_context, mapping, context_entity, context_dataset)

    return dependencies_by_mapping


def _validate_collapse_source_differs_target(
    mapping_id: str, source_dataset_id: str, target_dataset_id: str
) -> None:
    """Require a collapse mapping to read from a different target dataset."""
    if source_dataset_id == target_dataset_id:
        raise ValueError(f"Collapse {mapping_id} cannot use its target dataset as source")


def _validate_collapse_grouping_dimensions(
    mapping_id: str, target_dimensions: list[str], source_dimensions: list[str], source_id: str
) -> None:
    """Require collapse target grouping dimensions to exist in the source entity."""
    if not set(target_dimensions).issubset(source_dimensions):
        raise ValueError(
            f"Collapse {mapping_id} grouping dimensions must exist in source {source_id}"
        )


def _validate_collapse_source_feature_membership(
    mapping_id: str, inputs: list[str], source_features: set[str], source_id: str
) -> None:
    """Require explicit collapse inputs to belong to the inferred source dataset."""
    unknown = sorted(set(inputs) - source_features)
    if unknown:
        raise ValueError(
            f"Collapse {mapping_id} references features outside source {source_id}: "
            + ", ".join(unknown)
        )


def _validate_collapse_source_dimensions(
    mapping_id: str, referenced_dimensions: set[str], source_dimensions: list[str]
) -> None:
    """Require collapse dimension selectors to belong to the source entity."""
    unknown_dimensions = referenced_dimensions - set(source_dimensions)
    if unknown_dimensions:
        raise ValueError(
            f"Collapse {mapping_id} references unknown source dimensions: "
            + ", ".join(sorted(unknown_dimensions))
        )


def _validate_feature_reference(feature_id: str, feature_names: set[str], mapping_id: str) -> None:
    """Require an explicit input feature to be declared in the spec."""
    if feature_id not in feature_names:
        raise ValueError(f"Mapping {mapping_id} references unknown input feature: {feature_id}")


def _validate_dataset_local_inputs(
    operation: str,
    mapping_id: str,
    feature_id: str,
    local_features: set[str],
) -> None:
    """Restrict vectorize and write inputs to their target dataset."""
    if operation in {"vectorize", "write"} and feature_id not in local_features:
        raise ValueError(
            f"Mapping {mapping_id} cannot read feature {feature_id} from another dataset"
        )


def _validate_referenced_feature(feature_id: str, mapping_id: str, feature_names: set[str]) -> None:
    """Require a feature selector in binding arguments to resolve."""
    if feature_id != contracts.CURRENT_ID and feature_id not in feature_names:
        raise ValueError(f"Mapping {mapping_id} references unknown feature: {feature_id}")


def _validate_referenced_dataset(dataset_id: str, mapping_id: str, dataset_ids: set[str]) -> None:
    """Require a dataset selector in binding arguments to resolve."""
    if dataset_id != contracts.CURRENT_ID and dataset_id not in dataset_ids:
        raise ValueError(f"Mapping {mapping_id} references unknown dataset: {dataset_id}")


def _validate_referenced_dimension(
    dimension_id: str, mapping_id: str, dimension_ids: set[str]
) -> None:
    """Require a dimension selector in binding arguments to resolve."""
    if dimension_id not in dimension_ids:
        raise ValueError(f"Mapping {mapping_id} references unknown dimension: {dimension_id}")


def _validate_row_context_order_requirement(
    mapping_id: str, requires_order: bool, dataset_order: list[spec_model.Order]
) -> None:
    """Require dataset ordering for directional row context."""
    if requires_order and not dataset_order:
        raise ValueError(f"Mapping {mapping_id} directional row context requires dataset order")


def _validate_row_context_dimension_membership(
    mapping_id: str, dimension_id: str, entity_dimensions: list[str]
) -> None:
    """Require a row-context dimension to belong to the input entity."""
    if dimension_id not in entity_dimensions:
        raise ValueError(
            f"Mapping {mapping_id} context dimension is not in the input entity: {dimension_id}"
        )


def _validate_row_context_dimension_type(
    mapping_id: str, expected_type: str | None, actual_type: str
) -> None:
    """Require a row-context dimension to have the type indicated by its extents."""
    if expected_type is not None and actual_type != expected_type:
        raise ValueError(f"Mapping {mapping_id} context dimension must have type {expected_type}")


def _validate_row_context_order_presence(
    mapping_id: str,
    dimension_reference: str,
    requires_order: bool,
    order_dimensions: set[str],
) -> None:
    """Require a directional row-context dimension to occur in dataset ordering."""
    if requires_order and dimension_reference not in order_dimensions:
        raise ValueError(f"Mapping {mapping_id} context dimension must occur in dataset order")
