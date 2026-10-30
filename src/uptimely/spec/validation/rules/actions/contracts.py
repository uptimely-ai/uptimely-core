"""Atomic dataframe and function-kind-specific action contract checks."""

from __future__ import annotations

import collections.abc
import dataclasses

from uptimely.spec import arg_types, functions, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors
from uptimely.spec.validation.rules import actions as action_rules
from uptimely.spec.validation.rules import datasets as dataset_rules
from uptimely.spec.validation.rules import features as feature_rules

from . import inputs

EXPAND_INPUT_ERROR = (
    "Expand action must reference a declared feature from a lower-dimensional foreign dataset"
)


@dataclasses.dataclass(frozen=True)
class DataframeInput:
    """A dataframe argument's value, normalized reference, and candidate source."""

    argument_id: str
    value: object
    source_id: str | None
    source: dataset_rules.DatasetDeclaration | None
    path: errors.SpecPath


@dataclasses.dataclass(frozen=True)
class ActionContract:
    """The action and its resolved dataframe argument resources."""

    action: action_rules.ActionDeclaration
    dataframe_arguments: tuple[DataframeInput, ...]
    source: dataset_rules.DatasetDeclaration | None


def iter_action_contracts(spec: spec_model.Spec) -> collections.abc.Iterator[ActionContract]:
    """Yield action-specific dataframe resources in declaration order."""
    dataset = {item.dataset.id: item for item in dataset_rules.iter_datasets(spec)}.get
    for item in inputs.iter_input_sources(spec):
        yield ActionContract(
            action=item.action,
            dataframe_arguments=_dataframe_inputs(item.action, dataset),
            source=item.source,
        )


def _dataframe_inputs(
    action: action_rules.ActionDeclaration,
    dataset: collections.abc.Callable[[str], dataset_rules.DatasetDeclaration | None],
) -> tuple[DataframeInput, ...]:
    """Retain dataframe selector values and any matching dataset."""
    if action.function is None:
        return ()
    result: list[DataframeInput] = []
    for argument_id, argument in action.function.args.items():
        if argument.type != arg_types.DATAFRAME:
            continue
        value = action.action.binding.args.get(argument_id)
        source_id = None
        if isinstance(value, str) and value.startswith(selectors.DATASET_PREFIX):
            reference = value.removeprefix(selectors.DATASET_PREFIX).removesuffix(
                selectors.DATAFRAME_SELECTOR
            )
            source_id = action.dataset.id if reference == selectors.CURRENT_ID else reference
        source = dataset(source_id) if source_id is not None else None
        result.append(
            DataframeInput(
                argument_id,
                value,
                source_id,
                source,
                (*action.path, "binding", "args", argument_id),
            )
        )
    return tuple(result)


def _iter_matching_keys(
    action: action_rules.ActionDeclaration,
    value: object,
    path: errors.SpecPath,
    dataset: collections.abc.Callable[[str], dataset_rules.DatasetDeclaration | None],
) -> collections.abc.Iterator[tuple[str, errors.SpecPath]]:
    """Yield declared dimension keys and their argument paths."""
    if (
        isinstance(value, str)
        and value.startswith(selectors.DATASET_PREFIX)
        and value.endswith(selectors.DIMENSION_IDS_SELECTOR)
    ):
        dataset_id = value.removeprefix(selectors.DATASET_PREFIX).removesuffix(
            selectors.DIMENSION_IDS_SELECTOR
        )
        location = (
            action.dataset_declaration
            if dataset_id == selectors.CURRENT_ID
            else dataset(dataset_id)
        )
        if location is not None:
            for dimension_id in location.entity.dimension_ids:
                yield (dimension_id, path)
    elif isinstance(value, dict):
        for name, nested in value.items():
            yield from _iter_matching_keys(action, nested, (*path, name), dataset)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _iter_matching_keys(action, nested, (*path, index), dataset)


