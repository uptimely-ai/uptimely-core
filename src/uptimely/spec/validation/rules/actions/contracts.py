"""Atomic dataset-input and function-kind-specific action contract checks."""

import logging

from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)

EXPAND_INPUT_ERROR = (
    "Expand action must reference a declared feature from a lower-dimensional foreign dataset"
)


def validate_dataset_argument_reference(spec: spec_model.Spec) -> None:
    """Require each dataset argument to reference a dataset."""
    logger.debug("    - checking dataset arguments use dataset references")
    for key, arguments in spec.actions_arguments.items():
        for name, value, _ in arguments:
            if not isinstance(value, str) or not value.startswith(selectors.DATASET_PREFIX):
                raise errors.SpecError(
                    f"Dataset argument {name} must reference a dataset",
                    code="invalid_mapping_dataset_input",
                    path=(*spec.action_paths[key], "binding", "args", name),
                )


def validate_dataset_argument_selector(spec: spec_model.Spec) -> None:
    """Reject identifier and dimension selectors for dataset arguments."""
    logger.debug("    - checking dataset arguments select data, not IDs or dimensions")
    for key, arguments in spec.actions_arguments.items():
        for name, value, _ in arguments:
            if isinstance(value, str) and (
                value.endswith(selectors.ID_SELECTOR)
                or value.endswith(selectors.DIMENSION_IDS_SELECTOR)
            ):
                raise errors.SpecError(
                    f"Dataset argument {name} must select dataset data, not an identifier "
                    "or dimension list",
                    code="invalid_mapping_dataset_input",
                    path=(*spec.action_paths[key], "binding", "args", name),
                )


def validate_dataset_argument_source(spec: spec_model.Spec) -> None:
    """Require each dataset argument to resolve to a declared dataset."""
    logger.debug("    - checking dataset argument sources are declared")
    for key, arguments in spec.actions_arguments.items():
        for name, _, source_id in arguments:
            if source_id not in spec.profiles:
                raise errors.SpecError(
                    f"Dataset argument {name} references unknown dataset {source_id}",
                    code="invalid_mapping_dataset_input",
                    path=(*spec.action_paths[key], "binding", "args", name),
                )


def validate_dataset_argument_count(spec: spec_model.Spec) -> None:
    """Require actions to consume the foreign dataset count in their kind contract."""
    logger.debug("    - checking foreign dataset input counts match function kinds")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        expected = definition.dataframe_inputs
        if definition.dataframe_input_scope != "foreign" or expected is None:
            continue
        if len(spec.actions_arguments[key]) != expected or (
            len(spec.dataset_argument_ids[key]) != expected
        ):
            raise errors.SpecError(
                f"{function.kind.capitalize()} action must consume exactly "
                f"{expected} foreign dataset(s)",
                code="invalid_mapping_dataset_input",
                path=(*spec.action_paths[key], "binding", "args"),
            )


def validate_matching_keys(spec: spec_model.Spec) -> None:
    """Require explicitly selected matching keys to exist on every participating dataset."""
    logger.debug("    - checking matching keys exist on every participating dataset")
    for key, matches in spec.matching_key_dimensions.items():
        participants = (spec.action_profile_keys[key], *spec.dataset_argument_sources[key])
        for dimension, path in matches:
            for participant in participants:
                if dimension not in spec.dimensions_by_profile[participant]:
                    raise errors.SpecError(
                        f"Matching key {dimension} is not a dimension of profile {participant}",
                        code="invalid_mapping_matching_key",
                        path=path,
                    )


def validate_input_feature_source_count(spec: spec_model.Spec) -> None:
    """Require dataset-scoped feature inputs to belong to at most one dataset."""
    logger.debug("    - checking dataset-scoped feature inputs have at most one source")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None or functions.FUNCTION_KINDS[function.kind].feature_input_scope != (
            "dataframe"
        ):
            continue
        dataset_ids = {owner for _, owners in spec.input_candidates[key] for owner in owners}
        if len(dataset_ids) > 1:
            raise errors.SpecError(
                f"{function.kind.capitalize()} action inputs must belong to one source dataset",
                code="invalid_mapping_dataset_input",
                path=(*spec.action_paths[key], "features", "inputs"),
            )


def validate_foreign_dataset_argument(spec: spec_model.Spec) -> None:
    """Reject the target dataset when a kind requires a foreign dataset input."""
    logger.debug("    - checking foreign dataset arguments do not reference the target")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        if "target_as_foreign_input" in _dataset_input_violations(spec, key, definition):
            name = spec.actions_arguments[key][0][0]
            raise errors.SpecError(
                f"{function.kind.capitalize()} action must reference a foreign source dataset",
                code="invalid_mapping_dataset_input",
                path=(*spec.action_paths[key], "binding", "args", name),
            )


def validate_dataset_argument_feature_source(spec: spec_model.Spec) -> None:
    """Require a feature source to match the action's dataset input."""
    logger.debug("    - checking feature sources match dataset arguments")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        arguments = spec.actions_arguments[key]
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
                f"{function.kind.capitalize()} action must reference its foreign source dataset "
                f"{source}",
                code="invalid_mapping_dataset_input",
                path=(*spec.action_paths[key], "binding", "args", name),
            )


