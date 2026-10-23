"""Atomic dataframe and operation-specific mapping contract checks."""

from __future__ import annotations

from .. import operations, selectors
from . import context as context_module
from . import errors

CONFORM_INPUT_ERROR = (
    "Conform mapping must combine its target dataset with a dataset from the same entity"
)
EXPAND_INPUT_ERROR = (
    "Expand mapping must combine its target dataset with a "
    "declared feature from a lower-dimensional dataset"
)


def validate_dataframe_reference(
    item: context_module.DataframeInput,
) -> context_module.ValidationResult:
    """Require a dataframe argument to reference a dataset."""
    if not isinstance(item.value, str) or not item.value.startswith(selectors.DATASET_PREFIX):
        return errors.SpecError(
            f"Dataframe argument {item.argument_id} must reference a dataset",
            code="invalid_mapping_dataset_input",
            path=item.path,
        )
    return None


def validate_dataframe_selector(
    item: context_module.DataframeInput,
) -> context_module.ValidationResult:
    """Reject a dataset ID selector where a dataframe is required."""
    if isinstance(item.value, str) and item.value.endswith(selectors.ID_SELECTOR):
        return errors.SpecError(
            f"Dataframe argument {item.argument_id} must reference a dataframe",
            code="invalid_mapping_dataset_input",
            path=item.path,
        )
    return None


def validate_dataframe_source(
    item: context_module.DataframeInput,
) -> context_module.ValidationResult:
    """Require a dataframe reference to resolve to a dataset."""
    if item.source is None:
        return errors.SpecError(
            f"Dataframe argument {item.argument_id} references unknown dataset {item.source_id}",
            code="invalid_mapping_dataset_input",
            path=item.path,
        )
    return None


def validate_dataset_count(item: context_module.MappingContract) -> context_module.ValidationResult:
    """Require conform and expand to consume two distinct datasets."""
    operation = item.mapping.operation
    if operation in {operations.CONFORM, operations.EXPAND} and len(item.dataset_ids) != 2:
        return errors.SpecError(
            f"{operation.capitalize()} mapping must consume two distinct datasets",
            code="invalid_mapping_dataset_input",
            path=(*item.mapping.location.path, "binding", "args"),
        )
    return None


def validate_dataframe_features(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require conform and expand feature inputs to belong to dataframe inputs."""
    operation = item.mapping.operation
    if operation in {operations.CONFORM, operations.EXPAND} and item.unavailable_features:
        return errors.SpecError(
            f"{operation.capitalize()} mapping inputs must belong to its dataframe inputs: "
            + ", ".join(item.unavailable_features),
            code="invalid_mapping_feature_inputs",
            path=(*item.mapping.location.path, "features", "inputs"),
        )
    return None


def validate_read_inputs(item: context_module.MappingFacts) -> context_module.ValidationResult:
    """Reject feature inputs on read mappings."""
    if item.operation == operations.READ and item.inputs:
        return errors.SpecError(
            "Read mappings cannot declare feature inputs",
            code="invalid_mapping_feature_inputs",
            path=(*item.location.path, "features", "inputs"),
        )
    return None


def validate_target_input(item: context_module.MappingContract) -> context_module.ValidationResult:
    """Require vectorize and write to consume their target dataset."""
    operation = item.mapping.operation
    if operation in {operations.VECTORIZE, operations.WRITE} and not item.target_is_input:
        return errors.SpecError(
            f"{operation.capitalize()} mapping must consume its target dataset",
            code="invalid_mapping_dataset_input",
            path=(*item.mapping.location.path, "binding", "args"),
        )
    return None


def validate_local_features(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require vectorize and write feature inputs to belong to their target."""
    operation = item.mapping.operation
    if operation in {operations.VECTORIZE, operations.WRITE} and item.local_foreign_features:
        return errors.SpecError(
            f"{operation.capitalize()} mapping inputs must belong to its target dataset: "
            + ", ".join(item.local_foreign_features),
            code="invalid_mapping_feature_inputs",
            path=(*item.mapping.location.path, "features", "inputs"),
        )
    return None


def validate_collapse_source(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require collapse to consume its inferred source dataset."""
    if (
        item.mapping.operation == operations.COLLAPSE
        and item.source is not None
        and item.source.dataset.id not in item.dataset_ids
    ):
        return errors.SpecError(
            f"Collapse mapping must consume its source dataset {item.source.dataset.id}",
            code="invalid_mapping_dataset_input",
            path=(*item.mapping.location.path, "binding", "args"),
        )
    return None


def validate_collapse_dimensions(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require collapse to reduce source dimensionality."""
    if (
        item.mapping.operation == operations.COLLAPSE
        and item.source is not None
        and item.source_dimensions == item.mapping.dimensions
    ):
        return errors.SpecError(
            "Collapse mapping must reduce dataset dimensionality",
            code="invalid_mapping_dimensions",
            path=(*item.mapping.location.path, "features", "inputs"),
        )
    return None


def validate_conform_dimensions(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require conform inputs to preserve target dimensionality."""
    if item.mapping.operation == operations.CONFORM and any(
        dimensions != item.mapping.dimensions for dimensions in item.input_dimensions
    ):
        return errors.SpecError(
            "Conform mapping inputs must preserve target dimensionality",
            code="invalid_mapping_dimensions",
            path=(*item.mapping.location.path, "binding", "args"),
        )
    return None


def validate_conform_entity(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require conform to combine its target with an input from the same entity."""
    if item.mapping.operation == operations.CONFORM and (
        not item.target_is_input or not item.same_entity
    ):
        return errors.SpecError(
            CONFORM_INPUT_ERROR,
            code="invalid_mapping_entity",
            path=(*item.mapping.location.path, "binding", "args"),
        )
    return None


def validate_expand_dimensions(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require expand to combine its target with a lower-dimensional feature."""
    if item.mapping.operation == operations.EXPAND and (
        not item.target_is_input or not item.lower_dataset_ids or not item.has_lower_feature
    ):
        return errors.SpecError(
            EXPAND_INPUT_ERROR,
            code="invalid_mapping_dimensions",
            path=(*item.mapping.location.path, "binding", "args"),
        )
    return None
