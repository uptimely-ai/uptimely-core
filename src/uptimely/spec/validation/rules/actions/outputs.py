"""Atomic output declaration, ownership, and producer checks."""

from __future__ import annotations

import collections.abc
import warnings

from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors
from uptimely.spec.validation.rules import actions as action_rules
from uptimely.spec.validation.rules import datasets as dataset_rules

type OutputDeclaration = tuple[str, str | None]
type ActionOutputFacts = tuple[action_rules.ActionDeclaration, tuple[OutputDeclaration, ...]]
type DatasetOutputFacts = tuple[
    dataset_rules.DatasetDeclaration, tuple[ActionOutputFacts, ...], tuple[str, ...]
]


def iter_output_datasets(spec: spec_model.Spec) -> collections.abc.Iterator[DatasetOutputFacts]:
    """Yield action outputs and uncovered features for each dataset."""
    actions_by_key = {item.key: item for item in action_rules.iter_actions(spec)}
    for location in dataset_rules.iter_datasets(spec):
        producers: dict[str, str] = {}
        output_actions: list[ActionOutputFacts] = []
        for action_id in location.dataset.actions:
            item = actions_by_key[*location.key, action_id]
            declarations: list[OutputDeclaration] = []
            if item.kind != functions.WRITE:
                for feature_id in item.outputs:
                    declarations.append((feature_id, producers.get(feature_id)))
                    if feature_id not in item.dimensions:
                        producers[feature_id] = item.action_id
            output_actions.append((item, tuple(declarations)))
        missing = tuple(
            sorted(set(location.dataset.features) - producers.keys() - location.dimensions)
        )
        yield (location, tuple(output_actions), missing)


def validate_output_presence(spec: spec_model.Spec) -> None:
    """Require a producing action to declare at least one output."""
    for item in action_rules.iter_actions(spec):
        if item.kind == functions.WRITE:
            continue
        action_id = item.action_id
        if not item.outputs:
            raise ValueError(f"Action {action_id} must declare one or more features")


def validate_function_id(spec: spec_model.Spec) -> None:
    """Require a calculation function ID to be nonempty."""
    for item in action_rules.iter_actions(spec):
        if item.kind != functions.VECTORIZE:
            continue
        if item.function is not None and (not item.function.id.strip()):
            raise ValueError("Every function must define a non-empty string id")


def validate_output_names(spec: spec_model.Spec) -> None:
    """Require calculated output names to be nonempty."""
    for item in action_rules.iter_actions(spec):
        if item.kind != functions.VECTORIZE:
            continue
        if any(not feature.strip() for feature in item.outputs):
            raise ValueError("Every calculation must define a non-empty output feature name")


def validate_dimension_collision(spec: spec_model.Spec) -> None:
    """Reject calculated feature names that collide with dimensions."""
    dimension_ids = frozenset(spec.dimensions)
    for item in action_rules.iter_actions(spec):
        collisions = set(item.outputs) & dimension_ids
        if item.kind == functions.VECTORIZE and collisions:
            raise ValueError(
                "Calculated feature names cannot duplicate entity dimensions: "
                + ", ".join(sorted(collisions))
            )


def validate_function_reference(spec: spec_model.Spec) -> None:
    """Require an action's function reference to resolve in the catalog."""
    function_catalog = spec.functions.root
    for item in action_rules.iter_actions(spec):
        function_id = item.action.binding.function
        dataset_id = item.dataset.id
        path = (*item.declaration_path, "binding", "function")
        if function_id not in function_catalog:
            raise errors.SpecError(
                f"Dataset {dataset_id} actions reference unknown functions: {function_id}",
                code="unknown_function_reference",
                path=path,
            )


def validate_write_outputs(spec: spec_model.Spec) -> None:
    """Reject output features on a write action."""
    for item in action_rules.iter_actions(spec):
        if item.kind != functions.WRITE:
            continue
        if item.outputs:
            raise ValueError(f"Write action {item.action_id} cannot produce features")


def validate_output_feature(spec: spec_model.Spec) -> None:
    """Require an output feature to be declared in the target dataset."""
    for item in action_rules.iter_actions(spec):
        if item.kind == functions.WRITE:
            continue
        for feature in item.outputs:
            if feature not in item.dataset.features:
                raise ValueError(f"Action {item.action_id} references unknown feature: {feature}")


def validate_unique_producer(spec: spec_model.Spec) -> None:
    """Reject multiple producers for a non-dimension feature."""
    for _, output_actions, _ in iter_output_datasets(spec):
        for item, declarations in output_actions:
            if item.kind == functions.WRITE:
                continue
            for feature, previous in declarations:
                if feature not in item.dimensions and previous is not None:
                    raise ValueError(
                        f"Feature {feature} is produced by multiple actions: "
                        f"{previous}, {item.action_id}"
                    )


def validate_collapse_output(spec: spec_model.Spec) -> None:
    """Require collapse to produce a non-dimension feature."""
    for item in action_rules.iter_actions(spec):
        if item.kind == functions.COLLAPSE and (not set(item.outputs) - item.dimensions):
            raise ValueError(
                f"Collapse action {item.action_id} must produce a non-dimension feature"
            )


def validate_current_feature_selector(spec: spec_model.Spec) -> None:
    """Reject ambiguous current-feature selectors on multi-output calculations."""
    for item in action_rules.iter_actions(spec):
        if item.kind not in {functions.VECTORIZE, functions.COLLAPSE}:
            continue
        count = (
            len(set(item.outputs) - item.dimensions)
            if item.kind == functions.COLLAPSE
            else len(item.outputs)
        )
        if count > 1 and selectors.CURRENT_ID in item.feature_selectors:
            raise ValueError(
                f"{item.kind.capitalize()} action {item.action_id} "
                "cannot use $features.@ when it produces multiple features"
            )


def warn_unproduced_features(spec: spec_model.Spec) -> None:
    """Warn when declared dataset features have no action producer."""
    for location, _, missing in iter_output_datasets(spec):
        if missing:
            feature_path = ".".join((*location.path, "features"))
            warnings.warn(
                f"{feature_path}: Features have no producer action: {', '.join(missing)}",
                UserWarning,
                stacklevel=2,
            )
