"""Mapping output declarations, feature ownership, and producer accounting."""

from __future__ import annotations

from uptimely import contracts
from uptimely.spec import model as spec_model
from uptimely.spec import references as bindings

from . import context as context_module


def _validate_mapping_outputs(
    context: context_module.SpecValidationContext,
    location: context_module.MappingLocation,
    producers: dict[str, str],
) -> dict[str, tuple[str, str]]:
    """Validate one mapping's outputs and return its non-dimension producers."""
    mapping = location.mapping
    mapping_id = location.mapping_id
    function = context.model.functions.get(mapping.binding.function)
    if function is None:
        raise ValueError(
            f"Dataset {location.dataset.id} mappings reference unknown functions: "
            f"{mapping.binding.function}"
        )
    if function.operation == "write":
        _validate_output_forbidden(mapping_id, mapping.output_features)
        return {}

    dimensions = set(location.entity.dimension_ids)
    _validate_output_required(mapping_id, mapping.output_features)
    if function.operation == "vectorize":
        _validate_output_dimension_collisions(mapping.output_features, dimensions)

    feature_producers: dict[str, tuple[str, str]] = {}
    for feature_id in mapping.output_features:
        _validate_output_declaration(mapping_id, feature_id, location.dataset.features)
        if feature_id in dimensions:
            continue
        _validate_producer_uniqueness(feature_id, mapping_id, producers)
        producers[feature_id] = mapping_id
        if feature_id not in context.dimension_ids:
            feature_producers[feature_id] = (location.dataset.id, mapping_id)

    _validate_current_feature_outputs(location, function.operation, dimensions)
    return feature_producers


def _validate_current_feature_outputs(
    location: context_module.MappingLocation,
    operation: contracts.FunctionOperation,
    dimensions: set[str],
) -> None:
    """Restrict current-feature placeholders according to the operation's outputs."""
    mapping = location.mapping
    if operation == "collapse":
        _validate_collapse_non_dimension_output(
            location.mapping_id, mapping.output_features, dimensions
        )
        output_count = len(set(mapping.output_features) - dimensions)
        validate_placeholder = _validate_collapse_current_feature_placeholder
    elif operation == "vectorize":
        output_count = len(mapping.output_features)
        validate_placeholder = _validate_vectorize_current_feature_placeholder
    else:
        return
    references_current_feature = contracts.CURRENT_ID in bindings.structural_references(
        mapping.binding.args, contracts.FEATURE_PREFIX
    )
    validate_placeholder(location.mapping_id, output_count, references_current_feature)


def validate_outputs(
    validation_context: context_module.SpecValidationContext,
) -> dict[str, tuple[str, str]]:
    """Validate output declarations and return feature-to-producer mappings."""
    feature_producers: dict[str, tuple[str, str]] = {}
    for entity_id, entity in validation_context.model.entities.items():
        entity_dimensions = set(entity.dimension_ids)
        for dataset_model in entity.datasets:
            producers: dict[str, str] = {}
            for mapping_id, mapping in dataset_model.mappings.items():
                location = context_module.MappingLocation(
                    entity_id, entity, dataset_model, mapping_id, mapping
                )
                feature_producers.update(
                    _validate_mapping_outputs(validation_context, location, producers)
                )
            _validate_producer_completeness(dataset_model.features, producers, entity_dimensions)
    return feature_producers


def validate_calculation_outputs(
    validation_context: context_module.SpecValidationContext,
) -> None:
    """Validate vectorize output declarations before collection-wide checks."""
    for _entity_id, dataset, mapping in bindings.iter_mappings(validation_context.model):
        function = validation_context.model.functions.get(mapping.binding.function)
        if function is None or function.operation != "vectorize":
            continue
        _validate_output_required(mapping.id, mapping.output_features)
        unknown = set(mapping.output_features) - dataset.features.keys()
        if unknown:
            raise ValueError(
                f"Mapping {mapping.id} references unknown feature: " + ", ".join(sorted(unknown))
            )
        if not function.id.strip():
            raise ValueError("Every function must define a non-empty string id")
        for feature in mapping.output_features:
            if not feature.strip():
                raise ValueError("Every calculation must define a non-empty output feature name")