def validate_dataframe_reference(spec: spec_model.Spec) -> None:
    """Require a dataframe argument to reference a dataset."""
    for contract in iter_action_contracts(spec):
        for item in contract.dataframe_arguments:
            if not isinstance(item.value, str) or not item.value.startswith(
                selectors.DATASET_PREFIX
            ):
                raise errors.SpecError(
                    f"Dataframe argument {item.argument_id} must reference a dataset",
                    code="invalid_mapping_dataset_input",
                    path=item.path,
                )


def validate_dataframe_selector(spec: spec_model.Spec) -> None:
    """Reject a dataset ID selector where a dataframe is required."""
    for contract in iter_action_contracts(spec):
        for item in contract.dataframe_arguments:
            if isinstance(item.value, str) and (
                item.value.endswith(selectors.ID_SELECTOR)
                or item.value.endswith(selectors.DIMENSION_IDS_SELECTOR)
            ):
                raise errors.SpecError(
                    f"Dataframe argument {item.argument_id} must reference a dataframe",
                    code="invalid_mapping_dataset_input",
                    path=item.path,
                )


def validate_dataframe_source(spec: spec_model.Spec) -> None:
    """Require a dataframe reference to resolve to a dataset."""
    for contract in iter_action_contracts(spec):
        for item in contract.dataframe_arguments:
            if item.source is None:
                raise errors.SpecError(
                    f"Dataframe argument {item.argument_id} references unknown dataset "
                    f"{item.source_id}",
                    code="invalid_mapping_dataset_input",
                    path=item.path,
                )


def validate_dataset_count(spec: spec_model.Spec) -> None:
    """Require actions to consume the foreign dataframe count in their contract."""
    for item in iter_action_contracts(spec):
        kind = item.action.kind
        if kind is None:
            continue
        definition = functions.FUNCTION_KINDS[kind]
        if definition.dataframe_input_scope != "foreign":
            continue
        expected_count = definition.dataframe_inputs
        if expected_count is None:
            continue
        dataset_ids = {
            argument.source.dataset.id
            for argument in item.dataframe_arguments
            if argument.source is not None
        }
        if len(item.dataframe_arguments) != expected_count or len(dataset_ids) != expected_count:
            raise errors.SpecError(
                f"{kind.capitalize()} action must consume exactly "
                f"{expected_count} foreign dataset(s)",
                code="invalid_mapping_dataset_input",
                path=(*item.action.path, "binding", "args"),
            )


def validate_matching_keys(spec: spec_model.Spec) -> None:
    """Require explicitly selected matching keys to exist on every participating dataset."""
    dataset = {item.dataset.id: item for item in dataset_rules.iter_datasets(spec)}.get
    for item in iter_action_contracts(spec):
        participants = (
            item.action.dataset_declaration,
            *(
                argument.source
                for argument in item.dataframe_arguments
                if argument.source is not None
            ),
        )
        base_path = (*item.action.declaration_path, "binding", "args")
        for name, value in item.action.action.binding.args.items():
            for dimension_id, path in _iter_matching_keys(
                item.action, value, (*base_path, name), dataset
            ):
                for participant in participants:
                    if dimension_id not in participant.dimensions:
                        raise errors.SpecError(
                            f"Matching key {dimension_id} is not a dimension of dataset "
                            f"{participant.dataset.id}",
                            code="invalid_mapping_matching_key",
                            path=path,
                        )


def validate_input_feature_source_count(spec: spec_model.Spec) -> None:
    """Require dataframe-scoped feature inputs to belong to at most one dataset."""
    for item in inputs.iter_input_sources(spec):
        if item.action.kind is None:
            continue
        definition = functions.FUNCTION_KINDS[item.action.kind]
        if definition.feature_input_scope != "dataframe":
            continue
        feature_dataset_ids = {
            owner.dataset.id for _, owners in item.candidates for owner in owners
        }
        if len(feature_dataset_ids) > 1:
            raise errors.SpecError(
                f"{item.action.kind.capitalize()} action inputs must belong to one source dataset",
                code="invalid_mapping_dataset_input",
                path=(*item.action.path, "features", "inputs"),
            )


