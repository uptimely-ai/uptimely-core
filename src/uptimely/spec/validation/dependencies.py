"""Action feature dependency graph traversal and cycle validation."""

from __future__ import annotations

import collections.abc

from uptimely.spec import functions
from uptimely.spec import model as spec_model

from . import traversal


def feature_producers(
    actions: collections.abc.Iterable[traversal.ActionFacts], dimension_ids: frozenset[str]
) -> dict[str, traversal.ActionKey]:
    """Build the action dependency producer index independently of output validity."""
    return {
        feature_id: (item.location.dataset.id, item.location.action_id)
        for item in actions
        if item.kind != functions.WRITE
        for feature_id in item.outputs
        if feature_id not in item.dimensions and feature_id not in dimension_ids
    }


def find_action_cycle(
    actions: collections.abc.Iterable[traversal.ActionFacts],
    producers: collections.abc.Mapping[str, traversal.ActionKey],
) -> traversal.ActionKey | None:
    """Find the first active dependency reached by the established DFS order."""
    action_dependencies = {
        (item.location.dataset.id, item.location.action_id): tuple(
            dict.fromkeys(
                producers[feature_id] for feature_id in item.inputs if feature_id in producers
            )
        )
        for item in actions
    }
    visiting: set[traversal.ActionKey] = set()
    visited: set[traversal.ActionKey] = set()

    def visit(key: traversal.ActionKey) -> traversal.ActionKey | None:
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


def validate_action_cycle(spec: spec_model.Spec) -> None:
    """Reject cycles between feature-producing actions.

    Requires unique dataset IDs, feature owners, and producers, and valid
    action function, input, and output references.
    """
    actions = tuple(traversal.iter_actions(spec))
    cycle = find_action_cycle(actions, feature_producers(actions, frozenset(spec.dimensions)))
    if cycle is not None:
        raise ValueError(f"Action feature dependency cycle: {cycle[0]}.{cycle[1]}")
