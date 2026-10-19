"""Coordinate semantic spec validation phases in their established order."""

from __future__ import annotations

from uptimely.spec import model as spec_model

from . import context as context_module
from . import dataset as dataset_validation
from . import dependencies as dependency_validation
from . import dimensions as dimensions_validation
from . import functions as function_validation
from . import mapping_contracts as contracts_validation
from . import mapping_inputs as inputs_validation
from . import mapping_outputs as outputs_validation


def validate_spec(model: spec_model.Spec) -> None:
    """Validate document semantics without constructing executable invocations.

    Args:
        model: The spec document to validate.

    Raises:
        ValueError: Declarations, references, mappings, or dependencies are invalid.
    """
    validation_context = context_module.SpecValidationContext.build(model)
    outputs_validation.validate_calculation_outputs(validation_context)
    dataset_validation.validate_dataset_ids(model)
    outputs_validation.validate_feature_ownership(validation_context)
    dependency_validation.validate_calculation_dependencies(validation_context)
    dependency_validation.validate_write_dependencies(validation_context)

    declared_dimensions = dimensions_validation.validate_parents(validation_context)
    dimensions_validation.validate_entity_dimensions(validation_context, declared_dimensions)
    dataset_validation.validate_order(validation_context)

    feature_producers = outputs_validation.validate_outputs(validation_context)
    collapse_sources = inputs_validation.validate_collapse(validation_context)
    mapping_dependencies = inputs_validation.validate_inputs(
        validation_context, feature_producers, collapse_sources
    )
    dependency_validation.validate_mapping_cycles(mapping_dependencies)
    function_validation.validate_bindings(validation_context)
    function_validation.validate_contracts(validation_context)
    contracts_validation.validate_contracts(validation_context, collapse_sources)