def validate_foreign_dataframe(spec: spec_model.Spec) -> None:
    """Reject the target dataset when a kind requires a foreign dataframe."""
    for item in iter_action_contracts(spec):
        kind = item.action.kind
        if kind is None:
            continue
        definition = functions.FUNCTION_KINDS[kind]
        if definition.dataframe_input_scope != "foreign":
            continue
        if (
            definition.dataframe_inputs is None
            or len(item.dataframe_arguments) != definition.dataframe_inputs
            or not item.dataframe_arguments
        ):
            continue
        dataframe = item.dataframe_arguments[0]
        if dataframe.source_id == item.action.dataset.id:
            raise errors.SpecError(
                f"{kind.capitalize()} action must reference a foreign source dataset",
                code="invalid_mapping_dataset_input",
                path=dataframe.path,
            )


def validate_dataframe_feature_source(spec: spec_model.Spec) -> None:
    """Require a dataframe-scoped feature source to match its dataframe binding."""
    for item in iter_action_contracts(spec):
        kind = item.action.kind
        if kind is None:
            continue
        definition = functions.FUNCTION_KINDS[kind]
        if definition.feature_input_scope != "dataframe":
            continue
        if (
            definition.dataframe_inputs is None
            or len(item.dataframe_arguments) != definition.dataframe_inputs
            or not item.dataframe_arguments
        ):
            continue
        if item.source is None:
            continue
        dataframe = item.dataframe_arguments[0]
        if dataframe.source is None:
            continue
        expected_source = item.source.dataset.id
        if dataframe.source.dataset.id != expected_source:
            raise errors.SpecError(
                f"{kind.capitalize()} action must reference its foreign source dataset "
                f"{expected_source}",
                code="invalid_mapping_dataset_input",
                path=dataframe.path,
            )


def validate_dataframe_features(spec: spec_model.Spec) -> None:
    """Require dataframe-scoped feature inputs to belong to dataframe inputs."""
    dimension_ids = frozenset(spec.dimensions)
    feature_owners = feature_rules.feature_owners(spec)
    for item in iter_action_contracts(spec):
        kind = item.action.kind
        if kind is None:
            continue
        if functions.FUNCTION_KINDS[kind].feature_input_scope != "dataframe":
            continue
        dataset_ids = {
            argument.source.dataset.id
            for argument in item.dataframe_arguments
            if argument.source is not None
        }
        available_dimensions = frozenset().union(
            *(
                argument.source.dimensions
                for argument in item.dataframe_arguments
                if argument.source is not None
            )
        )
        unavailable_features = sorted(
            feature
            for feature in item.action.inputs
            if (
                feature not in available_dimensions
                if feature in dimension_ids
                else not any(
                    owner.dataset.id in dataset_ids for owner in feature_owners.get(feature, ())
                )
            )
        )
        if unavailable_features:
            raise errors.SpecError(
                f"{kind.capitalize()} action inputs must belong to its dataframe inputs: "
                + ", ".join(unavailable_features),
                code="invalid_mapping_feature_inputs",
                path=(*item.action.path, "features", "inputs"),
            )


def validate_feature_input_scope(spec: spec_model.Spec) -> None:
    """Reject feature inputs for kinds that do not accept feature dependencies."""
    for item in action_rules.iter_actions(spec):
        if (
            item.kind is not None
            and functions.FUNCTION_KINDS[item.kind].feature_input_scope == "none"
            and item.inputs
        ):
            raise errors.SpecError(
                f"Kind {item.kind} cannot declare feature inputs",
                code="invalid_mapping_feature_inputs",
                path=(*item.path, "features", "inputs"),
            )


