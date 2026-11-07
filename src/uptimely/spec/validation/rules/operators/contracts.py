"""Atomic profile-input and function-kind-specific operator contract checks."""

import logging

from uptimely.spec import function_kinds as functions
from uptimely.spec import model as spec_model
from uptimely.spec import selectors
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)

EXPAND_INPUT_ERROR = (
    "Expand operator must reference a declared feature from a lower-dimensional foreign profile"
)


def validate_dataset_argument_reference(spec: spec_model.Spec) -> None:
    """Require each dataframe argument to reference a profile."""
    logger.debug("    - checking dataframe arguments use profile references")
    for key, arguments in spec.operator_arguments.items():
        for name, value, _ in arguments:
            if not isinstance(value, str) or not value.startswith(selectors.PROFILE_PREFIX):
                raise errors.SpecError(
                    f"DataFrame argument {name} must reference a profile",
                    code="invalid_mapping_dataset_input",
                    path=(*spec.operator_paths[key], "compute", "args", name),
                )


def validate_dataset_argument_selector(spec: spec_model.Spec) -> None:
    """Reject identifier and grain-key selectors for dataframe arguments."""
    logger.debug("    - checking dataframe arguments select profile data, not IDs or grain keys")
    for key, arguments in spec.operator_arguments.items():
        for name, value, _ in arguments:
            if isinstance(value, str) and (
                value.endswith(selectors.ID_SELECTOR)
                or value.endswith(selectors.PROFILE_GRAIN_IDS_SELECTOR)
            ):
                raise errors.SpecError(
                    f"DataFrame argument {name} must select profile data, not an identifier "
                    "or grain-key list",
                    code="invalid_mapping_dataset_input",
                    path=(*spec.operator_paths[key], "compute", "args", name),
                )


def validate_dataset_argument_source(spec: spec_model.Spec) -> None:
    """Require each dataframe argument to resolve to a declared profile."""
    logger.debug("    - checking dataframe argument profiles are declared")
    for key, arguments in spec.operator_arguments.items():
        for name, _, source_id in arguments:
            if source_id not in spec.profiles:
                raise errors.SpecError(
                    f"DataFrame argument {name} references unknown profile {source_id}",
                    code="invalid_mapping_dataset_input",
                    path=(*spec.operator_paths[key], "compute", "args", name),
                )


def validate_dataset_argument_count(spec: spec_model.Spec) -> None:
    """Require operator to consume the foreign profile count in their kind contract."""
    logger.debug("    - checking foreign profile input counts match function kinds")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        expected = definition.dataframe_inputs
        if definition.dataframe_input_scope != "foreign" or expected is None:
            continue
        if len(spec.operator_arguments[key]) != expected or (
            len(spec.dataset_argument_ids[key]) != expected
        ):
            raise errors.SpecError(
                f"{function.kind.capitalize()} operator must consume exactly "
                f"{expected} foreign profile(s)",
                code="invalid_mapping_dataset_input",
                path=(*spec.operator_paths[key], "compute", "args"),
            )


def validate_matching_keys(spec: spec_model.Spec) -> None:
    """Require matching keys on every participating profile."""
    logger.debug("    - checking matching keys exist on every participating profile")
    for key, matches in spec.matching_profile_keys.items():
        participants = (spec.operator_profile_keys[key], *spec.dataset_argument_sources[key])
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
    logger.debug("    - checking profile-scoped feature inputs have at most one source")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None or functions.FUNCTION_KINDS[function.kind].feature_input_scope != (
            "dataframe"
        ):
            continue
        dataset_ids = {owner for _, owners in spec.input_candidates[key] for owner in owners}
        if len(dataset_ids) > 1:
            raise errors.SpecError(
                f"{function.kind.capitalize()} operator inputs must belong to one source profile",
                code="invalid_mapping_dataset_input",
                path=(*spec.operator_paths[key], "interface", "inputs"),
            )


def validate_foreign_dataset_argument(spec: spec_model.Spec) -> None:
    """Reject the target profile when a kind requires a foreign profile input."""
    logger.debug("    - checking foreign profile arguments do not reference the target")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        if "target_as_foreign_input" in _dataset_input_violations(spec, key, definition):
            name = spec.operator_arguments[key][0][0]
            raise errors.SpecError(
                f"{function.kind.capitalize()} operator must reference a foreign source profile",
                code="invalid_mapping_dataset_input",
                path=(*spec.operator_paths[key], "compute", "args", name),
            )


def validate_dataset_argument_feature_source(spec: spec_model.Spec) -> None:
    """Require a feature source to match the operator's profile input."""
    logger.debug("    - checking feature sources match profile arguments")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        arguments = spec.operator_arguments[key]
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
                f"{function.kind.capitalize()} operator must reference its foreign source profile "
                f"{source}",
                code="invalid_mapping_dataset_input",
                path=(*spec.operator_paths[key], "compute", "args", name),
            )


