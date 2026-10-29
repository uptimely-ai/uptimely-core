"""Atomic output declaration, ownership, and producer checks."""

from __future__ import annotations

import collections.abc

from uptimely.spec import model as spec_model

from .. import functions, selectors
from . import context as context_module
from . import errors

type OutputDeclaration = tuple[str, str | None]
type ActionOutputFacts = tuple[context_module.ActionFacts, tuple[OutputDeclaration, ...]]
type DatasetOutputFacts = tuple[
    context_module.DatasetLocation, tuple[ActionOutputFacts, ...], tuple[str, ...]
]


def iter_output_datasets(
    datasets: collections.abc.Iterable[context_module.DatasetLocation],
    actions: collections.abc.Iterable[context_module.ActionFacts],
) -> collections.abc.Iterator[DatasetOutputFacts]:
    """Yield action outputs and uncovered features for each dataset."""
    actions_by_key = {item.location.key: item for item in actions}
    for location in datasets:
        producers: dict[str, str] = {}
        output_actions: list[ActionOutputFacts] = []
        for action_id in location.dataset.actions:
            item = actions_by_key[(*location.key, action_id)]
            declarations: list[OutputDeclaration] = []
            if item.kind != functions.WRITE:
                for feature_id in item.outputs:
                    declarations.append((feature_id, producers.get(feature_id)))
                    if feature_id not in item.dimensions:
                        producers[feature_id] = item.location.action_id
            output_actions.append((item, tuple(declarations)))
        missing = tuple(
            sorted(set(location.dataset.features) - producers.keys() - location.dimensions)
        )
        yield location, tuple(output_actions), missing


def validate_output_presence(
    item: context_module.ActionFacts, action_id: str
) -> context_module.ValidationResult:
    """Require a producing action to declare at least one output."""
    if not item.outputs:
        return ValueError(f"Action {action_id} must declare one or more features")
    return None


def validate_calculation_features(
    item: context_module.ActionFacts,
) -> context_module.ValidationResult:
    """Require calculated outputs to be declared in the target dataset."""
    unknown = sorted(set(item.outputs) - item.location.dataset.features.keys())
    if unknown:
        return ValueError(
            f"Action {item.location.action.id} references unknown feature: " + ", ".join(unknown)
        )
    return None


def validate_function_id(item: context_module.ActionFacts) -> context_module.ValidationResult:
    """Require a calculation function ID to be nonempty."""
    if item.function is not None and not item.function.id.strip():
        return ValueError("Every function must define a non-empty string id")
    return None


def validate_output_names(item: context_module.ActionFacts) -> context_module.ValidationResult:
    """Require calculated output names to be nonempty."""
    if any(not feature.strip() for feature in item.outputs):
        return ValueError("Every calculation must define a non-empty output feature name")
    return None


def validate_feature_ownership(duplicate: str | None) -> context_module.ValidationResult:
    """Require a unique owner for each non-dimension feature."""
    if duplicate is not None:
        return ValueError(f"Duplicate feature name: {duplicate}")
    return None


def validate_dimension_collision(
    item: context_module.ActionFacts, dimension_ids: frozenset[str]
) -> context_module.ValidationResult:
    """Reject calculated feature names that collide with dimensions."""
    collisions = set(item.outputs) & dimension_ids
    if item.kind == functions.VECTORIZE and collisions:
        return ValueError(
            "Calculated feature names cannot duplicate entity dimensions: "
            + ", ".join(sorted(collisions))
        )
    return None


def validate_function_reference(
    function_id: str,
    dataset_id: str,
    function_catalog: collections.abc.Mapping[str, spec_model.FunctionTemplate],
    path: context_module.SpecPath,
) -> context_module.ValidationResult:
    """Require an action's function reference to resolve in the catalog."""
    if function_id not in function_catalog:
        return errors.SpecError(
            f"Dataset {dataset_id} actions reference unknown functions: {function_id}",
            code="unknown_function_reference",
            path=path,
        )
    return None


def validate_write_outputs(item: context_module.ActionFacts) -> context_module.ValidationResult:
    """Reject output features on a write action."""
    if item.outputs:
        return ValueError(f"Write action {item.location.action_id} cannot produce features")
    return None


def validate_output_feature(
    item: context_module.ActionFacts, feature: str
) -> context_module.ValidationResult:
    """Require an output feature to be declared in the target dataset."""
    if feature not in item.location.dataset.features:
        return ValueError(f"Action {item.location.action_id} references unknown feature: {feature}")
    return None


def validate_unique_producer(
    item: context_module.ActionFacts, feature: str, previous: str | None
) -> context_module.ValidationResult:
    """Reject multiple producers for a non-dimension feature."""
    if feature not in item.dimensions and previous is not None:
        return ValueError(
            f"Feature {feature} is produced by multiple actions: "
            f"{previous}, {item.location.action_id}"
        )
    return None


def validate_collapse_output(item: context_module.ActionFacts) -> context_module.ValidationResult:
    """Require collapse to produce a non-dimension feature."""
    if item.kind == functions.COLLAPSE and not set(item.outputs) - item.dimensions:
        return ValueError(
            f"Collapse action {item.location.action_id} must produce a non-dimension feature"
        )
    return None


def validate_current_feature_selector(
    item: context_module.ActionFacts,
) -> context_module.ValidationResult:
    """Reject ambiguous current-feature selectors on multi-output calculations."""
    if item.kind not in {functions.VECTORIZE, functions.COLLAPSE}:
        return None
    count = (
        len(set(item.outputs) - item.dimensions)
        if item.kind == functions.COLLAPSE
        else len(item.outputs)
    )
    if count > 1 and selectors.CURRENT_ID in item.feature_selectors:
        return ValueError(
            f"{item.kind.capitalize()} action {item.location.action_id} "
            "cannot use $features.@ when it produces multiple features"
        )
    return None
