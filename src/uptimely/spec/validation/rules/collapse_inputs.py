"""Atomic collapse source inference and source scope checks."""

from __future__ import annotations

import dataclasses
import typing

from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model

from .. import traversal


@dataclasses.dataclass(frozen=True)
class CollapseInputs:
    """Ordered source candidates, including unresolved or ambiguous inputs."""

    action: traversal.ActionFacts
    candidates: tuple[tuple[str, tuple[traversal.DatasetLocation, ...]], ...]
    source: traversal.DatasetLocation | None


def iter_collapse_inputs(spec: spec_model.Spec) -> typing.Iterator[CollapseInputs]:
    """Yield collapse source candidates from the current declarations."""
    dimension_ids = frozenset(spec.dimensions)
    feature_owners = traversal.feature_owners(spec)
    for action in traversal.iter_actions(spec):
        if action.kind != functions.COLLAPSE:
            continue
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
        yield CollapseInputs(action=action, candidates=candidates, source=source)


def source_index(
    items: typing.Iterable[CollapseInputs],
) -> dict[tuple[str, str, str], traversal.DatasetLocation]:
    """Index resolved collapse sources by action declaration identity."""
    return {item.action.location.key: item.source for item in items if item.source is not None}


def validate_source_feature(spec: spec_model.Spec) -> None:
    """Require collapse to reference a source feature."""
    for item in iter_collapse_inputs(spec):
        if not item.candidates:
            raise ValueError(
                f"Collapse {item.action.location.action.id} must reference a source feature"
            )


def validate_feature_owner(spec: spec_model.Spec) -> None:
    """Require a collapse source feature to have exactly one owner."""
    for item in iter_collapse_inputs(spec):
        action_id = item.action.location.action.id
        for feature, owners in item.candidates:
            if not owners:
                raise ValueError(
                    f"Collapse {action_id} references unknown input feature: {feature}"
                )
            if len(owners) != 1:
                raise ValueError(f"Collapse {action_id} has ambiguous input feature: {feature}")


def validate_source_count(spec: spec_model.Spec) -> None:
    """Require all collapse source features to belong to one dataset."""
    for item in iter_collapse_inputs(spec):
        source_ids = {owners[0].dataset.id for _, owners in item.candidates if len(owners) == 1}
        if len(source_ids) != 1:
            raise ValueError(
                f"Collapse {item.action.location.action.id} input features must belong to one "
                "dataset; use expand to combine inputs from different datasets"
            )


def validate_source_target(spec: spec_model.Spec) -> None:
    """Reject the target dataset as a collapse source."""
    for item in iter_collapse_inputs(spec):
        if item.source is not None and item.source.dataset.id == item.action.location.dataset.id:
            raise ValueError(
                f"Collapse {item.action.location.action.id} cannot use its target dataset as source"
            )


def validate_grouping_dimensions(spec: spec_model.Spec) -> None:
    """Require grouping dimensions to exist in the collapse source."""
    for item in iter_collapse_inputs(spec):
        if item.source is not None and (
            not item.action.dimensions.issubset(item.source.dimensions)
        ):
            raise ValueError(
                f"Collapse {item.action.location.action.id} grouping dimensions must exist in "
                f"source {item.source.dataset.id}"
            )


def validate_source_features(spec: spec_model.Spec) -> None:
    """Require collapse input features to belong to its source."""
    for item in iter_collapse_inputs(spec):
        source_features = (
            frozenset(item.source.dataset.features) | item.source.dimensions
            if item.source is not None
            else frozenset()
        )
        unknown = sorted(set(item.action.inputs) - source_features)
        if item.source is not None and unknown:
            raise ValueError(
                f"Collapse {item.action.location.action.id} references features outside source "
                f"{item.source.dataset.id}: " + ", ".join(unknown)
            )


def validate_source_dimensions(spec: spec_model.Spec) -> None:
    """Require structural dimension references to belong to the source."""
    dimension_ids = frozenset(spec.dimensions)
    for item in iter_collapse_inputs(spec):
        unknown = sorted(
            (set(item.action.dimension_references) & dimension_ids)
            - (item.source.dimensions if item.source is not None else frozenset())
        )
        if unknown:
            raise ValueError(
                f"Collapse {item.action.location.action.id} references unknown source dimensions: "
                + ", ".join(unknown)
            )
