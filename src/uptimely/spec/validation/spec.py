"""Coordinate atomic semantic checks in their established first-error order."""

from __future__ import annotations

import collections.abc
import warnings

from uptimely.spec import model as spec_model

from .. import functions as function_kinds
from . import (
    action_contracts,
    action_inputs,
    action_outputs,
    bindings,
    collapse_inputs,
    dataset,
    dependencies,
    dimensions,
    functions,
    row_context,
)
from . import context as context_module


def validate_spec(model: spec_model.Spec) -> None:
    """Validate document semantics without constructing executable invocations.

    Args:
        model: The spec document to validate.

    Raises:
        ValueError: Declarations, references, actions, or dependencies are invalid.
    """
    context = context_module.SpecValidationContext.build(model)
    for error in _validation_results(context):
        if error is not None:
            raise error
    _warn_unproduced_features(context)


def _warn_unproduced_features(context: context_module.SpecValidationContext) -> None:
    """Warn when declared dataset features have no action producer."""
    for location, _, missing in action_outputs.iter_output_datasets(
        context.datasets, context.actions
    ):
        if missing:
            feature_path = ".".join((*location.path, "features"))
            warnings.warn(
                f"{feature_path}: Features have no producer action: {', '.join(missing)}",
                UserWarning,
                stacklevel=2,
            )


