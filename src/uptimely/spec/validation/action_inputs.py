"""Atomic explicit input and structural reference checks."""

from __future__ import annotations

from .. import functions, selectors
from . import context as context_module
from . import errors


def validate_escape_inputs(item: context_module.ActionFacts) -> context_module.ValidationResult:
    """Require escape actions to declare feature inputs."""
    if item.kind == functions.ESCAPE and not item.inputs:
        return errors.SpecError(
            "Escape actions must declare one or more input features",
            code="invalid_mapping_feature_inputs",
            path=(*item.location.path, "features", "inputs"),
        )
    return None


def validate_input_feature(
    item: context_module.ActionFacts, feature: str, feature_names: frozenset[str]
) -> context_module.ValidationResult:
    """Require an explicit input feature to be declared."""
    if feature not in feature_names:
        return ValueError(
            f"Action {item.location.action.id} references unknown input feature: {feature}"
        )
    return None


def validate_input_scope(
    item: context_module.ActionFacts,
    feature: str,
) -> context_module.ValidationResult:
    """Require vectorize and write inputs to belong to the target dataset."""
    if item.kind in {functions.VECTORIZE, functions.WRITE} and feature not in item.local_features:
        return ValueError(
            f"Action {item.location.action.id} cannot read feature {feature} from another dataset"
        )
    return None


def validate_feature_reference(
    item: context_module.ActionFacts, feature: str, feature_names: frozenset[str]
) -> context_module.ValidationResult:
    """Require a structural feature reference to be declared."""
    if feature != selectors.CURRENT_ID and feature not in feature_names:
        return ValueError(f"Action {item.location.action.id} references unknown feature: {feature}")
    return None


def validate_dataset_reference(
    item: context_module.ActionFacts,
    dataset: str,
    datasets_by_id: dict[str, tuple[context_module.DatasetLocation, ...]],
) -> context_module.ValidationResult:
    """Require a structural dataset reference to be declared."""
    if dataset != selectors.CURRENT_ID and dataset not in datasets_by_id:
        return ValueError(f"Action {item.location.action.id} references unknown dataset: {dataset}")
    return None


def validate_dimension_reference(
    item: context_module.ActionFacts,
    dimension: str,
    dimension_ids: frozenset[str],
    path: context_module.SpecPath,
) -> context_module.ValidationResult:
    """Require a structural dimension reference to be declared."""
    if dimension not in dimension_ids:
        return errors.SpecError(
            f"Action {item.location.action.id} references unknown dimension: {dimension}",
            code="unknown_dimension_reference",
            path=path,
        )
    return None