def validate_feature_ownership(
    validation_context: context_module.SpecValidationContext,
) -> None:
    """Validate feature ownership and calculated feature/dimension collisions."""
    duplicate_feature = min(
        (
            (owners[1].order, feature_id)
            for feature_id, owners in validation_context.feature_owners.items()
            if len(owners) > 1
        ),
        default=(0, None),
    )[1]
    _validate_unique_feature_ownership(duplicate_feature)

    dimension_names = set(validation_context.dimension_ids)
    for _entity_id, _dataset, mapping in bindings.iter_mappings(validation_context.model):
        function = validation_context.model.functions.get(mapping.binding.function)
        if function is not None and function.operation == "vectorize":
            _validate_output_dimension_collisions(mapping.output_features, dimension_names)


def _validate_output_required(mapping_id: str, output_features: list[str]) -> None:
    """Require a mapping to declare at least one output feature."""
    if not output_features:
        raise ValueError(f"Mapping {mapping_id} must declare one or more features")


def _validate_output_forbidden(mapping_id: str, output_features: list[str]) -> None:
    """Forbid output features on a write mapping."""
    if output_features:
        raise ValueError(f"Write mapping {mapping_id} cannot produce features")


def _validate_output_dimension_collisions(output_features: list[str], dimensions: set[str]) -> None:
    """Reject calculated feature names that collide with entity dimensions."""
    collisions = sorted(set(output_features) & dimensions)
    if collisions:
        raise ValueError(
            "Calculated feature names cannot duplicate entity dimensions: " + ", ".join(collisions)
        )


def _validate_output_declaration(
    mapping_id: str, feature_id: str, dataset_features: dict[str, spec_model.Feature]
) -> None:
    """Require a mapping output to be declared in its dataset."""
    if feature_id not in dataset_features:
        raise ValueError(f"Mapping {mapping_id} references unknown feature: {feature_id}")


def _validate_producer_uniqueness(
    feature_id: str, mapping_id: str, producers: dict[str, str]
) -> None:
    """Require each non-dimension feature to have at most one producer."""
    if feature_id in producers:
        raise ValueError(
            f"Feature {feature_id} is produced by multiple mappings: "
            f"{producers[feature_id]}, {mapping_id}"
        )


def _validate_producer_completeness(
    dataset_features: dict[str, spec_model.Feature],
    producers: dict[str, str],
    dimensions: set[str],
) -> None:
    """Require every non-dimension dataset feature to have a producer."""
    missing = sorted(set(dataset_features) - set(producers) - dimensions)
    if missing:
        raise ValueError("Features have no producer mapping: " + ", ".join(missing))


def _validate_vectorize_current_feature_placeholder(
    mapping_id: str,
    output_count: int,
    references_current_feature: bool,
) -> None:
    """Restrict the current-feature placeholder on multi-output vectorize mappings."""
    if output_count > 1 and references_current_feature:
        raise ValueError(
            f"Vectorize mapping {mapping_id} cannot use $features.@ "
            "when it produces multiple features"
        )


def _validate_collapse_current_feature_placeholder(
    mapping_id: str,
    output_count: int,
    references_current_feature: bool,
) -> None:
    """Restrict the current-feature placeholder on multi-output collapse mappings."""
    if output_count > 1 and references_current_feature:
        raise ValueError(
            f"Collapse mapping {mapping_id} cannot use $features.@ "
            "when it produces multiple features"
        )


def _validate_collapse_non_dimension_output(
    mapping_id: str, output_features: list[str], dimensions: set[str]
) -> None:
    """Require collapse mappings to produce at least one non-dimension feature."""
    if not set(output_features) - dimensions:
        raise ValueError(f"Collapse mapping {mapping_id} must produce a non-dimension feature")


def _validate_unique_feature_ownership(duplicate_feature: str | None) -> None:
    """Require each non-dimension feature to have one declaring dataset."""
    if duplicate_feature is not None:
        raise ValueError(f"Duplicate feature name: {duplicate_feature}")
