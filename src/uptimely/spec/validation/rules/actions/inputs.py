"""Atomic action input, reference, and source scope checks."""

from __future__ import annotations

import collections.abc
import dataclasses

from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors
from uptimely.spec.validation.rules import actions as action_rules
from uptimely.spec.validation.rules import datasets as dataset_rules
from uptimely.spec.validation.rules import features as feature_rules


@dataclasses.dataclass(frozen=True)
class InputSource:
    """Ordered source candidates, including unresolved or ambiguous inputs."""

    action: action_rules.ActionDeclaration
    candidates: tuple[tuple[str, tuple[dataset_rules.DatasetDeclaration, ...]], ...]
    source: dataset_rules.DatasetDeclaration | None


def iter_input_sources(spec: spec_model.Spec) -> collections.abc.Iterator[InputSource]:
    """Yield every action's input feature owners, retaining ambiguous declarations."""
    dimension_ids = frozenset(spec.dimensions)
    feature_owners = feature_rules.feature_owners(spec)
    for action in action_rules.iter_actions(spec):
        candidates = tuple(
            (feature_id, feature_owners.get(feature_id, ()))
            for feature_id in action.inputs
            if feature_id != selectors.CURRENT_ID and feature_id not in dimension_ids
        )
        sources = {owners[0].dataset.id: owners[0] for _, owners in candidates if len(owners) == 1}
        source = (
            next(iter(sources.values()))
            if len(sources) == 1 and all((len(owners) == 1 for _, owners in candidates))
            else None
        )
        yield InputSource(action=action, candidates=candidates, source=source)


def validate_source_feature(spec: spec_model.Spec) -> None:
    """Require collapse to reference a source feature."""
    for item in iter_input_sources(spec):
        if item.action.kind == functions.COLLAPSE and not item.candidates:
            raise ValueError(f"Collapse {item.action.action.id} must reference a source feature")


def validate_feature_owner(spec: spec_model.Spec) -> None:
    """Require a collapse source feature to have exactly one owner."""
    for item in iter_input_sources(spec):
        if item.action.kind != functions.COLLAPSE:
            continue
        action_id = item.action.action.id
        for feature, owners in item.candidates:
            if not owners:
                raise ValueError(
                    f"Collapse {action_id} references unknown input feature: {feature}"
                )
            if len(owners) != 1:
                raise ValueError(f"Collapse {action_id} has ambiguous input feature: {feature}")


def validate_source_count(spec: spec_model.Spec) -> None:
    """Require all collapse source features to belong to one dataset."""
    for item in iter_input_sources(spec):
        if item.action.kind != functions.COLLAPSE:
            continue
        source_ids = {owners[0].dataset.id for _, owners in item.candidates if len(owners) == 1}
        if len(source_ids) != 1:
            raise ValueError(
                f"Collapse {item.action.action.id} input features must belong to one "
                "dataset; use expand to combine inputs from different datasets"
            )


def validate_source_target(spec: spec_model.Spec) -> None:
    """Reject the target dataset as a collapse source."""
    for item in iter_input_sources(spec):
        if item.action.kind != functions.COLLAPSE:
            continue
        if item.source is not None and item.source.dataset.id == item.action.dataset.id:
            raise ValueError(
                f"Collapse {item.action.action.id} cannot use its target dataset as source"
            )


def validate_grouping_dimensions(spec: spec_model.Spec) -> None:
    """Require grouping dimensions to exist in the collapse source."""
    for item in iter_input_sources(spec):
        if item.action.kind != functions.COLLAPSE:
            continue
        if item.source is not None and (
            not item.action.dimensions.issubset(item.source.dimensions)
        ):
            raise ValueError(
                f"Collapse {item.action.action.id} grouping dimensions must exist in "
                f"source {item.source.dataset.id}"
            )


def validate_source_features(spec: spec_model.Spec) -> None:
    """Require collapse input features to belong to its source."""
    for item in iter_input_sources(spec):
        if item.action.kind != functions.COLLAPSE:
            continue
        source_features = (
            frozenset(item.source.dataset.features) | item.source.dimensions
            if item.source is not None
            else frozenset()
        )
        unknown = sorted(set(item.action.inputs) - source_features)
        if item.source is not None and unknown:
            raise ValueError(
                f"Collapse {item.action.action.id} references features outside source "
                f"{item.source.dataset.id}: " + ", ".join(unknown)
            )


def validate_source_dimensions(spec: spec_model.Spec) -> None:
    """Require structural dimension references to belong to the source."""
    dimension_ids = frozenset(spec.dimensions)
    for item in iter_input_sources(spec):
        if item.action.kind != functions.COLLAPSE:
            continue
        unknown = sorted(
            (set(item.action.dimension_references) & dimension_ids)
            - (item.source.dimensions if item.source is not None else frozenset())
        )
        if unknown:
            raise ValueError(
                f"Collapse {item.action.action.id} references unknown source dimensions: "
                + ", ".join(unknown)
            )


def validate_escape_inputs(spec: spec_model.Spec) -> None:
    """Require escape actions to declare feature inputs."""
    for item in action_rules.iter_actions(spec):
        if item.kind == functions.ESCAPE and not item.inputs:
            raise errors.SpecError(
                "Escape actions must declare one or more input features",
                code="invalid_mapping_feature_inputs",
                path=(*item.path, "features", "inputs"),
            )


def validate_input_feature(spec: spec_model.Spec) -> None:
    """Require an explicit input feature to be declared."""
    feature_names = spec.dimensions.keys() | feature_rules.feature_owners(spec).keys()
    for item in action_rules.iter_actions(spec):
        for feature in item.inputs:
            if feature not in feature_names:
                raise ValueError(
                    f"Action {item.action.id} references unknown input feature: {feature}"
                )


def validate_input_scope(spec: spec_model.Spec) -> None:
    """Require vectorize and write inputs to belong to the target dataset."""
    for item in action_rules.iter_actions(spec):
        for feature in item.inputs:
            if (
                item.kind in {functions.VECTORIZE, functions.WRITE}
                and feature not in item.local_features
            ):
                raise ValueError(
                    f"Action {item.action.id} cannot read feature {feature} from another dataset"
                )


def validate_feature_reference(spec: spec_model.Spec) -> None:
    """Require a structural feature reference to be declared."""
    feature_names = spec.dimensions.keys() | feature_rules.feature_owners(spec).keys()
    for item in action_rules.iter_actions(spec):
        for feature in item.feature_selectors:
            if feature != selectors.CURRENT_ID and feature not in feature_names:
                raise ValueError(f"Action {item.action.id} references unknown feature: {feature}")


def validate_dataset_reference(spec: spec_model.Spec) -> None:
    """Require a structural dataset reference to be declared."""
    dataset_ids = {item.dataset.id for item in dataset_rules.iter_datasets(spec)}
    for item in action_rules.iter_actions(spec):
        for dataset in item.dataset_references:
            if dataset != selectors.CURRENT_ID and dataset not in dataset_ids:
                raise ValueError(f"Action {item.action.id} references unknown dataset: {dataset}")


def validate_dimension_reference(spec: spec_model.Spec) -> None:
    """Require a structural dimension reference to be declared."""
    dimension_ids = frozenset(spec.dimensions)
    for item in action_rules.iter_actions(spec):
        for dimension, path in item.dimension_reference_paths:
            if dimension not in dimension_ids:
                raise errors.SpecError(
                    f"Action {item.action.id} references unknown dimension: {dimension}",
                    code="unknown_dimension_reference",
                    path=path,
                )