def validate_target_input(spec: spec_model.Spec) -> None:
    """Require target-scoped actions to consume their target dataset."""
    for item in iter_action_contracts(spec):
        kind = item.action.kind
        if kind is None:
            continue
        definition = functions.FUNCTION_KINDS[kind]
        if definition.dataframe_input_scope != "target":
            continue
        dataset_ids = {
            argument.source.dataset.id
            for argument in item.dataframe_arguments
            if argument.source is not None
        }
        if item.action.dataset.id not in dataset_ids:
            raise errors.SpecError(
                f"{kind.capitalize()} action must consume its target dataset",
                code="invalid_mapping_dataset_input",
                path=(*item.action.path, "binding", "args"),
            )


def validate_write_dataframe(spec: spec_model.Spec) -> None:
    """Reject foreign dataframe inputs on target-scoped actions."""
    for item in iter_action_contracts(spec):
        kind = item.action.kind
        if kind is None:
            continue
        dataset_ids = {
            argument.source.dataset.id
            for argument in item.dataframe_arguments
            if argument.source is not None
        }
        if functions.FUNCTION_KINDS[kind].dataframe_input_scope == "target":
            foreign = sorted(dataset_ids - {item.action.dataset.id})
            if foreign:
                raise errors.SpecError(
                    f"{kind.capitalize()} action cannot publish a foreign dataset dataframe: "
                    + ", ".join(foreign),
                    code="invalid_mapping_dataset_input",
                    path=(*item.action.path, "binding", "args"),
                )


def validate_collapse_source(spec: spec_model.Spec) -> None:
    """Require collapse to consume its inferred source dataset."""
    for item in iter_action_contracts(spec):
        dataset_ids = {
            argument.source.dataset.id
            for argument in item.dataframe_arguments
            if argument.source is not None
        }
        if (
            item.action.kind == functions.COLLAPSE
            and item.source is not None
            and (item.source.dataset.id not in dataset_ids)
        ):
            raise errors.SpecError(
                f"Collapse action must consume its source dataset {item.source.dataset.id}",
                code="invalid_mapping_dataset_input",
                path=(*item.action.path, "binding", "args"),
            )


def validate_collapse_dimensions(spec: spec_model.Spec) -> None:
    """Require collapse to reduce source dimensionality."""
    for item in iter_action_contracts(spec):
        if (
            item.action.kind == functions.COLLAPSE
            and item.source is not None
            and (not item.action.dimensions < item.source.dimensions)
        ):
            raise errors.SpecError(
                "Collapse action source must have strictly higher dimensionality than its target",
                code="invalid_mapping_dimensions",
                path=(*item.action.path, "features", "inputs"),
            )


def validate_conform_dimensions(spec: spec_model.Spec) -> None:
    """Require conform inputs to preserve target dimensionality."""
    for item in iter_action_contracts(spec):
        if item.action.kind == functions.CONFORM and any(
            argument.source is not None and argument.source.dimensions != item.action.dimensions
            for argument in item.dataframe_arguments
        ):
            raise errors.SpecError(
                "Conform action inputs must preserve target dimensionality",
                code="invalid_mapping_dimensions",
                path=(*item.action.path, "binding", "args"),
            )


def validate_expand_dimensions(spec: spec_model.Spec) -> None:
    """Require expand to use a declared feature from a lower-dimensional source."""
    feature_owners = feature_rules.feature_owners(spec)
    for item in iter_action_contracts(spec):
        if item.action.kind != functions.EXPAND:
            continue
        lower_dataset_ids = {
            argument.source.dataset.id
            for argument in item.dataframe_arguments
            if argument.source is not None and argument.source.dimensions < item.action.dimensions
        }
        has_lower_feature = any(
            owner.dataset.id in lower_dataset_ids
            for feature in item.action.inputs
            for owner in feature_owners.get(feature, ())
        )
        if not lower_dataset_ids or not has_lower_feature:
            raise errors.SpecError(
                EXPAND_INPUT_ERROR,
                code="invalid_mapping_dimensions",
                path=(*item.action.path, "binding", "args"),
            )
