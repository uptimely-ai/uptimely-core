"""Resolved calculation dependency validation."""

from __future__ import annotations

import typing

from . import context as context_module

__all__ = ["_validate_feature_dependencies"]


def _validate_feature_dependencies(
    calls: list[typing.Any], validation_context: context_module.SpecValidationContext
) -> None:
    """Validate that calculation dependencies resolve to features or dimensions."""
    feature_names = validation_context.feature_names
    dimensions = validation_context.dimension_ids
    for call in calls:
        for dependency in call.depends_on_features:
            if dependency not in feature_names and dependency not in dimensions:
                raise ValueError(
                    f"Calculation {call.feature} references unknown feature: {dependency}"
                )
