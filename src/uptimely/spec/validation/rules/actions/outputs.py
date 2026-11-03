"""Atomic output declaration, ownership, and producer checks."""

import logging
import warnings

from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_output_presence(spec: spec_model.Spec) -> None:
    """Require feature-producing actions to declare outputs when their kind requires them."""
    logger.debug("    - checking required action outputs are declared")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if (
            function is not None
            and functions.FUNCTION_KINDS[function.kind].requires_feature_outputs
            and not action.output_features
        ):
            raise ValueError(f"Action {key[1]} must declare one or more features")


def validate_function_id(spec: spec_model.Spec) -> None:
    """Require a calculation function ID to be nonempty."""
    logger.debug("    - checking calculation function IDs are nonempty")
    for action in spec.actions:
        function = spec.functions.root.get(action.binding.function)
        if (
            function is not None
            and function.kind == functions.VECTORIZE
            and not function.id.strip()
        ):
            raise ValueError("Every function must define a non-empty string id")


def validate_output_names(spec: spec_model.Spec) -> None:
    """Require calculated output names to be nonempty."""
    logger.debug("    - checking calculated output names are nonempty")
    for action in spec.actions:
        function = spec.functions.root.get(action.binding.function)
        if (
            function is not None
            and function.kind == functions.VECTORIZE
            and any(not feature.strip() for feature in action.output_features)
        ):
            raise ValueError("Every calculation must define a non-empty output feature name")


def validate_dimension_collision(spec: spec_model.Spec) -> None:
    """Reject calculated feature names that collide with dimensions."""
    logger.debug("    - checking calculated outputs do not collide with dimensions")
    for action in spec.actions:
        function = spec.functions.root.get(action.binding.function)
        collisions = set(action.output_features) & spec.dimensions.keys()
        if function is not None and function.kind == functions.VECTORIZE and collisions:
            raise ValueError(
                "Calculated feature names cannot duplicate profile dimensions: "
                + ", ".join(sorted(collisions))
            )


def validate_function_reference(spec: spec_model.Spec) -> None:
    """Require an action's function reference to resolve in the catalog."""
    logger.debug("    - checking action function references")
    for key, action in spec.action_items:
        function_id = action.binding.function
        if function_id not in spec.functions:
            raise errors.SpecError(
                f"Profile {key[0]} actions reference unknown functions: {function_id}",
                code="unknown_function_reference",
                path=(*spec.declaration_paths[key], "binding", "function"),
            )


def validate_nonproducing_outputs(spec: spec_model.Spec) -> None:
    """Reject output feature declarations on kinds that do not support them."""
    logger.debug("    - checking nonproducing actions do not declare outputs")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if (
            function is not None
            and not functions.FUNCTION_KINDS[function.kind].produces_features
            and action.output_features
        ):
            raise ValueError(
                f"{function.kind.capitalize()} action {key[1]} cannot produce features"
            )


def validate_output_feature(spec: spec_model.Spec) -> None:
    """Require an output feature to be declared in the target dataset."""
    logger.debug("    - checking action outputs are declared in the target dataset")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None or not functions.FUNCTION_KINDS[function.kind].produces_features:
            continue
        for feature in action.output_features:
            if feature not in spec.profiles_by_key[key[0]].features:
                raise ValueError(f"Action {key[1]} references unknown feature: {feature}")


def validate_unique_producer(spec: spec_model.Spec) -> None:
    """Reject multiple producers for a non-dimension feature in declaration order."""
    logger.debug("    - checking unique producers for non-dimension features")
    producers: dict[tuple[spec_model.ProfileKey, str], str] = {}
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None or not functions.FUNCTION_KINDS[function.kind].produces_features:
            continue
        for feature in action.output_features:
            if feature in spec.dimensions_by_profile[key[0]]:
                continue
            producer_key = (key[0], feature)
            previous = producers.get(producer_key)
            if previous is not None:
                raise ValueError(
                    f"Feature {feature} is produced by multiple actions: {previous}, {key[1]}"
                )
            producers[producer_key] = key[1]


def validate_collapse_output(spec: spec_model.Spec) -> None:
    """Require collapse to produce a non-dimension feature."""
    logger.debug("    - checking collapse actions produce non-dimension features")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if (
            function is not None
            and function.kind == functions.COLLAPSE
            and not (set(action.output_features) - spec.dimensions_by_profile[key[0]])
        ):
            raise ValueError(f"Collapse action {key[1]} must produce a non-dimension feature")


def validate_current_feature_selector(spec: spec_model.Spec) -> None:
    """Reject ambiguous current-feature selectors on multi-output calculations."""
    logger.debug("    - checking current-feature selectors are unambiguous")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None or function.kind not in {functions.VECTORIZE, functions.COLLAPSE}:
            continue
        count = (
            len(set(action.output_features) - spec.dimensions_by_profile[key[0]])
            if function.kind == functions.COLLAPSE
            else len(action.output_features)
        )
        if count > 1 and selectors.CURRENT_ID in action.feature_selectors:
            raise ValueError(
                f"{function.kind.capitalize()} action {key[1]} "
                "cannot use $features.@ when it produces multiple features"
            )


def warn_unproduced_features(spec: spec_model.Spec) -> None:
    """Warn when declared dataset features have no action producer."""
    logger.debug("    - checking declared features have producers (warning only)")
    for key, profile in spec.profile_items:
        produced = {
            feature
            for feature, producers in profile.feature_producers.items()
            if any(
                (function := spec.functions.root.get(action.binding.function)) is not None
                and functions.FUNCTION_KINDS[function.kind].produces_features
                for _, action in producers
            )
        }
        missing = sorted(profile.features.keys() - produced - spec.dimensions_by_profile[key])
        if missing:
            warnings.warn(
                f"profiles.{key}.features: Features have no producer action: " + ", ".join(missing),
                UserWarning,
                stacklevel=2,
            )
