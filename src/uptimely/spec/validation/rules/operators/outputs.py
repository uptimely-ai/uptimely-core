"""Atomic output declaration, ownership, and producer checks."""

import logging
import warnings

from uptimely.spec import model as spec_model
from uptimely.spec import operator_kinds as functions
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_output_presence(spec: spec_model.Spec) -> None:
    """Require feature-producing operators to declare required outputs."""
    logger.debug("Check required operator outputs are declared")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is not None
            and functions.OPERATOR_KINDS[spec.operator_kinds[key]].requires_feature_outputs
            and not operator.output_features
        ):
            raise ValueError(f"Operator {key[1]} must declare one or more features")


def validate_function_id(spec: spec_model.Spec) -> None:
    """Require a calculation function ID to be nonempty."""
    logger.debug("Check calculation function IDs are nonempty")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is not None
            and spec.operator_kinds[key] == functions.VECTORIZE
            and not function.id.strip()
        ):
            raise ValueError("Every function must define a non-empty string id")


def validate_output_names(spec: spec_model.Spec) -> None:
    """Require calculated output names to be nonempty."""
    logger.debug("Check calculated output names are nonempty")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is not None
            and spec.operator_kinds[key] == functions.VECTORIZE
            and any(not feature.strip() for feature in operator.output_features)
        ):
            raise ValueError("Every calculation must define a non-empty output feature name")


def validate_dimension_collision(spec: spec_model.Spec) -> None:
    """Reject calculated feature names that collide with selected grain keys."""
    logger.debug("Check calculated outputs do not collide with dimensions")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        collisions = set(operator.output_features) & spec.grain_key_ids
        if function is not None and spec.operator_kinds[key] == functions.VECTORIZE and collisions:
            raise ValueError(
                "Calculated feature names cannot duplicate profile grain keys: "
                + ", ".join(sorted(collisions))
            )


def validate_compute_function_exists(spec: spec_model.Spec) -> None:
    """Require compute function references to resolve."""
    logger.debug("Check compute functions exist")
    for key, operator in spec.operator_items:
        profile_id, _ = key
        function_id = operator.compute.function
        if function_id not in spec.functions.root:
            raise errors.SpecError(
                f"Profile {profile_id} operators reference unknown functions: {function_id}",
                code="unknown_function_reference",
                path=(*spec.declaration_paths[key], "compute", "function"),
            )


def validate_merge_function_exists(spec: spec_model.Spec) -> None:
    """Require declared merge function references to resolve."""
    logger.debug("Check merge functions exist")
    for key, operator in spec.operator_items:
        if operator.merge is None:
            continue
        profile_id, _ = key
        function_id = operator.merge.function
        if function_id not in spec.functions.root:
            raise errors.SpecError(
                f"Profile {profile_id} operators reference unknown functions: {function_id}",
                code="unknown_function_reference",
                path=(*spec.declaration_paths[key], "merge", "function"),
            )


def validate_nonproducing_outputs(spec: spec_model.Spec) -> None:
    """Reject output feature declarations on kinds that do not support them."""
    logger.debug("Check nonproducing operator do not declare outputs")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is not None
            and not functions.OPERATOR_KINDS[spec.operator_kinds[key]].produces_features
            and operator.output_features
        ):
            raise ValueError(
                f"{spec.operator_kinds[key].capitalize()} operator {key[1]} cannot produce features"
            )


def validate_output_feature(spec: spec_model.Spec) -> None:
    """Require an output feature to be declared in the target profile."""
    logger.debug("Check operator outputs are declared in the target profile")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is None
            or not functions.OPERATOR_KINDS[spec.operator_kinds[key]].produces_features
        ):
            continue
        for feature in operator.output_features:
            if (
                feature not in spec.profiles_by_key[key[0]].features
                and feature not in spec.grain_keys_by_profile[key[0]]
            ):
                raise ValueError(f"Operator {key[1]} references unknown feature: {feature}")


def validate_unique_producer(spec: spec_model.Spec) -> None:
    """Reject multiple producers for a non-dimension feature in declaration order."""
    logger.debug("Check unique producers for non-dimension features")
    producers: dict[tuple[spec_model.ProfileKey, str], str] = {}
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is None
            or not functions.OPERATOR_KINDS[spec.operator_kinds[key]].produces_features
        ):
            continue
        for feature in operator.output_features:
            if feature in spec.grain_keys_by_profile[key[0]]:
                continue
            producer_key = (key[0], feature)
            previous = producers.get(producer_key)
            if previous is not None:
                raise ValueError(
                    f"Feature {feature} is produced by multiple operators: {previous}, {key[1]}"
                )
            producers[producer_key] = key[1]


def validate_collapse_output(spec: spec_model.Spec) -> None:
    """Require collapse to produce a non-dimension feature."""
    logger.debug("Check collapse operator produce non-dimension features")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is not None
            and spec.operator_kinds[key] == functions.COLLAPSE
            and not (set(operator.output_features) - set(spec.grain_keys_by_profile[key[0]]))
        ):
            raise ValueError(f"Collapse operator {key[1]} must produce a non-dimension feature")


def validate_current_feature_selector(spec: spec_model.Spec) -> None:
    """Reject ambiguous current-feature selectors on multi-output calculations."""
    logger.debug("Check current-feature selectors are unambiguous")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None or spec.operator_kinds[key] not in {
            functions.VECTORIZE,
            functions.COLLAPSE,
        }:
            continue
        count = (
            len(set(operator.output_features) - set(spec.grain_keys_by_profile[key[0]]))
            if spec.operator_kinds[key] == functions.COLLAPSE
            else len(operator.output_features)
        )
        if count > 1 and operator.compute.uses_current_feature:
            raise ValueError(
                f"{spec.operator_kinds[key].capitalize()} operator {key[1]} "
                "cannot use $features.@ when it produces multiple features"
            )


def warn_unproduced_features(spec: spec_model.Spec) -> None:
    """Warn when declared profile features have no operator producer."""
    logger.debug("Check declared features have producers (warning only)")
    for key, profile in spec.profile_items:
        produced = {
            feature
            for feature, producers in profile.feature_producers.items()
            if any(
                spec.functions.root.get(operator.compute.function) is not None
                and functions.OPERATOR_KINDS[
                    spec.operator_kinds[(key, operator_id)]
                ].produces_features
                for operator_id, operator in producers
            )
        }
        missing = sorted(profile.features.keys() - produced - set(spec.grain_keys_by_profile[key]))
        if missing:
            warnings.warn(
                f"profiles.{key}.features: Features have no producer operator: "
                + ", ".join(missing),
                UserWarning,
                stacklevel=2,
            )
