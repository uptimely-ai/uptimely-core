"""Run atomic spec validators in explicit prerequisite order."""

from __future__ import annotations

import collections.abc
import graphlib

from uptimely.spec import model as spec_model

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

type Validator = collections.abc.Callable[[spec_model.Spec], None]

VALIDATION_DEPENDENCIES: dict[Validator, tuple[Validator, ...]] = {
    dataset.validate_dataset_ids: (),
    action_outputs.validate_feature_ownership: (),
    dimensions.validate_parent: (),
    dimensions.validate_parent_cycle: (dimensions.validate_parent,),
    dimensions.validate_entity_dimensions: (),
    dataset.validate_order_dimension: (dimensions.validate_entity_dimensions,),
    dataset.validate_unique_order_dimension: (),
    functions.validate_return_kind: (),
    functions.validate_dataframe_count: (),
    action_outputs.validate_function_reference: (),
    action_outputs.validate_function_id: (action_outputs.validate_function_reference,),
    action_outputs.validate_output_names: (action_outputs.validate_function_reference,),
    action_outputs.validate_output_presence: (action_outputs.validate_function_reference,),
    action_outputs.validate_write_outputs: (action_outputs.validate_function_reference,),
    action_outputs.validate_dimension_collision: (action_outputs.validate_function_reference,),
    action_outputs.validate_output_feature: (
        action_outputs.validate_function_reference,
        action_outputs.validate_write_outputs,
    ),
    action_outputs.validate_unique_producer: (
        action_outputs.validate_output_feature,
        action_outputs.validate_feature_ownership,
        action_outputs.validate_dimension_collision,
    ),
    action_outputs.validate_collapse_output: (action_outputs.validate_output_presence,),
    action_outputs.validate_current_feature_selector: (
        action_outputs.validate_output_presence,
        action_outputs.validate_collapse_output,
    ),
    action_inputs.validate_escape_inputs: (action_outputs.validate_function_reference,),
    action_inputs.validate_input_feature: (),
    action_inputs.validate_input_scope: (
        action_inputs.validate_input_feature,
        action_outputs.validate_function_reference,
    ),
    action_inputs.validate_feature_reference: (),
    action_inputs.validate_dataset_reference: (dataset.validate_dataset_ids,),
    action_inputs.validate_dimension_reference: (),
    bindings.validate_arguments: (action_outputs.validate_function_reference,),
    bindings.validate_selector_type: (bindings.validate_arguments,),
    collapse_inputs.validate_source_feature: (action_outputs.validate_function_reference,),
    collapse_inputs.validate_feature_owner: (
        action_outputs.validate_feature_ownership,
        action_inputs.validate_input_feature,
        collapse_inputs.validate_source_feature,
    ),
    collapse_inputs.validate_source_count: (
        dataset.validate_dataset_ids,
        collapse_inputs.validate_feature_owner,
    ),
    collapse_inputs.validate_source_target: (collapse_inputs.validate_source_count,),
    collapse_inputs.validate_grouping_dimensions: (
        collapse_inputs.validate_source_count,
        dimensions.validate_entity_dimensions,
    ),
    collapse_inputs.validate_source_features: (collapse_inputs.validate_source_count,),
    collapse_inputs.validate_source_dimensions: (
        collapse_inputs.validate_source_count,
        action_inputs.validate_dimension_reference,
    ),
    row_context.validate_dataset_order: (
        collapse_inputs.validate_source_count,
        dataset.validate_order_dimension,
        dataset.validate_unique_order_dimension,
    ),
    row_context.validate_dimension: (
        collapse_inputs.validate_source_count,
        dimensions.validate_entity_dimensions,
    ),
    row_context.validate_dimension_type: (row_context.validate_dimension,),
    row_context.validate_dimension_order: (
        row_context.validate_dimension,
        row_context.validate_dataset_order,
    ),
    action_contracts.validate_dataframe_reference: (bindings.validate_arguments,),
    action_contracts.validate_dataframe_selector: (action_contracts.validate_dataframe_reference,),
    action_contracts.validate_dataframe_source: (
        dataset.validate_dataset_ids,
        action_contracts.validate_dataframe_selector,
    ),
    action_contracts.validate_dataset_count: (
        action_contracts.validate_dataframe_source,
        functions.validate_dataframe_count,
    ),
    action_contracts.validate_matching_keys: (
        action_contracts.validate_dataframe_source,
        action_inputs.validate_dataset_reference,
        dimensions.validate_entity_dimensions,
    ),
    action_contracts.validate_input_feature_source_count: (
        action_outputs.validate_function_reference,
        action_outputs.validate_feature_ownership,
        action_inputs.validate_input_feature,
    ),
    action_contracts.validate_foreign_dataframe: (action_contracts.validate_dataset_count,),
    action_contracts.validate_dataframe_feature_source: (
        action_contracts.validate_dataset_count,
        action_contracts.validate_input_feature_source_count,
    ),
    action_contracts.validate_dataframe_features: (
        action_contracts.validate_dataframe_feature_source,
        dimensions.validate_entity_dimensions,
    ),
    action_contracts.validate_read_inputs: (action_outputs.validate_function_reference,),
    action_contracts.validate_target_input: (action_contracts.validate_dataframe_source,),
    action_contracts.validate_write_dataframe: (action_contracts.validate_dataframe_source,),
    action_contracts.validate_collapse_source: (
        action_contracts.validate_dataframe_source,
        collapse_inputs.validate_source_count,
    ),
    action_contracts.validate_collapse_dimensions: (collapse_inputs.validate_grouping_dimensions,),
    action_contracts.validate_conform_dimensions: (
        action_contracts.validate_dataframe_source,
        dimensions.validate_entity_dimensions,
    ),
    action_contracts.validate_expand_dimensions: (
        action_contracts.validate_dataframe_feature_source,
        dimensions.validate_entity_dimensions,
    ),
    dependencies.validate_action_cycle: (
        dataset.validate_dataset_ids,
        action_outputs.validate_unique_producer,
        action_inputs.validate_input_feature,
    ),
}


def validate_spec(spec: spec_model.Spec) -> None:
    """Run read-only semantic checks after their prerequisites succeed.

    Args:
        spec: The structurally parsed spec document.

    Raises:
        ValueError: A semantic invariant is violated.
        graphlib.CycleError: Validator dependencies contain a configuration cycle.
    """
    ordered = tuple(graphlib.TopologicalSorter(VALIDATION_DEPENDENCIES).static_order())
    for validate in ordered:
        validate(spec)
    action_outputs.warn_unproduced_features(spec)
