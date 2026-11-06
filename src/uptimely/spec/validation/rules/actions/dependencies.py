"""Action feature dependency cycle validation."""

import logging

from uptimely.spec import functions
from uptimely.spec import model as spec_model

logger = logging.getLogger(__name__)

type ActionKey = tuple[str, str]


def validate_action_cycle(spec: spec_model.Spec) -> None:
    """Reject cycles between feature-producing actions in declaration DFS order."""
    logger.debug("    - checking action feature dependencies are acyclic")
    producers: dict[str, ActionKey] = {}
    for key, operator in spec.operator_items:
        if spec.functions[operator.compute.function].kind == functions.WRITE:
            continue
        profile_id = spec.action_profile_keys[key]
        grain_keys = spec.grain_keys_by_profile[profile_id]
        action_key = key
        for feature in operator.output_features:
            if feature not in grain_keys and feature not in spec.grain_key_ids:
                producers[feature] = action_key

    dependencies: dict[ActionKey, tuple[ActionKey, ...]] = {}
    for key, operator in spec.operator_items:
        action_key = key
        dependencies[action_key] = tuple(
            dict.fromkeys(
                producers[feature] for feature in operator.input_features if feature in producers
            )
        )

    visiting: set[ActionKey] = set()
    visited: set[ActionKey] = set()

    def visit(key: ActionKey) -> ActionKey | None:
        if key in visiting:
            return key
        if key in visited:
            return None
        visiting.add(key)
        for dependency in dependencies[key]:
            cycle = visit(dependency)
            if cycle is not None:
                return cycle
        visiting.remove(key)
        visited.add(key)
        return None

    for key in dependencies:
        cycle = visit(key)
        if cycle is not None:
            raise ValueError(f"Action feature dependency cycle: {cycle[0]}.{cycle[1]}")
