"""Atomic profile-input and operator-specific contract checks."""

import logging

from uptimely.spec import model as spec_model
from uptimely.spec import selectors
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


def validate_matching_keys(spec: spec_model.Spec) -> None:
    """Require matching keys on every participating profile."""
    logger.debug("Check matching keys exist on every participating profile")
    for key, matches in spec.matching_profile_keys.items():
        participants = (spec.operator_profile_keys[key], *spec.dataframe_argument_profiles[key])
        for grain_key, path in matches:
            for participant in participants:
                if grain_key not in spec.identifiers_by_profile[participant]:
                    raise errors.SpecError(
                        f"Matching key {grain_key} is not in the grain of profile {participant}",
                        code="invalid_mapping_matching_key",
                        path=path,
                    )


def validate_input_feature_source_count(spec: spec_model.Spec) -> None:
    """Require dataframe-producing feature inputs to belong to one source profile."""
    logger.debug("Check dataframe-producing feature inputs have at most one source")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None or function.returns != "dataframe" or not operator.input_features:
            continue
        profile_ids = {owner for _, owners in spec.input_candidates[key] for owner in owners}
        if len(profile_ids) > 1:
            raise errors.SpecError(
                f"Operator {key[1]} feature inputs must belong to one source profile",
                code="invalid_mapping_dataframe_input",
                path=(*spec.operator_paths[key], "interface", "inputs"),
            )


def validate_foreign_profile_argument(spec: spec_model.Spec) -> None:
    """Require a bound dataframe to match a foreign feature-input source."""
    logger.debug("Check dataframe arguments match foreign feature-input sources")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None or function.returns != "dataframe":
            continue
        source = spec.input_sources[key]
        arguments = spec.operator_dataframe_arguments[key]
        if source is not None and source != key[0] and arguments:
            name, _, source_id = arguments[0]
            if source_id == source:
                continue
            raise errors.SpecError(
                f"Operator {key[1]} dataframe argument {name} must reference a foreign "
                f"source profile {source}",
                code="invalid_mapping_dataframe_input",
                path=(*spec.operator_paths[key], "compute", "args", name),
            )


def validate_dataframe_argument_feature_source(spec: spec_model.Spec) -> None:
    """Require a feature source to match the operator's profile input."""
    logger.debug("Check feature sources match profile arguments")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None or function.returns != "dataframe":
            continue
        arguments = spec.operator_dataframe_arguments[key]
        source = spec.input_sources[key]
        if not arguments or source is None:
            continue
        for name, _, source_id in arguments:
            if source_id != source:
                scope = "foreign source" if source != key[0] else "target"
                raise errors.SpecError(
                    f"Operator {key[1]} dataframe argument {name} must reference its {scope} "
                    f"profile {source}",
                    code="invalid_mapping_dataframe_input",
                    path=(*spec.operator_paths[key], "compute", "args", name),
                )


def validate_dataframe_argument_features(spec: spec_model.Spec) -> None:
    """Require declared feature inputs to exist in the bound dataframe profile."""
    logger.debug("Check feature inputs belong to profile arguments")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is None
            or function.returns != "dataframe"
            or not operator.input_features
            or not spec.dataframe_argument_profiles[key]
        ):
            continue
        unavailable = sorted(
            feature
            for feature in operator.input_features
            if (
                feature not in spec.dataframe_argument_identifiers[key]
                if feature in spec.identifier_ids
                else not any(
                    owner in spec.dataframe_argument_profile_ids[key]
                    for owner in spec.feature_owners.get(feature, [])
                )
            )
        )
        if unavailable:
            raise errors.SpecError(
                f"Operator {key[1]} inputs must belong to its profile inputs: "
                + ", ".join(unavailable),
                code="invalid_mapping_feature_inputs",
                path=(*spec.operator_paths[key], "interface", "inputs"),
            )


def validate_feature_input_scope(spec: spec_model.Spec) -> None:
    """Reject feature inputs when a dataframe computation has no source binding."""
    logger.debug("Check dataframe-producing functions have bindings for feature inputs")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if (
            function is not None
            and function.returns == "dataframe"
            and not spec.operator_dataframe_arguments[key]
            and operator.input_features
        ):
            raise errors.SpecError(
                f"Operator {key[1]} cannot declare feature inputs without a dataframe source",
                code="invalid_mapping_feature_inputs",
                path=(*spec.operator_paths[key], "interface", "inputs"),
            )


def validate_dimension_change(spec: spec_model.Spec) -> None:
    """Reject dataframe sources with unresolved or unrelated target grains."""
    logger.debug("Check dataframe source and target grain relationships")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None or function.returns != "dataframe":
            continue
        for source_key in spec.dataframe_argument_profiles[key]:
            relationship = spec.operator_grain_relationships[key].get(source_key)
            if relationship in {"same", "expand", "collapse"}:
                continue
            raise errors.SpecError(
                f"Operator {key[1]} source profile {source_key} has an "
                f"{relationship or 'unresolved'} grain relationship to target {key[0]}",
                code="invalid_mapping_dimensions",
                path=(*spec.operator_paths[key], "compute", "args"),
            )


def validate_dimension_expansion_input(spec: spec_model.Spec) -> None:
    """Require dimensional expansion to use a feature from a lower-dimensional source."""
    logger.debug("Check dimensional expansion inputs come from lower-dimensional sources")
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None or function.returns != "dataframe":
            continue
        lower = {
            source
            for source in spec.dataframe_argument_profiles[key]
            if spec.operator_grain_relationships[key].get(source) == "expand"
        }
        if not lower:
            continue
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
