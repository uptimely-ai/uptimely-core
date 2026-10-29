"""Atomic collapse source inference and source scope checks."""

from __future__ import annotations

import dataclasses
import typing

from .. import functions, selectors
from . import context as context_module


@dataclasses.dataclass(frozen=True)
class CollapseInputs:
    """Ordered source candidates, including unresolved or ambiguous inputs."""

    action: context_module.ActionFacts
    candidates: tuple[tuple[str, tuple[context_module.DatasetLocation, ...]], ...]
    source: context_module.DatasetLocation | None


def iter_collapse_inputs(
    actions: typing.Iterable[context_module.ActionFacts],
    dimension_ids: frozenset[str],
    feature_owners: dict[str, tuple[context_module.DatasetLocation, ...]],
) -> typing.Iterator[CollapseInputs]:
    """Prepare source facts for collapse actions from shared declaration indexes."""
    for action in actions:
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
            if len(sources) == 1 and all(len(owners) == 1 for _, owners in candidates)
            else None
        )
        yield CollapseInputs(
            action=action,
            candidates=candidates,
            source=source,
        )


def source_index(
    items: typing.Iterable[CollapseInputs],
) -> dict[tuple[str, str, str], context_module.DatasetLocation]:
    """Index resolved collapse sources by action declaration identity."""
    return {item.action.location.key: item.source for item in items if item.source is not None}


def validate_source_feature(item: CollapseInputs) -> context_module.ValidationResult:
    """Require collapse to reference a source feature."""
    if not item.candidates:
        return ValueError(
            f"Collapse {item.action.location.action.id} must reference a source feature"
        )
    return None


def validate_feature_owner(
    action_id: str, feature: str, owners: tuple[context_module.DatasetLocation, ...]
) -> context_module.ValidationResult:
    """Require a collapse source feature to have exactly one owner."""
    if not owners:
        return ValueError(f"Collapse {action_id} references unknown input feature: {feature}")
    if len(owners) != 1:
        return ValueError(f"Collapse {action_id} has ambiguous input feature: {feature}")
    return None


def validate_source_count(item: CollapseInputs) -> context_module.ValidationResult:
    """Require all collapse source features to belong to one dataset."""
    source_ids = {owners[0].dataset.id for _, owners in item.candidates if len(owners) == 1}
    if len(source_ids) != 1:
        return ValueError(
            f"Collapse {item.action.location.action.id} input features must belong to one "
            "dataset; use expand to combine inputs from different datasets"
        )
    return None


def validate_source_target(item: CollapseInputs) -> context_module.ValidationResult:
    """Reject the target dataset as a collapse source."""
    if item.source is not None and item.source.dataset.id == item.action.location.dataset.id:
        return ValueError(
            f"Collapse {item.action.location.action.id} cannot use its target dataset as source"
        )
    return None


def validate_grouping_dimensions(
    item: CollapseInputs,
) -> context_module.ValidationResult:
    """Require grouping dimensions to exist in the collapse source."""
    if item.source is not None and not item.action.dimensions.issubset(item.source.dimensions):
        return ValueError(
            f"Collapse {item.action.location.action.id} grouping dimensions must exist in "
            f"source {item.source.dataset.id}"
        )
    return None


def validate_source_features(
    item: CollapseInputs,
) -> context_module.ValidationResult:
    """Require collapse input features to belong to its source."""
    source_features = (
        frozenset(item.source.dataset.features) | item.source.dimensions
        if item.source is not None
        else frozenset()
    )
    unknown = sorted(set(item.action.inputs) - source_features)
    if item.source is not None and unknown:
        return ValueError(
            f"Collapse {item.action.location.action.id} references features outside source "
            f"{item.source.dataset.id}: " + ", ".join(unknown)
        )
    return None


def validate_source_dimensions(
    item: CollapseInputs, dimension_ids: frozenset[str]
) -> context_module.ValidationResult:
    """Require structural dimension references to belong to the source."""
    unknown = sorted(
        (set(item.action.dimension_references) & dimension_ids)
        - (item.source.dimensions if item.source is not None else frozenset())
    )
    if unknown:
        return ValueError(
            f"Collapse {item.action.location.action.id} references unknown source dimensions: "
            + ", ".join(unknown)
        )
    return None
