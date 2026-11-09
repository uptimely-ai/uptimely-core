"""Atomic profile-input and function-kind-specific operator contract checks."""

import logging

from uptimely.spec import model as spec_model
from uptimely.spec import operator_kinds, selectors, semantics
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)

EXPAND_INPUT_ERROR = (
    "Expand operator must reference a declared feature from a lower-dimensional foreign profile"
)


def validate_dataframe_argument_profile_reference(spec: spec_model.Spec) -> None:
    """Require each dataframe argument to reference a profile."""
    logger.debug("Check dataframe arguments use profile references")
    for key, arguments in spec.operator_dataframe_arguments.items():
        for name, value, _ in arguments:
            if not isinstance(value, str) or not value.startswith(selectors.PROFILE_PREFIX):
                raise errors.SpecError(
                    f"DataFrame argument {name} must reference a profile",
                    code="invalid_mapping_dataframe_input",
                    path=(*spec.operator_paths[key], "compute", "args", name),
                )


def validate_dataframe_argument_selector(spec: spec_model.Spec) -> None:
    """Reject identifier and grain-key selectors for dataframe arguments."""
    logger.debug("Check dataframe arguments select profile data, not IDs or grain keys")
    for key, arguments in spec.operator_dataframe_arguments.items():
        for name, value, _ in arguments:
            if isinstance(value, str) and (
                value.endswith(selectors.ID_SELECTOR)
                or value.endswith(selectors.PROFILE_GRAIN_IDS_SELECTOR)
            ):
                raise errors.SpecError(
                    f"DataFrame argument {name} must select profile data, not an identifier "
                    "or grain-key list",
                    code="invalid_mapping_dataframe_input",
                    path=(*spec.operator_paths[key], "compute", "args", name),
                )


def validate_dataframe_argument_profile_source(spec: spec_model.Spec) -> None:
    """Require each dataframe argument to resolve to a declared profile."""
    logger.debug("Check dataframe argument profiles are declared")
    for key, arguments in spec.operator_dataframe_arguments.items():
        for name, _, source_id in arguments:
            if source_id not in spec.profiles:
                raise errors.SpecError(
                    f"DataFrame argument {name} references unknown profile {source_id}",
                    code="invalid_mapping_dataframe_input",
                    path=(*spec.operator_paths[key], "compute", "args", name),
                )


def validate_dataframe_argument_count(spec: spec_model.Spec) -> None:
    """Require operator to consume the foreign profile count in their kind contract."""
    logger.debug("Check foreign profile input counts match function kinds")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = operator_kinds.OPERATOR_KINDS[spec.operator_kinds[key]]
        expected = definition.dataframe_inputs
        if definition.dataframe_input_scope != "foreign" or expected is None:
            continue
        if len(spec.operator_dataframe_arguments[key]) != expected or (
            len(spec.dataframe_argument_profile_ids[key]) != expected
        ):
            raise errors.SpecError(
                f"{spec.operator_kinds[key].capitalize()} operator "
                f"must consume exactly "
                f"{expected} foreign profile(s)",
                code="invalid_mapping_dataframe_input",
                path=(*spec.operator_paths[key], "compute", "args"),
            )


def validate_matching_keys(spec: spec_model.Spec) -> None:
    """Require matching keys on every participating profile."""
    logger.debug("Check matching keys exist on every participating profile")
    for key, matches in spec.matching_profile_keys.items():
        participants = (spec.operator_profile_keys[key], *spec.dataframe_argument_profiles[key])
        for grain_key, path in matches:
            for participant in participants:
                if grain_key not in spec.grain_keys_by_profile[participant]:
                    raise errors.SpecError(
                        f"Matching key {grain_key} is not in the grain of profile {participant}",
                        code="invalid_mapping_matching_key",
                        path=path,
                    )


def validate_input_feature_source_count(spec: spec_model.Spec) -> None:
    """Require profile-scoped feature inputs to belong to at most one profile."""
    logger.debug("Check profile-scoped feature inputs have at most one source")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None or operator_kinds.OPERATOR_KINDS[
            spec.operator_kinds[key]
        ].feature_input_scope != ("dataframe"):
            continue
        profile_ids = {owner for _, owners in spec.input_candidates[key] for owner in owners}
        if len(profile_ids) > 1:
            raise errors.SpecError(
                f"{spec.operator_kinds[key].capitalize()} operator "
                f"inputs must belong to one source profile",
                code="invalid_mapping_dataframe_input",
                path=(*spec.operator_paths[key], "interface", "inputs"),
            )