def validate_dataset_argument_features(spec: spec_model.Spec) -> None:
    """Require profile-scoped feature inputs to belong to the operator's profile inputs."""
    logger.debug("    - checking feature inputs belong to profile arguments")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None or functions.FUNCTION_KINDS[function.kind].feature_input_scope != (
            "dataframe"
        ):
            continue
        unavailable = sorted(
            feature
            for feature in operator.input_features
            if (
                feature not in spec.dataset_argument_grain_keys[key]
                if feature in spec.grain_key_ids
                else not any(
                    owner in spec.dataset_argument_ids[key]
                    for owner in spec.feature_owners.get(feature, [])
                )
            )
        )
        if unavailable:
            raise errors.SpecError(
                f"{function.kind.capitalize()} operator inputs must belong to its profile inputs: "
                + ", ".join(unavailable),
                code="invalid_mapping_feature_inputs",
                path=(*spec.operator_paths[key], "interface", "inputs"),
            )


def validate_feature_input_scope(spec: spec_model.Spec) -> None:
    """Reject feature inputs for kinds that do not accept feature dependencies."""
    logger.debug("    - checking function kinds permit declared feature inputs")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is not None
            and functions.FUNCTION_KINDS[function.kind].feature_input_scope == ("none")
            and operator.input_features
        ):
            raise errors.SpecError(
                f"Kind {function.kind} cannot declare feature inputs",
                code="invalid_mapping_feature_inputs",
                path=(*spec.operator_paths[key], "interface", "inputs"),
            )


def validate_target_dataset_input(spec: spec_model.Spec) -> None:
    """Require target-scoped operator to consume their target profile."""
    logger.debug("    - checking target-scoped operator consume their target profile")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        if "missing_target" in _dataset_input_violations(spec, key, definition):
            raise errors.SpecError(
                f"{function.kind.capitalize()} operator must consume its target profile",
                code="invalid_mapping_dataset_input",
                path=(*spec.operator_paths[key], "compute", "args"),
            )


def validate_target_dataset_only(spec: spec_model.Spec) -> None:
    """Reject foreign profile inputs on target-scoped operator."""
    logger.debug("    - checking target-scoped operator do not consume foreign profiles")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        if "foreign_target_input" not in _dataset_input_violations(spec, key, definition):
            continue
        foreign = sorted(spec.dataset_argument_ids[key] - {spec.operator_profile_keys[key]})
        if foreign:
            raise errors.SpecError(
                f"{function.kind.capitalize()} operator cannot publish a foreign profile: "
                + ", ".join(foreign),
                code="invalid_mapping_dataset_input",
                path=(*spec.operator_paths[key], "compute", "args"),
            )


def validate_dimension_source(spec: spec_model.Spec) -> None:
    """Require dimension-reducing operator to consume their inferred source."""
    logger.debug("    - checking dimension-reducing operator consume their inferred source")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        source = spec.input_sources[key]
        if source is not None and "missing_source" in _dataset_input_violations(
            spec, key, definition
        ):
            raise errors.SpecError(
                f"{function.kind.capitalize()} operator must consume its source profile {source}",
                code="invalid_mapping_dataset_input",
                path=(*spec.operator_paths[key], "compute", "args"),
            )


def _dataset_input_violations(
    spec: spec_model.Spec,
    key: spec_model.OperatorKey,
    definition: functions.FunctionKind,
) -> tuple[functions.DatasetInputViolation, ...]:
    source = spec.input_sources[key]
    return definition.dataset_input_violations(
        target_dataset_id=spec.operator_profile_keys[key],
        argument_dataset_ids=tuple(source_id for _, _, source_id in spec.operator_arguments[key]),
        resolved_dataset_ids=spec.dataset_argument_ids[key],
        inferred_source_id=source,
    )


def validate_dimension_change(spec: spec_model.Spec) -> None:
    """Require profile sources and targets to follow their declared grain policy."""
    logger.debug("    - checking source and target dimensions follow function-kind policies")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        change = functions.FUNCTION_KINDS[function.kind].dimension_change
        if change == "unrestricted":
            continue
        target_profile = spec.operator_profile_keys[key]
        target = spec.profiles_by_key[target_profile].grain_reference_set
        for source_key in spec.dataset_argument_sources[key]:
            source = spec.profiles_by_key[source_key].grain_reference_set
            valid = (
                source == target
                if change == "preserve"
                else (
                    spec.grain_refines(source_key, target_profile) and source != target
                    if change == "add"
                    else spec.grain_refines(target_profile, source_key) and target != source
                )
            )
            if valid:
                continue
            if change == "preserve":
                message = (
                    f"{function.kind.capitalize()} operator inputs must preserve "
                    "target dimensionality"
                )
                path = (*spec.operator_paths[key], "compute", "args")
            elif change == "remove":
                message = (
                    f"{function.kind.capitalize()} operator source must have strictly higher "
                    "dimensionality than its target"
                )
                path = (*spec.operator_paths[key], "interface", "inputs")
            else:
                message = EXPAND_INPUT_ERROR
                path = (*spec.operator_paths[key], "compute", "args")
            raise errors.SpecError(message, code="invalid_mapping_dimensions", path=path)


def validate_dimension_expansion_input(spec: spec_model.Spec) -> None:
    """Require dimensional expansion to use a feature from a lower-dimensional source."""
    logger.debug("    - checking dimensional expansion inputs come from lower-dimensional sources")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None or functions.FUNCTION_KINDS[function.kind].dimension_change != "add":
            continue
        lower = {
            source
            for source in spec.dataset_argument_sources[key]
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