def validate_dataset_argument_features(spec: spec_model.Spec) -> None:
    """Require dataset-scoped feature inputs to belong to the action's dataset inputs."""
    logger.debug("    - checking feature inputs belong to the dataset arguments")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None or functions.FUNCTION_KINDS[function.kind].feature_input_scope != (
            "dataframe"
        ):
            continue
        unavailable = sorted(
            feature
            for feature in action.input_features
            if (
                feature not in spec.dataset_argument_dimensions[key]
                if feature in spec.dimensions
                else not any(
                    owner in spec.dataset_argument_ids[key]
                    for owner in spec.feature_owners.get(feature, [])
                )
            )
        )
        if unavailable:
            raise errors.SpecError(
                f"{function.kind.capitalize()} action inputs must belong to its dataset inputs: "
                + ", ".join(unavailable),
                code="invalid_mapping_feature_inputs",
                path=(*spec.action_paths[key], "features", "inputs"),
            )


def validate_feature_input_scope(spec: spec_model.Spec) -> None:
    """Reject feature inputs for kinds that do not accept feature dependencies."""
    logger.debug("    - checking function kinds permit declared feature inputs")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if (
            function is not None
            and functions.FUNCTION_KINDS[function.kind].feature_input_scope == ("none")
            and action.input_features
        ):
            raise errors.SpecError(
                f"Kind {function.kind} cannot declare feature inputs",
                code="invalid_mapping_feature_inputs",
                path=(*spec.action_paths[key], "features", "inputs"),
            )


def validate_target_dataset_input(spec: spec_model.Spec) -> None:
    """Require target-scoped actions to consume their target dataset."""
    logger.debug("    - checking target-scoped actions consume their target dataset")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        if "missing_target" in _dataset_input_violations(spec, key, definition):
            raise errors.SpecError(
                f"{function.kind.capitalize()} action must consume its target dataset",
                code="invalid_mapping_dataset_input",
                path=(*spec.action_paths[key], "binding", "args"),
            )


def validate_target_dataset_only(spec: spec_model.Spec) -> None:
    """Reject foreign dataset inputs on target-scoped actions."""
    logger.debug("    - checking target-scoped actions do not consume foreign datasets")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        if "foreign_target_input" not in _dataset_input_violations(spec, key, definition):
            continue
        foreign = sorted(spec.dataset_argument_ids[key] - {spec.action_profile_keys[key]})
        if foreign:
            raise errors.SpecError(
                f"{function.kind.capitalize()} action cannot publish a foreign dataset: "
                + ", ".join(foreign),
                code="invalid_mapping_dataset_input",
                path=(*spec.action_paths[key], "binding", "args"),
            )


def validate_dimension_source(spec: spec_model.Spec) -> None:
    """Require dimension-reducing actions to consume their inferred source."""
    logger.debug("    - checking dimension-reducing actions consume their inferred source")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None:
            continue
        definition = functions.FUNCTION_KINDS[function.kind]
        source = spec.input_sources[key]
        if source is not None and "missing_source" in _dataset_input_violations(
            spec, key, definition
        ):
            raise errors.SpecError(
                f"{function.kind.capitalize()} action must consume its source dataset {source}",
                code="invalid_mapping_dataset_input",
                path=(*spec.action_paths[key], "binding", "args"),
            )


def _dataset_input_violations(
    spec: spec_model.Spec,
    key: spec_model.ActionKey,
    definition: functions.FunctionKind,
) -> tuple[functions.DatasetInputViolation, ...]:
    source = spec.input_sources[key]
    return definition.dataset_input_violations(
        target_dataset_id=spec.action_profile_keys[key],
        argument_dataset_ids=tuple(source_id for _, _, source_id in spec.actions_arguments[key]),
        resolved_dataset_ids=spec.dataset_argument_ids[key],
        inferred_source_id=source,
    )


def validate_dimension_change(spec: spec_model.Spec) -> None:
    """Require dataset sources and targets to follow their declared dimension policy."""
    logger.debug("    - checking source and target dimensions follow function-kind policies")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None:
            continue
        change = functions.FUNCTION_KINDS[function.kind].dimension_change
        if change == "unrestricted":
            continue
        target = spec.dimensions_by_profile[spec.action_profile_keys[key]]
        for source_key in spec.dataset_argument_sources[key]:
            source = spec.dimensions_by_profile[source_key]
            valid = (
                source == target
                if change == "preserve"
                else (source < target if change == "add" else target < source)
            )
            if valid:
                continue
            if change == "preserve":
                message = (
                    f"{function.kind.capitalize()} action inputs must preserve "
                    "target dimensionality"
                )
                path = (*spec.action_paths[key], "binding", "args")
            elif change == "remove":
                message = (
                    f"{function.kind.capitalize()} action source must have strictly higher "
                    "dimensionality than its target"
                )
                path = (*spec.action_paths[key], "features", "inputs")
            else:
                message = EXPAND_INPUT_ERROR
                path = (*spec.action_paths[key], "binding", "args")
            raise errors.SpecError(message, code="invalid_mapping_dimensions", path=path)


def validate_dimension_expansion_input(spec: spec_model.Spec) -> None:
    """Require dimensional expansion to use a feature from a lower-dimensional source."""
    logger.debug("    - checking dimensional expansion inputs come from lower-dimensional sources")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None or functions.FUNCTION_KINDS[function.kind].dimension_change != "add":
            continue
        lower = {
            source
            for source in spec.dataset_argument_sources[key]
            if (
                spec.dimensions_by_profile[source]
                < spec.dimensions_by_profile[spec.action_profile_keys[key]]
            )
        }
        if not any(
            owner in lower
            for feature in action.input_features
            for owner in spec.feature_owners.get(feature, [])
        ):
            raise errors.SpecError(
                EXPAND_INPUT_ERROR,
                code="invalid_mapping_feature_inputs",
                path=(*spec.action_paths[key], "features", "inputs"),
            )
