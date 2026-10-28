"""Atomic dataframe and function-kind-specific mapping contract checks."""

from __future__ import annotations

from .. import functions, selectors
from . import context as context_module
from . import errors

EXPAND_INPUT_ERROR = (
    "Expand mapping must reference a declared feature from a lower-dimensional foreign dataset"
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
    if isinstance(item.value, str) and (
        item.value.endswith(selectors.ID_SELECTOR)
        or item.value.endswith(selectors.DIMENSION_IDS_SELECTOR)
    ):
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
    """Require dimensional operations to consume one foreign dataframe."""
    kind = item.mapping.kind
    if kind not in {functions.CONFORM, functions.COLLAPSE, functions.EXPAND}:
        return None

    expected_count = functions.KIND_DATAFRAME_INPUT_COUNTS[kind]
    if len(item.dataframe_arguments) != expected_count or len(item.dataset_ids) != expected_count:
        return errors.SpecError(
            f"{kind.capitalize()} mapping must consume exactly {expected_count} foreign dataset(s)",
            code="invalid_mapping_dataset_input",
            path=(*item.mapping.location.path, "binding", "args"),
        )
    return None


def validate_matching_keys(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require explicitly selected matching keys to exist on every participating dataset."""
    invalid = next(
        (
            (key, dataset_id)
            for key, dataset_id, dimensions in item.matching_key_checks
            if key.dimension_id not in dimensions
        ),
        None,
    )
    if invalid is None:
        return None
    key, dataset_id = invalid
    return errors.SpecError(
        f"Matching key {key.dimension_id} is not a dimension of dataset {dataset_id}",
        code="invalid_mapping_matching_key",
        path=key.path,
    )


def validate_input_feature_source_count(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require dimensional input features to belong to at most one dataset."""
    kind = item.mapping.kind
    if kind not in {functions.CONFORM, functions.COLLAPSE, functions.EXPAND}:
        return None
    if len(item.feature_dataset_ids) > 1:
        return errors.SpecError(
            f"{kind.capitalize()} mapping inputs must belong to one source dataset",
            code="invalid_mapping_dataset_input",
            path=(*item.mapping.location.path, "features", "inputs"),
        )
    return None


def validate_foreign_dataframe(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Reject the target dataset as a dimensional operation's dataframe input."""
    kind = item.mapping.kind
    if kind not in {functions.CONFORM, functions.COLLAPSE, functions.EXPAND}:
        return None
    if len(item.dataframe_arguments) != functions.KIND_DATAFRAME_INPUT_COUNTS[kind]:
        return None

    dataframe = item.dataframe_arguments[0]
    if dataframe.source_id == item.mapping.location.dataset.id:
        return errors.SpecError(
            f"{kind.capitalize()} mapping must reference a foreign source dataset",
            code="invalid_mapping_dataset_input",
            path=dataframe.path,
        )
    return None


def validate_dataframe_feature_source(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require a dimensional dataframe argument to match the input feature owner."""
    kind = item.mapping.kind
    if kind not in {functions.CONFORM, functions.COLLAPSE, functions.EXPAND}:
        return None
    if len(item.dataframe_arguments) != functions.KIND_DATAFRAME_INPUT_COUNTS[kind]:
        return None
    if len(item.feature_dataset_ids) != 1:
        return None

    dataframe = item.dataframe_arguments[0]
    if dataframe.source is None:
        return None
    expected_source = next(iter(item.feature_dataset_ids))
    if dataframe.source.dataset.id != expected_source:
        return errors.SpecError(
            f"{kind.capitalize()} mapping must reference its foreign source dataset "
            f"{expected_source}",
            code="invalid_mapping_dataset_input",
            path=dataframe.path,
        )
    return None


def validate_dataframe_features(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require conform and expand feature inputs to belong to dataframe inputs."""
    kind = item.mapping.kind
    if kind in {functions.CONFORM, functions.EXPAND} and item.unavailable_features:
        return errors.SpecError(
            f"{kind.capitalize()} mapping inputs must belong to its dataframe inputs: "
            + ", ".join(item.unavailable_features),
            code="invalid_mapping_feature_inputs",
            path=(*item.mapping.location.path, "features", "inputs"),
        )
    return None


def validate_read_inputs(item: context_module.MappingFacts) -> context_module.ValidationResult:
    """Reject feature inputs on read mappings."""
    if item.kind == functions.READ and item.inputs:
        return errors.SpecError(
            "Read mappings cannot declare feature inputs",
            code="invalid_mapping_feature_inputs",
            path=(*item.location.path, "features", "inputs"),
        )
    return None


def validate_target_input(item: context_module.MappingContract) -> context_module.ValidationResult:
    """Require vectorize and write to consume their target dataset."""
    kind = item.mapping.kind
    if kind in {functions.VECTORIZE, functions.WRITE} and not item.target_is_input:
        return errors.SpecError(
            f"{kind.capitalize()} mapping must consume its target dataset",
            code="invalid_mapping_dataset_input",
            path=(*item.mapping.location.path, "binding", "args"),
        )
    return None


def validate_local_features(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require vectorize and write feature inputs to belong to their target."""
    kind = item.mapping.kind
    if kind in {functions.VECTORIZE, functions.WRITE} and item.local_foreign_features:
        return errors.SpecError(
            f"{kind.capitalize()} mapping inputs must belong to its target dataset: "
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
        item.mapping.kind == functions.COLLAPSE
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
        item.mapping.kind == functions.COLLAPSE
        and item.source is not None
        and not item.mapping.dimensions < item.source_dimensions
    ):
        return errors.SpecError(
            "Collapse mapping source must have strictly higher dimensionality than its target",
            code="invalid_mapping_dimensions",
            path=(*item.mapping.location.path, "features", "inputs"),
        )
    return None


def validate_conform_dimensions(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require conform inputs to preserve target dimensionality."""
    if item.mapping.kind == functions.CONFORM and any(
        dimensions != item.mapping.dimensions for dimensions in item.input_dimensions
    ):
        return errors.SpecError(
            "Conform mapping inputs must preserve target dimensionality",
            code="invalid_mapping_dimensions",
            path=(*item.mapping.location.path, "binding", "args"),
        )
    return None


def validate_expand_dimensions(
    item: context_module.MappingContract,
) -> context_module.ValidationResult:
    """Require expand to use a declared feature from a lower-dimensional source."""
    if item.mapping.kind == functions.EXPAND and (
        not item.lower_dataset_ids or not item.has_lower_feature
    ):
        return errors.SpecError(
            EXPAND_INPUT_ERROR,
            code="invalid_mapping_dimensions",
            path=(*item.mapping.location.path, "binding", "args"),
        )
    return None