def validate_foreign_profile_argument(spec: spec_model.Spec) -> None:
    """Reject the target profile when a kind requires a foreign profile input."""
    logger.debug("Check foreign profile arguments do not reference the target")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = operator_kinds.OPERATOR_KINDS[spec.operator_kinds[key]]
        if "target_as_foreign_input" in _dataframe_input_violations(spec, key, definition):
            name = spec.operator_dataframe_arguments[key][0][0]
            raise errors.SpecError(
                f"{spec.operator_kinds[key].capitalize()} operator "
                f"must reference a foreign source profile",
                code="invalid_mapping_dataframe_input",
                path=(*spec.operator_paths[key], "compute", "args", name),
            )


def validate_dataframe_argument_feature_source(spec: spec_model.Spec) -> None:
    """Require a feature source to match the operator's profile input."""
    logger.debug("Check feature sources match profile arguments")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = operator_kinds.OPERATOR_KINDS[spec.operator_kinds[key]]
        arguments = spec.operator_dataframe_arguments[key]
        source = spec.input_sources[key]
        if (
            definition.feature_input_scope != "dataframe"
            or definition.dataframe_inputs is None
            or len(arguments) != definition.dataframe_inputs
            or not arguments
            or source is None
        ):
            continue
        name, _, source_id = arguments[0]
        if source_id in spec.profiles and source_id != source:
            raise errors.SpecError(
                f"{spec.operator_kinds[key].capitalize()} operator "
                f"must reference its foreign source profile "
                f"{source}",
                code="invalid_mapping_dataframe_input",
                path=(*spec.operator_paths[key], "compute", "args", name),
            )


def validate_dataframe_argument_features(spec: spec_model.Spec) -> None:
    """Require profile-scoped feature inputs to belong to the operator's profile inputs."""
    logger.debug("Check feature inputs belong to profile arguments")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None or operator_kinds.OPERATOR_KINDS[
            spec.operator_kinds[key]
        ].feature_input_scope != ("dataframe"):
            continue
        unavailable = sorted(
            feature
            for feature in operator.input_features
            if (
                feature not in spec.dataframe_argument_grain_keys[key]
                if feature in spec.grain_key_ids
                else not any(
                    owner in spec.dataframe_argument_profile_ids[key]
                    for owner in spec.feature_owners.get(feature, [])
                )
            )
        )
        if unavailable:
            raise errors.SpecError(
                f"{spec.operator_kinds[key].capitalize()} operator "
                f"inputs must belong to its profile inputs: " + ", ".join(unavailable),
                code="invalid_mapping_feature_inputs",
                path=(*spec.operator_paths[key], "interface", "inputs"),
            )


def validate_feature_input_scope(spec: spec_model.Spec) -> None:
    """Reject feature inputs for kinds that do not accept feature dependencies."""
    logger.debug("Check function kinds permit declared feature inputs")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is not None
            and operator_kinds.OPERATOR_KINDS[spec.operator_kinds[key]].feature_input_scope
            == ("none")
            and operator.input_features
        ):
            raise errors.SpecError(
                f"Kind {spec.operator_kinds[key]} cannot declare feature inputs",
                code="invalid_mapping_feature_inputs",
                path=(*spec.operator_paths[key], "interface", "inputs"),
            )


def validate_target_profile_input(spec: spec_model.Spec) -> None:
    """Require target-scoped operator to consume their target profile."""
    logger.debug("Check target-scoped operator consume their target profile")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = operator_kinds.OPERATOR_KINDS[spec.operator_kinds[key]]
        if "missing_target" in _dataframe_input_violations(spec, key, definition):
            raise errors.SpecError(
                f"{spec.operator_kinds[key].capitalize()} operator must consume its target profile",
                code="invalid_mapping_dataframe_input",
                path=(*spec.operator_paths[key], "compute", "args"),
            )


