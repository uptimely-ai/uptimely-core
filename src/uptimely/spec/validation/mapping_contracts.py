"""Dataframe arguments and operation-specific mapping contracts."""

from __future__ import annotations

from uptimely import contracts
from uptimely.spec import model as spec_model

from . import context as context_module
from . import errors

CONFORM_INPUT_ERROR = (
    "Conform mapping must combine its target dataset with a dataset from the same entity"
)
EXPAND_INPUT_ERROR = (
    "Expand mapping must combine its target dataset with a "
    "declared feature from a lower-dimensional dataset"
)


def validate_contracts(
    context: context_module.SpecValidationContext,
    collapse_sources: context_module.CollapseSources,
) -> None:
    """Validate common dataframe inputs before each operation's contract."""
    for location in context.iter_mappings():
        function = context.model.functions[location.mapping.binding.function]
        inputs = _resolve_dataframe_inputs(context, location, function)
        operation = function.operation
        if operation in {"conform", "expand"}:
            _validate_join_inputs(context, location, inputs, operation)

        match operation:
            case "read":
                _validate_read_contract(location)
            case "vectorize" | "write":
                _validate_local_contract(location, inputs, operation)
            case "collapse":
                _validate_collapse_contract(location, inputs, collapse_sources[location.key])
            case "conform":
                _validate_conform_contract(location, inputs)
            case "expand":
                _validate_expand_contract(context, location, inputs)


def _resolve_dataframe_inputs(
    context: context_module.SpecValidationContext,
    location: context_module.MappingLocation,
    function: spec_model.FunctionTemplate,
) -> list[context_module.DatasetLocation]:
    """Resolve declared dataframe arguments, rejecting invalid selectors and datasets."""
    inputs: list[context_module.DatasetLocation] = []
    for argument_id, argument in function.args.items():
        if argument.type != "dataframe":
            continue
        value = location.mapping.binding.args[argument_id]
        path = (*location.path, "binding", "args", argument_id)
        if not isinstance(value, str) or not value.startswith(contracts.DATASET_PREFIX):
            raise errors.SpecError(
                f"Dataframe argument {argument_id} must reference a dataset",
                code="invalid_mapping_dataset_input",
                path=path,
            )
        if value.endswith(contracts.ID_SELECTOR):
            raise errors.SpecError(
                f"Dataframe argument {argument_id} must reference a dataframe",
                code="invalid_mapping_dataset_input",
                path=path,
            )
        reference = value.removeprefix(contracts.DATASET_PREFIX).removesuffix(
            contracts.DATAFRAME_SELECTOR
        )
        source_id = location.dataset.id if reference == contracts.CURRENT_ID else reference
        source = context.dataset(source_id)
        if source is None:
            raise errors.SpecError(
                f"Dataframe argument {argument_id} references unknown dataset {source_id}",
                code="invalid_mapping_dataset_input",
                path=path,
            )
        inputs.append(source)
    return inputs


def _validate_read_contract(location: context_module.MappingLocation) -> None:
    """Forbid explicit feature inputs on read mappings."""
    if location.mapping.input_features:
        raise errors.SpecError(
            "Read mappings cannot declare feature inputs",
            code="invalid_mapping_feature_inputs",
            path=(*location.path, "features", "inputs"),
        )


def _validate_local_contract(
    location: context_module.MappingLocation,
    inputs: list[context_module.DatasetLocation],
    operation: contracts.FunctionOperation,
) -> None:
    """Require vectorize and write mappings to consume their own dataset and features."""
    if not any(source.dataset.id == location.dataset.id for source in inputs):
        raise errors.SpecError(
            f"{operation.capitalize()} mapping must consume its target dataset",
            code="invalid_mapping_dataset_input",
            path=(*location.path, "binding", "args"),
        )
    local_features = set(location.dataset.features) | set(location.entity.dimension_ids)
    invalid_inputs = sorted(
        feature for feature in location.mapping.input_features if feature not in local_features
    )
    if invalid_inputs:
        raise errors.SpecError(
            f"{operation.capitalize()} mapping inputs must belong to its target dataset: "
            + ", ".join(invalid_inputs),
            code="invalid_mapping_feature_inputs",
            path=(*location.path, "features", "inputs"),
        )


