"""Validation rules for resolved functions and calls."""

from __future__ import annotations

import typing

from .. import model as analytics_model
from .. import resolved
from . import analytics as analytics_validation
from . import context as context_module
from . import dimensions


def _validate_feature_ownership(
    validation_context: context_module.AnalyticsValidationContext,
) -> None:
    """Reject duplicate feature names and record each feature's dataset."""
    duplicate = validation_context.first_duplicate_feature()
    if duplicate is not None:
        raise ValueError(f"Duplicate feature name: {duplicate}")


def _validate_calculation_dimensions(
    validation_context: context_module.AnalyticsValidationContext,
) -> None:
    """Ensure calculated features do not collide with entity dimensions."""
    dimension_names = validation_context.dimension_ids
    for entity in validation_context.model.entities.values():
        for dataset in entity.datasets:
            for mapping in dataset.mappings.values():
                function = validation_context.model.functions.get(mapping.binding.function)
                if function is not None and function.operation == "vectorize":
                    collisions = sorted(set(mapping.output_features) & dimension_names)
                    if collisions:
                        raise ValueError(
                            "Calculated feature names cannot duplicate entity dimensions: "
                            + ", ".join(collisions)
                        )


def _validate_calculation_dependencies(
    calls: list[typing.Any],
    validation_context: context_module.AnalyticsValidationContext,
) -> None:
    """Keep resolved calculations from reading features in another dataset."""
    dimension_names = validation_context.dimension_ids
    for call in calls:
        owner = validation_context.first_feature_owner(call.feature)
        owner_id = (owner.entity_id, owner.dataset.id) if owner is not None else None
        if owner is None and call.feature in dimension_names:
            continue
        for dependency in call.depends_on_features:
            dependency_owner = validation_context.first_feature_owner(dependency)
            dependency_owner_id = (
                (dependency_owner.entity_id, dependency_owner.dataset.id)
                if dependency_owner is not None
                else None
            )
            if dependency_owner_id is not None and dependency_owner_id != owner_id:
                raise ValueError(
                    f"Calculation {call.feature} cannot read feature {dependency} "
                    "from another dataset; use a source resource "
                    "operation to transfer features between datasets"
                )


def _validate_write_dependencies(
    validation_context: context_module.AnalyticsValidationContext,
) -> None:
    """Keep write mappings from consuming features owned by another dataset."""
    model = validation_context.model
    for entity_id, entity in model.entities.items():
        for dataset in entity.datasets:
            dataset_key = (entity_id, dataset.id)
            for mapping in dataset.mappings.values():
                function = model.functions.get(mapping.binding.function)
                if function is None or function.operation != "write":
                    continue
                foreign_features = sorted(
                    feature
                    for feature in set(mapping.input_features)
                    if feature not in entity.dimension_ids
                    and (
                        (owner := validation_context.first_feature_owner(feature)) is None
                        or (owner.entity_id, owner.dataset.id) != dataset_key
                    )
                )
                if foreign_features:
                    raise ValueError(
                        f"Write mapping {mapping.id} cannot read features from "
                        "another dataset: " + ", ".join(foreign_features)
                    )


def _validate_function_definitions(functions: list[typing.Any]) -> set[str]:
    """Validate resolved function definitions and return their identifiers."""
    seen_function_ids: set[str] = set()
    for function in functions:
        if not isinstance(function, resolved.Function):
            raise ValueError(
                f"Function definition must be a Function object, got {type(function).__name__}"
            )

        function_id = function.id
        if not isinstance(function_id, str) or not function_id.strip():
            raise ValueError("Every function must define a non-empty string id")
        if function_id in seen_function_ids:
            raise ValueError(f"Duplicate function id: {function_id}")
        seen_function_ids.add(function_id)

        operation_type = function.type
        if not isinstance(operation_type, str) or not operation_type.strip():
            raise ValueError(f"Function '{function_id}' must define a type")
        if operation_type not in analytics_model.FUNCTION_TYPES:
            raise ValueError(
                f"Function '{function_id}' uses unsupported operation type: {operation_type}"
            )

    return seen_function_ids


def _validate_call_definitions(calls: list[typing.Any], function_ids: set[str]) -> None:
    """Validate resolved call definitions and their function references."""
    seen_output_features: set[str] = set()
    for call in calls:
        if not isinstance(call, resolved.Call):
            raise ValueError(
                f"Call definition must be a Callable object, got {type(call).__name__}"
            )
        if not isinstance(call.feature, str) or not call.feature.strip():
            raise ValueError("Every call must define a non-empty output feature name")
        if call.feature in seen_output_features:
            raise ValueError(f"Duplicate output feature: {call.feature}")
        seen_output_features.add(call.feature)
        if call.function not in function_ids:
            raise ValueError(
                f"Call for feature '{call.feature}' references unknown function: {call.function}"
            )


def validate_prepared(
    model: analytics_model.Analytics,
    functions: list[typing.Any],
    calls: list[typing.Any],
) -> None:
    """Validate resolved and semantic analytics rules in the established order."""
    validation_context = context_module.AnalyticsValidationContext.build(model)
    dimensions.validate_dataset_ids(validation_context)
    _validate_feature_ownership(validation_context)
    _validate_calculation_dimensions(validation_context)
    _validate_calculation_dependencies(calls, validation_context)
    _validate_write_dependencies(validation_context)
    function_ids = _validate_function_definitions(functions)
    _validate_call_definitions(calls, function_ids)
    analytics_validation.validate_analytics(model, calls, validation_context=validation_context)
