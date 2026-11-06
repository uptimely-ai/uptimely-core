"""Run atomic spec validators in explicit prerequisite order."""

from __future__ import annotations

import collections.abc
import graphlib
import logging

from uptimely.spec import model as spec_model

from .rules import (
    bindings,
    dimensions,
    features,
    functions,
    profile_identity,
    profiles,
    row_context,
)
from .rules.operators import contracts as operator_contracts
from .rules.operators import dependencies
from .rules.operators import inputs as operator_inputs
from .rules.operators import outputs as operator_outputs

logger = logging.getLogger(__name__)

type Validator = collections.abc.Callable[[spec_model.Spec], None]

COMPUTE_FUNCTION_VALIDATORS: tuple[Validator, ...] = (
    operator_outputs.validate_compute_function_exists,
    operator_outputs.validate_compute_function_kind,
)
MERGE_FUNCTION_VALIDATORS: tuple[Validator, ...] = (
    operator_outputs.validate_merge_function_exists,
    operator_outputs.validate_merge_function_kind,
)

VALIDATION_DEPENDENCIES: dict[Validator, tuple[Validator, ...]] = {
    profile_identity.validate_profile_ids: (),
    features.validate_feature_ownership: (),
    dimensions.validate_parent: (),
    dimensions.validate_parent_cycle: (dimensions.validate_parent,),
    profiles.validate_grain_dimensions: (),
    profiles.validate_unique_grain_dimensions: (),
    profiles.validate_grain_resolutions: (profiles.validate_grain_dimensions,),
    profiles.validate_unique_grain_keys: (profiles.validate_grain_resolutions,),
    profile_identity.validate_order_dimension: (profiles.validate_unique_grain_keys,),
    profile_identity.validate_unique_order_dimension: (),
    functions.validate_return_kind: (),
    functions.validate_dataframe_count: (),
    functions.validate_nullable_dataframe_arguments: (functions.validate_dataframe_count,),
    functions.validate_merge_target_argument: (functions.validate_dataframe_count,),
    functions.validate_merge_fragment_argument: (functions.validate_dataframe_count,),
    operator_outputs.validate_compute_function_exists: (),
    operator_outputs.validate_compute_function_kind: (
        operator_outputs.validate_compute_function_exists,
    ),
    operator_outputs.validate_merge_function_exists: (),
    operator_outputs.validate_merge_function_kind: (
        operator_outputs.validate_merge_function_exists,
    ),
    operator_outputs.validate_function_id: COMPUTE_FUNCTION_VALIDATORS,
    operator_outputs.validate_output_names: COMPUTE_FUNCTION_VALIDATORS,
    operator_outputs.validate_output_presence: COMPUTE_FUNCTION_VALIDATORS,
    operator_outputs.validate_nonproducing_outputs: COMPUTE_FUNCTION_VALIDATORS,
    operator_outputs.validate_dimension_collision: COMPUTE_FUNCTION_VALIDATORS,
    operator_outputs.validate_output_feature: (
        *COMPUTE_FUNCTION_VALIDATORS,
        operator_outputs.validate_nonproducing_outputs,
    ),
    operator_outputs.validate_unique_producer: (
        operator_outputs.validate_output_feature,
        features.validate_feature_ownership,
        operator_outputs.validate_dimension_collision,
    ),
    operator_outputs.validate_collapse_output: (operator_outputs.validate_output_presence,),
    operator_outputs.validate_current_feature_selector: (
        operator_outputs.validate_output_presence,
        operator_outputs.validate_collapse_output,
    ),
    operator_inputs.validate_input_feature: (),
    operator_inputs.validate_input_scope: (
        operator_inputs.validate_input_feature,
        *COMPUTE_FUNCTION_VALIDATORS,
    ),
    operator_inputs.validate_feature_reference: (),
    operator_inputs.validate_dataset_reference: (profile_identity.validate_profile_ids,),
    operator_inputs.validate_dimension_reference: (),
    bindings.validate_arguments: (
        *COMPUTE_FUNCTION_VALIDATORS,
        *MERGE_FUNCTION_VALIDATORS,
    ),
    bindings.validate_default_merge_function: (),
    bindings.validate_selector_type: (bindings.validate_arguments,),
    bindings.validate_selector_metadata: (bindings.validate_arguments,),
    bindings.validate_merge_operator_kind: (
        *COMPUTE_FUNCTION_VALIDATORS,
        *MERGE_FUNCTION_VALIDATORS,
    ),
    bindings.validate_merge_target: (bindings.validate_arguments,),
    bindings.validate_merge_fragment: (bindings.validate_arguments,),
    bindings.validate_merge_feature_references: (),
    operator_inputs.validate_source_feature: (*COMPUTE_FUNCTION_VALIDATORS,),
    operator_inputs.validate_feature_owner: (
        features.validate_feature_ownership,
        operator_inputs.validate_input_feature,
        operator_inputs.validate_source_feature,
    ),
    operator_inputs.validate_source_count: (
        profile_identity.validate_profile_ids,
        operator_inputs.validate_feature_owner,
    ),
    operator_inputs.validate_source_target: (operator_inputs.validate_source_count,),
    operator_inputs.validate_grouping_dimensions: (
        operator_inputs.validate_source_count,
        profiles.validate_unique_grain_keys,
    ),
    operator_inputs.validate_source_features: (operator_inputs.validate_source_count,),
    operator_inputs.validate_source_dimensions: (
        operator_inputs.validate_source_count,
        operator_inputs.validate_dimension_reference,
    ),
    row_context.validate_dataset_order: (
        operator_inputs.validate_source_count,
        profile_identity.validate_order_dimension,
        profile_identity.validate_unique_order_dimension,
    ),
    row_context.validate_dimension: (
        operator_inputs.validate_source_count,
        profiles.validate_unique_grain_keys,
    ),
    row_context.validate_dimension_type: (row_context.validate_dimension,),
    row_context.validate_dimension_order: (
        row_context.validate_dimension,
        row_context.validate_dataset_order,
    ),
    operator_contracts.validate_dataset_argument_reference: (bindings.validate_arguments,),
    operator_contracts.validate_dataset_argument_selector: (
        operator_contracts.validate_dataset_argument_reference,
    ),
    operator_contracts.validate_dataset_argument_source: (
        profile_identity.validate_profile_ids,
        operator_contracts.validate_dataset_argument_selector,
    ),
    operator_contracts.validate_dataset_argument_count: (
        operator_contracts.validate_dataset_argument_source,
        functions.validate_dataframe_count,
    ),
    operator_contracts.validate_matching_keys: (
        operator_contracts.validate_dataset_argument_source,
        operator_inputs.validate_dataset_reference,
        profiles.validate_unique_grain_keys,
    ),
    operator_contracts.validate_input_feature_source_count: (
        *COMPUTE_FUNCTION_VALIDATORS,
        features.validate_feature_ownership,
        operator_inputs.validate_input_feature,
    ),
    operator_contracts.validate_foreign_dataset_argument: (
        operator_contracts.validate_dataset_argument_count,
    ),
    operator_contracts.validate_dataset_argument_feature_source: (
        operator_contracts.validate_dataset_argument_count,
        operator_contracts.validate_input_feature_source_count,
    ),
    operator_contracts.validate_dataset_argument_features: (
        operator_contracts.validate_dataset_argument_feature_source,
        profiles.validate_unique_grain_keys,
    ),
    operator_contracts.validate_feature_input_scope: (*COMPUTE_FUNCTION_VALIDATORS,),
    operator_contracts.validate_target_dataset_input: (
        operator_contracts.validate_dataset_argument_source,
    ),
    operator_contracts.validate_target_dataset_only: (
        operator_contracts.validate_dataset_argument_source,
    ),
    operator_contracts.validate_dimension_source: (
        operator_contracts.validate_dataset_argument_source,
        operator_inputs.validate_source_count,
    ),
    operator_contracts.validate_dimension_change: (
        operator_contracts.validate_dataset_argument_source,
        profiles.validate_unique_grain_keys,
    ),
    operator_contracts.validate_dimension_expansion_input: (
        operator_contracts.validate_dataset_argument_feature_source,
        profiles.validate_unique_grain_keys,
    ),
    dependencies.validate_operator_cycle: (
        profile_identity.validate_profile_ids,
        operator_outputs.validate_unique_producer,
        operator_inputs.validate_input_feature,
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
    logger.debug("  Semantic checks:")
    ordered = tuple(graphlib.TopologicalSorter(VALIDATION_DEPENDENCIES).static_order())
    for validate in ordered:
        validate(spec)
    operator_outputs.warn_unproduced_features(spec)