def _validate_collapse_contract(
    location: context_module.MappingLocation,
    inputs: list[context_module.DatasetLocation],
    source: context_module.CollapseSource,
) -> None:
    """Require the inferred source dataframe and a reduction in dimensionality."""
    if not any(item.dataset.id == source.dataset.id for item in inputs):
        raise errors.SpecError(
            f"Collapse mapping must consume its source dataset {source.dataset.id}",
            code="invalid_mapping_dataset_input",
            path=(*location.path, "binding", "args"),
        )
    if set(source.entity.dimension_ids) == set(location.entity.dimension_ids):
        raise errors.SpecError(
            "Collapse mapping must reduce dataset dimensionality",
            code="invalid_mapping_dimensions",
            path=(*location.path, "features", "inputs"),
        )


def _validate_join_inputs(
    context: context_module.SpecValidationContext,
    location: context_module.MappingLocation,
    inputs: list[context_module.DatasetLocation],
    operation: contracts.FunctionOperation,
) -> None:
    """Require two distinct dataframes and features available from those inputs."""
    dataset_ids = {source.dataset.id for source in inputs}
    if len(dataset_ids) != 2:
        raise errors.SpecError(
            f"{operation.capitalize()} mapping must consume two distinct datasets",
            code="invalid_mapping_dataset_input",
            path=(*location.path, "binding", "args"),
        )
    input_dimensions = {dimension for source in inputs for dimension in source.entity.dimension_ids}
    unavailable_features = sorted(
        feature_id
        for feature_id in location.mapping.input_features
        if (feature_id in context.dimension_ids and feature_id not in input_dimensions)
        or (
            feature_id not in context.dimension_ids
            and (
                (owner := context.last_feature_owner(feature_id)) is None
                or owner.dataset.id not in dataset_ids
            )
        )
    )
    if unavailable_features:
        raise errors.SpecError(
            f"{operation.capitalize()} mapping inputs must belong to its dataframe inputs: "
            + ", ".join(unavailable_features),
            code="invalid_mapping_feature_inputs",
            path=(*location.path, "features", "inputs"),
        )


def _validate_conform_contract(
    location: context_module.MappingLocation,
    inputs: list[context_module.DatasetLocation],
) -> None:
    """Require matching dimensions and the target combined within its entity."""
    target_dimensions = set(location.entity.dimension_ids)
    if any(set(source.entity.dimension_ids) != target_dimensions for source in inputs):
        raise errors.SpecError(
            "Conform mapping inputs must preserve target dimensionality",
            code="invalid_mapping_dimensions",
            path=(*location.path, "binding", "args"),
        )
    target_is_input = any(source.dataset.id == location.dataset.id for source in inputs)
    if not target_is_input or any(source.entity_id != location.entity_id for source in inputs):
        raise errors.SpecError(
            CONFORM_INPUT_ERROR,
            code="invalid_mapping_entity",
            path=(*location.path, "binding", "args"),
        )


def _validate_expand_contract(
    context: context_module.SpecValidationContext,
    location: context_module.MappingLocation,
    inputs: list[context_module.DatasetLocation],
) -> None:
    """Require the target and a feature from a lower-dimensional input."""
    target_dimensions = set(location.entity.dimension_ids)
    lower_dataset_ids = {
        source.dataset.id
        for source in inputs
        if set(source.entity.dimension_ids) < target_dimensions
    }
    target_is_input = any(source.dataset.id == location.dataset.id for source in inputs)
    has_lower_feature = any(
        (owner := context.last_feature_owner(feature_id)) is not None
        and owner.dataset.id in lower_dataset_ids
        for feature_id in location.mapping.input_features
    )
    if not target_is_input or not lower_dataset_ids or not has_lower_feature:
        raise errors.SpecError(
            EXPAND_INPUT_ERROR,
            code="invalid_mapping_dimensions",
            path=(*location.path, "binding", "args"),
        )
