"""Operator feature dependency cycle validation."""

import logging

from uptimely.spec import function_kinds as functions
from uptimely.spec import model as spec_model

logger = logging.getLogger(__name__)

type OperatorKey = tuple[str, str]


def validate_operator_cycle(spec: spec_model.Spec) -> None:
    """Reject cycles between feature-producing operators in declaration DFS order."""
    logger.debug("    - checking operator feature dependencies are acyclic")
    producers: dict[str, OperatorKey] = {}
    for key, operator in spec.operator_items:
        if spec.functions[operator.compute.function].kind == functions.WRITE:
            continue
        profile_id = spec.operator_profile_keys[key]
        grain_keys = spec.grain_keys_by_profile[profile_id]
        operator_key = key
        for feature in operator.output_features:
            if feature not in grain_keys and feature not in spec.grain_key_ids:
                producers[feature] = operator_key

    dependencies: dict[OperatorKey, tuple[OperatorKey, ...]] = {}
    for key, operator in spec.operator_items:
        operator_key = key
        dependencies[operator_key] = tuple(
            dict.fromkeys(
                producers[feature] for feature in operator.input_features if feature in producers
            )
        )

    visiting: set[OperatorKey] = set()
    visited: set[OperatorKey] = set()

    def visit(key: OperatorKey) -> OperatorKey | None:
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
            raise ValueError(f"Operator feature dependency cycle: {cycle[0]}.{cycle[1]}")