def validate_target_profile_only(spec: spec_model.Spec) -> None:
    """Reject foreign profile inputs on target-scoped operator."""
    logger.debug("Check target-scoped operator do not consume foreign profiles")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = operator_kinds.OPERATOR_KINDS[spec.operator_kinds[key]]
        if "foreign_target_input" not in _dataframe_input_violations(spec, key, definition):
            continue
        foreign = sorted(
            spec.dataframe_argument_profile_ids[key] - {spec.operator_profile_keys[key]}
        )
        if foreign:
            raise errors.SpecError(
                f"{spec.operator_kinds[key].capitalize()} operator "
                f"cannot publish a foreign profile: " + ", ".join(foreign),
                code="invalid_mapping_dataframe_input",
                path=(*spec.operator_paths[key], "compute", "args"),
            )


def validate_dimension_source(spec: spec_model.Spec) -> None:
    """Require dimension-reducing operator to consume their inferred source."""
    logger.debug("Check dimension-reducing operator consume their inferred source")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = operator_kinds.OPERATOR_KINDS[spec.operator_kinds[key]]
        source = spec.input_sources[key]
        if source is not None and "missing_source" in _dataframe_input_violations(
            spec, key, definition
        ):
            raise errors.SpecError(
                f"{spec.operator_kinds[key].capitalize()} operator "
                f"must consume its source profile {source}",
                code="invalid_mapping_dataframe_input",
                path=(*spec.operator_paths[key], "compute", "args"),
            )


def _dataframe_input_violations(
    spec: spec_model.Spec,
    key: spec_model.OperatorKey,
    definition: operator_kinds.OperatorKind,
) -> tuple[operator_kinds.DataFrameInputViolation, ...]:
    source = spec.input_sources[key]
    return definition.dataframe_input_violations(
        target_profile_id=spec.operator_profile_keys[key],
        argument_profile_ids=tuple(
            source_id for _, _, source_id in spec.operator_dataframe_arguments[key]
        ),
        resolved_profile_ids=spec.dataframe_argument_profile_ids[key],
        inferred_profile_id=source,
    )


def validate_dimension_change(spec: spec_model.Spec) -> None:
    """Require profile sources and targets to follow their declared grain policy."""
    logger.debug("Check source and target dimensions follow function-kind policies")
    spec_semantics = semantics.Semantics(spec)
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        change = operator_kinds.OPERATOR_KINDS[spec.operator_kinds[key]].dimension_change
        if change == "unrestricted":
            continue
        for source_key in spec.dataframe_argument_profiles[key]:
            relationship = spec_semantics.operator_grain_relationships[key].get(
                source_key, "not_applicable"
            )
            valid = (
                relationship
                == {
                    "preserve": "same",
                    "add": "expand",
                    "remove": "collapse",
                }[change]
            )
            if valid:
                continue
            if change == "preserve":
                message = (
                    f"{spec.operator_kinds[key].capitalize()} operator "
                    f"inputs must preserve "
                    "target dimensionality"
                )
                path = (*spec.operator_paths[key], "compute", "args")
            elif change == "remove":
                message = (
                    f"{spec.operator_kinds[key].capitalize()} operator "
                    f"source must have strictly higher "
                    "dimensionality than its target"
                )
                path = (*spec.operator_paths[key], "interface", "inputs")
            else:
                message = EXPAND_INPUT_ERROR
                path = (*spec.operator_paths[key], "compute", "args")
            raise errors.SpecError(message, code="invalid_mapping_dimensions", path=path)


def validate_dimension_expansion_input(spec: spec_model.Spec) -> None:
    """Require dimensional expansion to use a feature from a lower-dimensional source."""
    logger.debug("Check dimensional expansion inputs come from lower-dimensional sources")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is None
            or operator_kinds.OPERATOR_KINDS[spec.operator_kinds[key]].dimension_change != "add"
        ):
            continue
        lower = {
            source
            for source in spec.dataframe_argument_profiles[key]
            if (
                spec.grain_refines(source, spec.operator_profile_keys[key])
                and spec.profiles_by_key[source].grain_reference_set
                != spec.profiles_by_key[spec.operator_profile_keys[key]].grain_reference_set
            )
        }
        if not any(
            owner in lower
            for feature in operator.input_features
            for owner in spec.feature_owners.get(feature, [])
        ):
            raise errors.SpecError(
                EXPAND_INPUT_ERROR,
                code="invalid_mapping_feature_inputs",
                path=(*spec.operator_paths[key], "interface", "inputs"),
            )
