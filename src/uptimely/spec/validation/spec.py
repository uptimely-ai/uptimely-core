"""Run atomic spec validators in explicit prerequisite order."""

from __future__ import annotations

import collections.abc
import graphlib

from uptimely.spec import model as spec_model

from .rules import (
    bindings,
    datasets,
    dimensions,
    entities,
    features,
    functions,
    row_context,
)
from .rules.actions import contracts as action_contracts
from .rules.actions import dependencies
from .rules.actions import inputs as action_inputs
from .rules.actions import outputs as action_outputs

type Validator = collections.abc.Callable[[spec_model.Spec], None]

VALIDATION_DEPENDENCIES: dict[Validator, tuple[Validator, ...]] = {
    datasets.validate_dataset_ids: (),
    features.validate_feature_ownership: (),
    dimensions.validate_parent: (),
    dimensions.validate_parent_cycle: (dimensions.validate_parent,),
    entities.validate_entity_dimensions: (),
    datasets.validate_order_dimension: (entities.validate_entity_dimensions,),
    datasets.validate_unique_order_dimension: (),
    functions.validate_return_kind: (),
    functions.validate_dataframe_count: (),
    action_outputs.validate_function_reference: (),
    action_outputs.validate_function_id: (action_outputs.validate_function_reference,),
    action_outputs.validate_output_names: (action_outputs.validate_function_reference,),
    action_outputs.validate_output_presence: (action_outputs.validate_function_reference,),
    action_outputs.validate_nonproducing_outputs: (action_outputs.validate_function_reference,),
    action_outputs.validate_dimension_collision: (action_outputs.validate_function_reference,),
    action_outputs.validate_output_feature: (
        action_outputs.validate_function_reference,
        action_outputs.validate_nonproducing_outputs,
    ),
    action_outputs.validate_unique_producer: (
        action_outputs.validate_output_feature,
        features.validate_feature_ownership,
        action_outputs.validate_dimension_collision,
    ),
    action_outputs.validate_collapse_output: (action_outputs.validate_output_presence,),
    action_outputs.validate_current_feature_selector: (
        action_outputs.validate_output_presence,
        action_outputs.validate_collapse_output,
    ),
    action_inputs.validate_input_feature: (),
    action_inputs.validate_input_scope: (
        action_inputs.validate_input_feature,
        action_outputs.validate_function_reference,
    ),
    action_inputs.validate_feature_reference: (),
    action_inputs.validate_dataset_reference: (datasets.validate_dataset_ids,),
    action_inputs.validate_dimension_reference: (),
    bindings.validate_arguments: (action_outputs.validate_function_reference,),
    bindings.validate_selector_type: (bindings.validate_arguments,),
    action_inputs.validate_source_feature: (action_outputs.validate_function_reference,),
    action_inputs.validate_feature_owner: (
        features.validate_feature_ownership,
        action_inputs.validate_input_feature,
        action_inputs.validate_source_feature,
    ),
    action_inputs.validate_source_count: (
        datasets.validate_dataset_ids,
        action_inputs.validate_feature_owner,
    ),
    action_inputs.validate_source_target: (action_inputs.validate_source_count,),
    action_inputs.validate_grouping_dimensions: (
        action_inputs.validate_source_count,
        entities.validate_entity_dimensions,
    ),
    action_inputs.validate_source_features: (action_inputs.validate_source_count,),
    action_inputs.validate_source_dimensions: (
        action_inputs.validate_source_count,
        action_inputs.validate_dimension_reference,
    ),
    row_context.validate_dataset_order: (
        action_inputs.validate_source_count,
        datasets.validate_order_dimension,
        datasets.validate_unique_order_dimension,
    ),
    row_context.validate_dimension: (
        action_inputs.validate_source_count,
        entities.validate_entity_dimensions,
    ),
    row_context.validate_dimension_type: (row_context.validate_dimension,),
    row_context.validate_dimension_order: (
        row_context.validate_dimension,
        row_context.validate_dataset_order,
    ),
    action_contracts.validate_dataframe_reference: (bindings.validate_arguments,),
    action_contracts.validate_dataframe_selector: (action_contracts.validate_dataframe_reference,),
    action_contracts.validate_dataframe_source: (
        datasets.validate_dataset_ids,
        action_contracts.validate_dataframe_selector,
    ),
    action_contracts.validate_dataset_count: (
        action_contracts.validate_dataframe_source,
        functions.validate_dataframe_count,
    ),
    action_contracts.validate_matching_keys: (
        action_contracts.validate_dataframe_source,
        action_inputs.validate_dataset_reference,
        entities.validate_entity_dimensions,
    ),
    action_contracts.validate_input_feature_source_count: (
        action_outputs.validate_function_reference,
        features.validate_feature_ownership,
        action_inputs.validate_input_feature,
    ),
    action_contracts.validate_foreign_dataframe: (action_contracts.validate_dataset_count,),
    action_contracts.validate_dataframe_feature_source: (
        action_contracts.validate_dataset_count,
        action_contracts.validate_input_feature_source_count,
    ),
    action_contracts.validate_dataframe_features: (
        action_contracts.validate_dataframe_feature_source,
        entities.validate_entity_dimensions,
    ),
    action_contracts.validate_feature_input_scope: (action_outputs.validate_function_reference,),
    action_contracts.validate_target_input: (action_contracts.validate_dataframe_source,),
    action_contracts.validate_write_dataframe: (action_contracts.validate_dataframe_source,),
    action_contracts.validate_collapse_source: (
        action_contracts.validate_dataframe_source,
        action_inputs.validate_source_count,
    ),
    action_contracts.validate_collapse_dimensions: (action_inputs.validate_grouping_dimensions,),
    action_contracts.validate_conform_dimensions: (
        action_contracts.validate_dataframe_source,
        entities.validate_entity_dimensions,
    ),
    action_contracts.validate_expand_dimensions: (
        action_contracts.validate_dataframe_feature_source,
        entities.validate_entity_dimensions,
    ),
    dependencies.validate_action_cycle: (
        datasets.validate_dataset_ids,
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
