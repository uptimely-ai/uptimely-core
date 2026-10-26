"""Coordinate atomic semantic checks in their established first-error order."""

from __future__ import annotations

import collections.abc
import warnings

from uptimely.spec import model as spec_model

from .. import operations
from . import (
    bindings,
    collapse_inputs,
    dataset,
    dependencies,
    dimensions,
    functions,
    mapping_contracts,
    mapping_inputs,
    mapping_outputs,
    row_context,
)
from . import context as context_module


def validate_spec(model: spec_model.Spec) -> None:
    """Validate document semantics without constructing executable invocations.

    Args:
        model: The spec document to validate.

    Raises:
        ValueError: Declarations, references, mappings, or dependencies are invalid.
    """
    context = context_module.SpecValidationContext.build(model)
    for error in _validation_results(context):
        if error is not None:
            raise error
    _warn_unproduced_features(context)


def _warn_unproduced_features(context: context_module.SpecValidationContext) -> None:
    """Warn when declared dataset features have no mapping producer."""
    for location, _, missing in context.iter_output_datasets():
        if missing:
            feature_path = ".".join((*location.path, "features"))
            warnings.warn(
                f"{feature_path}: Features have no producer mapping: {', '.join(missing)}",
                UserWarning,
                stacklevel=2,
            )


def _validation_results(
    context: context_module.SpecValidationContext,
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Yield errors in the established declaration-first phase order."""
    yield from _early_declaration_results(context)
    yield from _dimension_results(context)
    yield from _output_results(context)
    yield from _input_results(context)
    yield from _binding_and_contract_results(context)


def _early_declaration_results(
    context: context_module.SpecValidationContext,
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Check declarations whose errors precede dimension and output validation."""
    for item in context.mappings:
        if item.operation == operations.VECTORIZE:
            yield mapping_outputs.validate_output_presence(item, item.location.mapping.id)
            yield mapping_outputs.validate_calculation_features(item)
            yield mapping_outputs.validate_function_id(item)
            yield mapping_outputs.validate_output_names(item)
    yield dataset.validate_unique_id(context.duplicate_dataset)
    yield mapping_outputs.validate_feature_ownership(context.duplicate_feature)
    for item in context.mappings:
        yield mapping_outputs.validate_dimension_collision(item, context.dimension_ids)
    for item, feature, owner in context.iter_calculation_dependencies():
        yield dependencies.validate_calculation_dependency(item, feature, owner)
    for item, foreign in context.iter_write_dependencies():
        yield dependencies.validate_write_dependencies(item, foreign)


def _dimension_results(
    context: context_module.SpecValidationContext,
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Validate dimension parents, entity membership, and dataset ordering."""
    for item in context.dimension_parents:
        yield dimensions.validate_parent(item, context.dimension_ids)
        yield dimensions.validate_parent_cycle(item)
    for entity_id, entity_dimensions in context.iter_entity_dimensions():
        yield dimensions.validate_entity_dimensions(
            entity_id, entity_dimensions, context.dimension_ids
        )
    for item in context.order_dimensions:
        yield dataset.validate_order_dimension(item)
        yield dataset.validate_unique_order_dimension(item)


def _output_results(
    context: context_module.SpecValidationContext,
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Validate mapping outputs and dataset producer coverage."""
    for _, output_mappings, _ in context.iter_output_datasets():
        for item, declarations in output_mappings:
            yield mapping_outputs.validate_function_reference(item)
            if item.operation == operations.WRITE:
                yield mapping_outputs.validate_write_outputs(item)
                continue
            yield mapping_outputs.validate_output_presence(item, item.location.mapping_id)
            yield mapping_outputs.validate_dimension_collision(item, item.dimensions)
            for feature, previous in declarations:
                yield mapping_outputs.validate_output_feature(item, feature)
                yield mapping_outputs.validate_unique_producer(item, feature, previous)
            yield mapping_outputs.validate_collapse_output(item)
            yield mapping_outputs.validate_current_feature_selector(item)


def _input_results(
    context: context_module.SpecValidationContext,
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Validate collapse sources, mapping references, row context, and cycles."""
    for item in context.collapse_inputs:
        yield collapse_inputs.validate_source_feature(item)
        for feature, owners in item.candidates:
            yield collapse_inputs.validate_feature_owner(
                item.mapping.location.mapping.id, feature, owners
            )
        yield collapse_inputs.validate_source_count(item)
        yield collapse_inputs.validate_source_target(item)
        yield collapse_inputs.validate_grouping_dimensions(item)
        yield collapse_inputs.validate_source_features(item)
        yield collapse_inputs.validate_source_dimensions(item, context.dimension_ids)
    for item, prepared_context in context.iter_input_contexts():
        yield mapping_inputs.validate_escape_inputs(item)
        for feature in item.inputs:
            yield mapping_inputs.validate_input_feature(item, feature, context.feature_names)
            yield mapping_inputs.validate_input_scope(item, feature)
        for feature in item.feature_selectors:
            yield mapping_inputs.validate_feature_reference(item, feature, context.feature_names)
        for reference in item.dataset_references:
            yield mapping_inputs.validate_dataset_reference(item, reference, context.datasets_by_id)
        for dimension, path in item.dimension_reference_paths:
            yield mapping_inputs.validate_dimension_reference(
                item, dimension, context.dimension_ids, path
            )
        if prepared_context is not None:
            yield row_context.validate_dataset_order(prepared_context)
            yield row_context.validate_dimension(prepared_context)
            yield row_context.validate_dimension_type(prepared_context)
            yield row_context.validate_dimension_order(prepared_context)
    yield dependencies.validate_mapping_cycle(context.mapping_cycle)


def _binding_and_contract_results(
    context: context_module.SpecValidationContext,
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Validate function bindings and operation-specific mapping contracts."""
    for item in context.iter_bound_mappings():
        yield bindings.validate_arguments(item)
        for value, argument_type in context.iter_binding_selectors(item):
            yield bindings.validate_selector_type(
                value,
                argument_type,
                (*item.location.declaration_path, "binding", "args"),
            )
    for function_id, function, dataframe_inputs in context.iter_functions():
        yield functions.validate_return_kind(function_id, function, dataframe_inputs)
        yield functions.validate_dataframe_count(function_id, function, dataframe_inputs)
    for item in context.mapping_contracts:
        for argument in item.dataframe_arguments:
            yield mapping_contracts.validate_dataframe_reference(argument)
            yield mapping_contracts.validate_dataframe_selector(argument)
            yield mapping_contracts.validate_dataframe_source(argument)
        yield mapping_contracts.validate_dataset_count(item)
        yield mapping_contracts.validate_matching_keys(item)
        yield mapping_contracts.validate_input_feature_source_count(item)
        yield mapping_contracts.validate_foreign_dataframe(item)
        yield mapping_contracts.validate_dataframe_feature_source(item)
        yield mapping_contracts.validate_dataframe_features(item)
        yield mapping_contracts.validate_read_inputs(item.mapping)
        yield mapping_contracts.validate_target_input(item)
        yield mapping_contracts.validate_local_features(item)
        yield mapping_contracts.validate_collapse_source(item)
        yield mapping_contracts.validate_collapse_dimensions(item)
        yield mapping_contracts.validate_conform_dimensions(item)
        yield mapping_contracts.validate_expand_dimensions(item)