def _validation_results(
    context: context_module.SpecValidationContext,
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Yield errors in the established declaration-first phase order."""
    collapse_items = tuple(
        collapse_inputs.iter_collapse_inputs(
            context.actions, context.dimension_ids, context.feature_owners
        )
    )
    collapse_sources = collapse_inputs.source_index(collapse_items)
    yield from _early_declaration_results(context)
    yield from _dimension_results(context)
    yield from _output_results(context)
    yield from _input_results(context, collapse_items, collapse_sources)
    yield from _binding_and_contract_results(context, collapse_sources)


def _early_declaration_results(
    context: context_module.SpecValidationContext,
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Check declarations whose errors precede dimension and output validation."""
    for item in context.actions:
        if item.kind == function_kinds.VECTORIZE:
            yield action_outputs.validate_output_presence(item, item.location.action.id)
            yield action_outputs.validate_calculation_features(item)
            yield action_outputs.validate_function_id(item)
            yield action_outputs.validate_output_names(item)
    yield dataset.validate_unique_id(context.duplicate_dataset)
    yield action_outputs.validate_feature_ownership(context.duplicate_feature)
    for item in context.actions:
        yield action_outputs.validate_dimension_collision(item, context.dimension_ids)
    for item, feature, owner in dependencies.iter_calculation_dependencies(
        context.actions, context.first_feature_owner
    ):
        yield dependencies.validate_calculation_dependency(item, feature, owner)
    for item, foreign in dependencies.iter_write_dependencies(
        context.actions, context.first_feature_owner
    ):
        yield dependencies.validate_write_dependencies(item, foreign)


def _dimension_results(
    context: context_module.SpecValidationContext,
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Validate dimension parents, entity membership, and dataset ordering."""
    for item in dimensions.iter_parent_declarations(context.model):
        yield dimensions.validate_parent(item, context.dimension_ids)
        yield dimensions.validate_parent_cycle(item)
    for entity_id, entity_dimensions in dimensions.iter_entity_dimensions(context.model):
        yield dimensions.validate_entity_dimensions(
            entity_id, entity_dimensions, context.dimension_ids
        )
    for item in dataset.iter_order_dimensions(context.datasets):
        yield dataset.validate_order_dimension(item)
        yield dataset.validate_unique_order_dimension(item)


def _output_results(
    context: context_module.SpecValidationContext,
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Validate action outputs and dataset producer coverage."""
    for _, output_actions, _ in action_outputs.iter_output_datasets(
        context.datasets, context.actions
    ):
        for item, declarations in output_actions:
            yield action_outputs.validate_function_reference(
                item.location.action.binding.function,
                item.location.dataset.id,
                context.model.functions.root,
                (*item.location.declaration_path, "binding", "function"),
            )
            if item.kind == function_kinds.WRITE:
                yield action_outputs.validate_write_outputs(item)
                continue
            yield action_outputs.validate_output_presence(item, item.location.action_id)
            yield action_outputs.validate_dimension_collision(item, item.dimensions)
            for feature, previous in declarations:
                yield action_outputs.validate_output_feature(item, feature)
                yield action_outputs.validate_unique_producer(item, feature, previous)
            yield action_outputs.validate_collapse_output(item)
            yield action_outputs.validate_current_feature_selector(item)


def _input_results(
    context: context_module.SpecValidationContext,
    collapse_items: tuple[collapse_inputs.CollapseInputs, ...],
    collapse_sources: dict[tuple[str, str, str], context_module.DatasetLocation],
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Validate collapse sources, action references, row context, and cycles."""
    for item in collapse_items:
        yield collapse_inputs.validate_source_feature(item)
        for feature, owners in item.candidates:
            yield collapse_inputs.validate_feature_owner(
                item.action.location.action.id, feature, owners
            )
        yield collapse_inputs.validate_source_count(item)
        yield collapse_inputs.validate_source_target(item)
        yield collapse_inputs.validate_grouping_dimensions(item)
        yield collapse_inputs.validate_source_features(item)
        yield collapse_inputs.validate_source_dimensions(item, context.dimension_ids)
    for item, prepared_context in row_context.iter_row_contexts(
        context.actions, context.model, collapse_sources
    ):
        yield action_inputs.validate_escape_inputs(item)
        for feature in item.inputs:
            yield action_inputs.validate_input_feature(item, feature, context.feature_names)
            yield action_inputs.validate_input_scope(item, feature)
        for feature in item.feature_selectors:
            yield action_inputs.validate_feature_reference(item, feature, context.feature_names)
        for reference in item.dataset_references:
            yield action_inputs.validate_dataset_reference(item, reference, context.datasets_by_id)
        for dimension, path in item.dimension_reference_paths:
            yield action_inputs.validate_dimension_reference(
                item, dimension, context.dimension_ids, path
            )
        if prepared_context is not None:
            yield row_context.validate_dataset_order(prepared_context)
            yield row_context.validate_dimension(prepared_context)
            yield row_context.validate_dimension_type(prepared_context)
            yield row_context.validate_dimension_order(prepared_context)
    producers = dependencies.feature_producers(context.actions, context.dimension_ids)
    yield dependencies.validate_action_cycle(
        dependencies.find_action_cycle(context.actions, producers)
    )


def _binding_and_contract_results(
    context: context_module.SpecValidationContext,
    collapse_sources: dict[tuple[str, str, str], context_module.DatasetLocation],
) -> collections.abc.Iterator[context_module.ValidationResult]:
    """Validate function bindings and kind-specific action contracts."""
    for item in bindings.iter_bound_actions(context.actions):
        yield bindings.validate_arguments(item)
        for value, argument_type in bindings.iter_binding_selectors(item):
            yield bindings.validate_selector_type(
                value,
                argument_type,
                (*item.location.declaration_path, "binding", "args"),
            )
    for function_id, function, dataframe_inputs in functions.iter_functions(context.model):
        yield functions.validate_return_kind(function_id, function, dataframe_inputs)
        yield functions.validate_dataframe_count(function_id, function, dataframe_inputs)
    for item in action_contracts.iter_action_contracts(
        context.actions,
        context.dataset,
        collapse_sources,
    ):
        for argument in item.dataframe_arguments:
            yield action_contracts.validate_dataframe_reference(argument)
            yield action_contracts.validate_dataframe_selector(argument)
            yield action_contracts.validate_dataframe_source(argument)
        yield action_contracts.validate_dataset_count(item)
        yield action_contracts.validate_matching_keys(item, context.dataset)
        yield action_contracts.validate_input_feature_source_count(
            item, context.dimension_ids, context.last_feature_owner
        )
        yield action_contracts.validate_foreign_dataframe(item)
        yield action_contracts.validate_dataframe_feature_source(
            item, context.dimension_ids, context.last_feature_owner
        )
        yield action_contracts.validate_dataframe_features(
            item, context.dimension_ids, context.last_feature_owner
        )
        yield action_contracts.validate_read_inputs(item.action)
        yield action_contracts.validate_target_input(item)
        yield action_contracts.validate_local_features(item)
        yield action_contracts.validate_collapse_source(item)
        yield action_contracts.validate_collapse_dimensions(item)
        yield action_contracts.validate_conform_dimensions(item)
        yield action_contracts.validate_expand_dimensions(item, context.last_feature_owner)
