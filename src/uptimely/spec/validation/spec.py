"""Run spec validators in small, explicit groups."""

from __future__ import annotations

import collections.abc
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

REFERENCE_CHECKS: tuple[Validator, ...] = (
    profile_identity.validate_profile_ids,
    features.validate_feature_ownership,
    dimensions.validate_parent,
    dimensions.validate_parent_cycle,
    profiles.validate_grain_dimensions,
    profiles.validate_unique_grain_dimensions,
    profile_identity.validate_unique_order_dimension,
    functions.validate_function_contracts,
    operator_outputs.validate_compute_function_exists,
    operator_outputs.validate_merge_function_exists,
    operator_inputs.validate_input_feature,
    operator_inputs.validate_feature_reference,
    operator_inputs.validate_dimension_reference,
    bindings.validate_default_merge_function,
    bindings.validate_merge_feature_references,
    operator_inputs.validate_profile_reference,
    profiles.validate_grain_resolutions,
    profiles.validate_unique_grain_keys,
    bindings.validate_binding_contracts,
)

DECLARATION_CHECKS: tuple[Validator, ...] = (
    operator_outputs.validate_function_id,
    operator_outputs.validate_output_names,
    operator_outputs.validate_output_presence,
    operator_outputs.validate_nonproducing_outputs,
    operator_outputs.validate_dimension_collision,
    operator_inputs.validate_input_scope,
    operator_inputs.validate_source_feature,
    operator_contracts.validate_input_feature_source_count,
    operator_contracts.validate_feature_input_scope,
    bindings.validate_arguments,
    profile_identity.validate_order_dimension,
    operator_outputs.validate_collapse_output,
    operator_outputs.validate_output_feature,
    operator_inputs.validate_feature_owner,
    bindings.validate_selector_type,
    bindings.validate_selector_metadata,
    bindings.validate_merge_dataset,
    bindings.validate_merge_fragment,
    operator_contracts.validate_dataframe_argument_profile_reference,
    operator_outputs.validate_current_feature_selector,
    operator_outputs.validate_unique_producer,
    operator_inputs.validate_source_count,
    operator_contracts.validate_dataframe_argument_selector,
    operator_inputs.validate_source_target,
    operator_inputs.validate_grouping_dimensions,
    operator_inputs.validate_source_features,
    operator_inputs.validate_source_dimensions,
    row_context.validate_row_context_profile_order,
    row_context.validate_dimension,
    operator_contracts.validate_dataframe_argument_profile_source,
    row_context.validate_dimension_type,
    row_context.validate_dimension_order,
    operator_contracts.validate_dataframe_argument_count,
    operator_contracts.validate_matching_keys,
    operator_contracts.validate_target_profile_input,
    operator_contracts.validate_target_profile_only,
    operator_contracts.validate_dimension_source,
    operator_contracts.validate_dimension_change,
    operator_contracts.validate_foreign_profile_argument,
    operator_contracts.validate_dataframe_argument_feature_source,
    operator_contracts.validate_dataframe_argument_features,
    operator_contracts.validate_dimension_expansion_input,
)

GRAPH_CHECKS: tuple[Validator, ...] = (dependencies.validate_operator_cycle,)
WARNING_CHECKS: tuple[Validator, ...] = (operator_outputs.warn_unproduced_features,)

VALIDATION_GROUPS: tuple[tuple[str, tuple[Validator, ...]], ...] = (
    ("Reference checks", REFERENCE_CHECKS),
    ("Declaration checks", DECLARATION_CHECKS),
    ("Graph checks", GRAPH_CHECKS),
    ("Warnings", WARNING_CHECKS),
)


def validate_spec(spec: spec_model.Spec) -> None:
    """Run reference, declaration, graph, and warning checks in order.

    Args:
        spec: The structurally parsed spec document.

    Raises:
        ValueError: A semantic invariant is violated.
    """
    logger.info("Start spec validation")
    for _group_name, checks in VALIDATION_GROUPS:
        for check in checks:
            check(spec)
    logger.info("Spec validated")
