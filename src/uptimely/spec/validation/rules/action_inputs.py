"""Atomic explicit input and structural reference checks."""

from __future__ import annotations

from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model

from .. import errors, traversal


def validate_escape_inputs(spec: spec_model.Spec) -> None:
    """Require escape actions to declare feature inputs."""
    for item in traversal.iter_actions(spec):
        if item.kind == functions.ESCAPE and (not item.inputs):
            raise errors.SpecError(
                "Escape actions must declare one or more input features",
                code="invalid_mapping_feature_inputs",
                path=(*item.location.path, "features", "inputs"),
            )


def validate_input_feature(spec: spec_model.Spec) -> None:
    """Require an explicit input feature to be declared."""
    feature_names = traversal.feature_names(spec)
    for item in traversal.iter_actions(spec):
        for feature in item.inputs:
            if feature not in feature_names:
                raise ValueError(
                    f"Action {item.location.action.id} references unknown input feature: {feature}"
                )


def validate_input_scope(spec: spec_model.Spec) -> None:
    """Require vectorize and write inputs to belong to the target dataset."""
    for item in traversal.iter_actions(spec):
        for feature in item.inputs:
            if (
                item.kind in {functions.VECTORIZE, functions.WRITE}
                and feature not in item.local_features
            ):
                raise ValueError(
                    f"Action {item.location.action.id} cannot read feature {feature} "
                    "from another dataset"
                )


def validate_feature_reference(spec: spec_model.Spec) -> None:
    """Require a structural feature reference to be declared."""
    feature_names = traversal.feature_names(spec)
    for item in traversal.iter_actions(spec):
        for feature in item.feature_selectors:
            if feature != selectors.CURRENT_ID and feature not in feature_names:
                raise ValueError(
                    f"Action {item.location.action.id} references unknown feature: {feature}"
                )


def validate_dataset_reference(spec: spec_model.Spec) -> None:
    """Require a structural dataset reference to be declared."""
    datasets_by_id = traversal.dataset_index(spec)
    for item in traversal.iter_actions(spec):
        for dataset in item.dataset_references:
            if dataset != selectors.CURRENT_ID and dataset not in datasets_by_id:
                raise ValueError(
                    f"Action {item.location.action.id} references unknown dataset: {dataset}"
                )


def validate_dimension_reference(spec: spec_model.Spec) -> None:
    """Require a structural dimension reference to be declared."""
    dimension_ids = frozenset(spec.dimensions)
    for item in traversal.iter_actions(spec):
        for dimension, path in item.dimension_reference_paths:
            if dimension not in dimension_ids:
                raise errors.SpecError(
                    f"Action {item.location.action.id} references unknown dimension: {dimension}",
                    code="unknown_dimension_reference",
                    path=path,
                )
