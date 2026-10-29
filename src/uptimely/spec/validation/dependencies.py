"""Atomic local dependency scope and action-cycle checks."""

from __future__ import annotations

import collections.abc

from .. import functions
from . import context as context_module


def iter_calculation_dependencies(
    actions: collections.abc.Iterable[context_module.ActionFacts],
    first_feature_owner: collections.abc.Callable[[str], context_module.DatasetLocation | None],
) -> collections.abc.Iterator[
    tuple[context_module.ActionFacts, str, context_module.DatasetLocation | None]
]:
    """Yield vectorize input owners in action and input declaration order."""
    for item in actions:
        if item.kind == functions.VECTORIZE:
            for feature_id in item.inputs:
                yield item, feature_id, first_feature_owner(feature_id)


def iter_write_dependencies(
    actions: collections.abc.Iterable[context_module.ActionFacts],
    first_feature_owner: collections.abc.Callable[[str], context_module.DatasetLocation | None],
) -> collections.abc.Iterator[tuple[context_module.ActionFacts, tuple[str, ...]]]:
    """Yield foreign write inputs using first-owner lookup."""
    for item in actions:
        if item.kind == functions.WRITE:
            foreign = tuple(
                sorted(
                    feature_id
                    for feature_id in set(item.inputs) - item.dimensions
                    if (owner := first_feature_owner(feature_id)) is None
                    or owner.key != (item.location.entity_id, item.location.dataset.id)
                )
            )
            yield item, foreign


def feature_producers(
    actions: collections.abc.Iterable[context_module.ActionFacts],
    dimension_ids: frozenset[str],
) -> dict[str, context_module.ActionKey]:
    """Build the action dependency producer index independently of output validity."""
    return {
        feature_id: (item.location.dataset.id, item.location.action_id)
        for item in actions
        if item.kind != functions.WRITE
        for feature_id in item.outputs
        if feature_id not in item.dimensions and feature_id not in dimension_ids
    }


def find_action_cycle(
    actions: collections.abc.Iterable[context_module.ActionFacts],
    producers: collections.abc.Mapping[str, context_module.ActionKey],
) -> context_module.ActionKey | None:
    """Find the first active dependency reached by the established DFS order."""
    action_dependencies = {
        (item.location.dataset.id, item.location.action.id): {
            producers[feature_id] for feature_id in item.inputs if feature_id in producers
        }
        for item in actions
    }
    visiting: set[context_module.ActionKey] = set()
    visited: set[context_module.ActionKey] = set()

    def visit(key: context_module.ActionKey) -> context_module.ActionKey | None:
        if key in visiting:
            return key
        if key in visited:
            return None
        visiting.add(key)
        for dependency in action_dependencies[key]:
            cycle = visit(dependency)
            if cycle is not None:
                return cycle
        visiting.remove(key)
        visited.add(key)
        return None

    for key in action_dependencies:
        cycle = visit(key)
        if cycle is not None:
            return cycle
    return None


def validate_calculation_dependency(
    item: context_module.ActionFacts,
    feature: str,
    owner: context_module.DatasetLocation | None,
) -> context_module.ValidationResult:
    """Require a vectorize input owner to match the target dataset."""
    action_name = item.outputs[0] if item.outputs else item.location.action_id
    if owner is not None and owner.key != item.location.key[:2]:
        return ValueError(
            f"Calculation {action_name} cannot read feature {feature} "
            "from another dataset; use a source resource "
            "operation to transfer features between datasets"
        )
    return None


def validate_write_dependencies(
    item: context_module.ActionFacts, foreign: tuple[str, ...]
) -> context_module.ValidationResult:
    """Require write inputs to belong to their target dataset."""
    if foreign:
        return ValueError(
            f"Write action {item.location.action.id} cannot read features from "
            "another dataset: " + ", ".join(foreign)
        )
    return None


def validate_action_cycle(
    cycle: context_module.ActionKey | None,
) -> context_module.ValidationResult:
    """Reject a prepared action dependency cycle."""
    if cycle is not None:
        return ValueError(f"Action feature dependency cycle: {cycle[0]}.{cycle[1]}")
    return None
