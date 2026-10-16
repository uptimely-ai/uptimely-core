"""Ordered orchestration of semantic analytics validation."""

from __future__ import annotations

import typing

from . import context as context_module
from . import dependencies, dimensions, functions, mappings


def validate_analytics(
    model: typing.Any,
    calls: list[typing.Any],
    *,
    validation_context: context_module.AnalyticsValidationContext | None = None,
) -> None:
    """Validate references and invariants after the structural model is parsed.

    The order is intentional: preserve the first validation error reported for
    documents containing more than one semantic error.
    """
    validation_context = validation_context or context_module.AnalyticsValidationContext.build(
        model
    )
    declared_dimensions = dimensions._validate_dimensions(validation_context)
    dimensions.validate_dataset_ids(validation_context)
    dimensions._validate_entity_dimensions(validation_context, declared_dimensions)
    dimensions._validate_dataset_order(validation_context)
    categories = validation_context.function_categories

    for entity in validation_context.model.entities.values():
        mappings._validate_calculation_bindings(entity, categories)
        functions._validate_operation_functions(entity, categories)

    mappings._validate_collapses(validation_context)
    mappings._validate_mapping_inputs(validation_context)
    functions._validate_binding_contracts(validation_context, categories)
    functions._validate_function_contracts(validation_context)
    mappings._validate_mapping_contracts(validation_context)
    dependencies._validate_feature_dependencies(calls, validation_context)
