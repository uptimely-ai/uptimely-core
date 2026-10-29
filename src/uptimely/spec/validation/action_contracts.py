"""Atomic dataframe and function-kind-specific action contract checks."""

from __future__ import annotations

import collections.abc
import dataclasses

from .. import arg_types, functions, selectors
from . import context as context_module
from . import errors

EXPAND_INPUT_ERROR = (
    "Expand action must reference a declared feature from a lower-dimensional foreign dataset"
)


@dataclasses.dataclass(frozen=True)
class DataframeInput:
    """A dataframe argument's value, normalized reference, and candidate source."""

    argument_id: str
    value: object
    source_id: str | None
    source: context_module.DatasetLocation | None
    path: context_module.SpecPath


@dataclasses.dataclass(frozen=True)
class ActionContract:
    """The action and its resolved dataframe argument resources."""

    action: context_module.ActionFacts
    dataframe_arguments: tuple[DataframeInput, ...]
    source: context_module.DatasetLocation | None


def iter_action_contracts(
    actions: collections.abc.Iterable[context_module.ActionFacts],
    dataset: collections.abc.Callable[[str], context_module.DatasetLocation | None],
    collapse_sources: collections.abc.Mapping[tuple[str, str, str], context_module.DatasetLocation],
) -> collections.abc.Iterator[ActionContract]:
    """Yield action-specific dataframe resources in declaration order."""
    for action in actions:
        yield ActionContract(
            action=action,
            dataframe_arguments=_dataframe_inputs(action, dataset),
            source=collapse_sources.get(action.location.key),
        )


def _dataframe_inputs(
    action: context_module.ActionFacts,
    dataset: collections.abc.Callable[[str], context_module.DatasetLocation | None],
) -> tuple[DataframeInput, ...]:
    """Retain dataframe selector values and any matching dataset."""
    if action.function is None:
        return ()
    result: list[DataframeInput] = []
    for argument_id, argument in action.function.args.items():
        if argument.type != arg_types.DATAFRAME:
            continue
        value = action.location.action.binding.args.get(argument_id)
        source_id = None
        if isinstance(value, str) and value.startswith(selectors.DATASET_PREFIX):
            reference = value.removeprefix(selectors.DATASET_PREFIX).removesuffix(
                selectors.DATAFRAME_SELECTOR
            )
            source_id = (
                action.location.dataset.id if reference == selectors.CURRENT_ID else reference
            )
        source = dataset(source_id) if source_id is not None else None
        result.append(
            DataframeInput(
                argument_id,
                value,
                source_id,
                source,
                (*action.location.path, "binding", "args", argument_id),
            )
        )
    return tuple(result)


def _iter_matching_keys(
    action: context_module.ActionFacts,
    value: object,
    path: context_module.SpecPath,
    dataset: collections.abc.Callable[[str], context_module.DatasetLocation | None],
) -> collections.abc.Iterator[tuple[str, context_module.SpecPath]]:
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
            action.location.dataset_location
            if dataset_id == selectors.CURRENT_ID
            else dataset(dataset_id)
        )
        if location is not None:
            for dimension_id in location.entity.dimension_ids:
                yield dimension_id, path
    elif isinstance(value, dict):
        for name, nested in value.items():
            yield from _iter_matching_keys(action, nested, (*path, name), dataset)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _iter_matching_keys(action, nested, (*path, index), dataset)


def validate_dataframe_reference(
    item: DataframeInput,
) -> context_module.ValidationResult:
    """Require a dataframe argument to reference a dataset."""
    if not isinstance(item.value, str) or not item.value.startswith(selectors.DATASET_PREFIX):
        return errors.SpecError(
            f"Dataframe argument {item.argument_id} must reference a dataset",
            code="invalid_mapping_dataset_input",
            path=item.path,
        )
    return None


def validate_dataframe_selector(
    item: DataframeInput,
) -> context_module.ValidationResult:
    """Reject a dataset ID selector where a dataframe is required."""
    if isinstance(item.value, str) and (
        item.value.endswith(selectors.ID_SELECTOR)
        or item.value.endswith(selectors.DIMENSION_IDS_SELECTOR)
    ):
        return errors.SpecError(
            f"Dataframe argument {item.argument_id} must reference a dataframe",
            code="invalid_mapping_dataset_input",
            path=item.path,
        )
    return None


def validate_dataframe_source(
    item: DataframeInput,
) -> context_module.ValidationResult:
    """Require a dataframe reference to resolve to a dataset."""
    if item.source is None:
        return errors.SpecError(
            f"Dataframe argument {item.argument_id} references unknown dataset {item.source_id}",
            code="invalid_mapping_dataset_input",
            path=item.path,
        )
    return None


def validate_dataset_count(item: ActionContract) -> context_module.ValidationResult:
    """Require dimensional operations to consume one foreign dataframe."""
    kind = item.action.kind
    if kind not in {functions.CONFORM, functions.COLLAPSE, functions.EXPAND}:
        return None

    expected_count = functions.KIND_DATAFRAME_INPUT_COUNTS[kind]
    dataset_ids = {
        argument.source.dataset.id
        for argument in item.dataframe_arguments
        if argument.source is not None
    }
    if len(item.dataframe_arguments) != expected_count or len(dataset_ids) != expected_count:
        return errors.SpecError(
            f"{kind.capitalize()} action must consume exactly {expected_count} foreign dataset(s)",
            code="invalid_mapping_dataset_input",
            path=(*item.action.location.path, "binding", "args"),
        )
    return None


def validate_matching_keys(
    item: ActionContract,
    dataset: collections.abc.Callable[[str], context_module.DatasetLocation | None],
) -> context_module.ValidationResult:
    """Require explicitly selected matching keys to exist on every participating dataset."""
    participants = (
        item.action.location.dataset_location,
        *(argument.source for argument in item.dataframe_arguments if argument.source is not None),
    )
    base_path = (*item.action.location.declaration_path, "binding", "args")
    for name, value in item.action.location.action.binding.args.items():
        for dimension_id, path in _iter_matching_keys(
            item.action, value, (*base_path, name), dataset
        ):
            for participant in participants:
                if dimension_id not in participant.dimensions:
                    return errors.SpecError(
                        f"Matching key {dimension_id} is not a dimension of dataset "
                        f"{participant.dataset.id}",
                        code="invalid_mapping_matching_key",
                        path=path,
                    )
    return None


def validate_input_feature_source_count(
    item: ActionContract,
    dimension_ids: frozenset[str],
    last_feature_owner: collections.abc.Callable[[str], context_module.DatasetLocation | None],
) -> context_module.ValidationResult:
    """Require dimensional input features to belong to at most one dataset."""
    kind = item.action.kind
    if kind not in {functions.CONFORM, functions.COLLAPSE, functions.EXPAND}:
        return None
    feature_dataset_ids = {
        owner.dataset.id
        for feature in item.action.inputs
        if feature not in dimension_ids
        and feature != selectors.CURRENT_ID
        and (owner := last_feature_owner(feature)) is not None
    }
    if len(feature_dataset_ids) > 1:
        return errors.SpecError(
            f"{kind.capitalize()} action inputs must belong to one source dataset",
            code="invalid_mapping_dataset_input",
            path=(*item.action.location.path, "features", "inputs"),
        )
    return None


def validate_foreign_dataframe(
    item: ActionContract,
) -> context_module.ValidationResult:
    """Reject the target dataset as a dimensional operation's dataframe input."""
    kind = item.action.kind
    if kind not in {functions.CONFORM, functions.COLLAPSE, functions.EXPAND}:
        return None
    if len(item.dataframe_arguments) != functions.KIND_DATAFRAME_INPUT_COUNTS[kind]:
        return None

    dataframe = item.dataframe_arguments[0]
    if dataframe.source_id == item.action.location.dataset.id:
        return errors.SpecError(
            f"{kind.capitalize()} action must reference a foreign source dataset",
            code="invalid_mapping_dataset_input",
            path=dataframe.path,
        )
    return None


def validate_dataframe_feature_source(
    item: ActionContract,
    dimension_ids: frozenset[str],
    last_feature_owner: collections.abc.Callable[[str], context_module.DatasetLocation | None],
) -> context_module.ValidationResult:
    """Require a dimensional dataframe argument to match the input feature owner."""
    kind = item.action.kind
    if kind not in {functions.CONFORM, functions.COLLAPSE, functions.EXPAND}:
        return None
    if len(item.dataframe_arguments) != functions.KIND_DATAFRAME_INPUT_COUNTS[kind]:
        return None
    feature_dataset_ids = {
        owner.dataset.id
        for feature in item.action.inputs
        if feature not in dimension_ids
        and feature != selectors.CURRENT_ID
        and (owner := last_feature_owner(feature)) is not None
    }
    if len(feature_dataset_ids) != 1:
        return None

    dataframe = item.dataframe_arguments[0]
    if dataframe.source is None:
        return None
    expected_source = next(iter(feature_dataset_ids))
    if dataframe.source.dataset.id != expected_source:
        return errors.SpecError(
            f"{kind.capitalize()} action must reference its foreign source dataset "
            f"{expected_source}",
            code="invalid_mapping_dataset_input",
            path=dataframe.path,
        )
    return None


def validate_dataframe_features(
    item: ActionContract,
    dimension_ids: frozenset[str],
    last_feature_owner: collections.abc.Callable[[str], context_module.DatasetLocation | None],
) -> context_module.ValidationResult:
    """Require conform and expand feature inputs to belong to dataframe inputs."""
    kind = item.action.kind
    if kind not in {functions.CONFORM, functions.EXPAND}:
        return None
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
            else (
                (owner := last_feature_owner(feature)) is None
                or owner.dataset.id not in dataset_ids
            )
        )
    )
    if unavailable_features:
        return errors.SpecError(
            f"{kind.capitalize()} action inputs must belong to its dataframe inputs: "
            + ", ".join(unavailable_features),
            code="invalid_mapping_feature_inputs",
            path=(*item.action.location.path, "features", "inputs"),
        )
    return None


def validate_read_inputs(item: context_module.ActionFacts) -> context_module.ValidationResult:
    """Reject feature inputs on read actions."""
    if item.kind == functions.READ and item.inputs:
        return errors.SpecError(
            "Read actions cannot declare feature inputs",
            code="invalid_mapping_feature_inputs",
            path=(*item.location.path, "features", "inputs"),
        )
    return None


def validate_target_input(item: ActionContract) -> context_module.ValidationResult:
    """Require vectorize and write to consume their target dataset."""
    kind = item.action.kind
    dataset_ids = {
        argument.source.dataset.id
        for argument in item.dataframe_arguments
        if argument.source is not None
    }
    if (
        kind in {functions.VECTORIZE, functions.WRITE}
        and item.action.location.dataset.id not in dataset_ids
    ):
        return errors.SpecError(
            f"{kind.capitalize()} action must consume its target dataset",
            code="invalid_mapping_dataset_input",
            path=(*item.action.location.path, "binding", "args"),
        )
    if kind == functions.WRITE:
        foreign = sorted(dataset_ids - {item.action.location.dataset.id})
        if foreign:
            return errors.SpecError(
                "Write action cannot publish a foreign dataset dataframe: " + ", ".join(foreign),
                code="invalid_mapping_dataset_input",
                path=(*item.action.location.path, "binding", "args"),
            )
    return None


def validate_local_features(
    item: ActionContract,
) -> context_module.ValidationResult:
    """Require vectorize and write feature inputs to belong to their target."""
    kind = item.action.kind
    foreign_features = sorted(
        feature for feature in item.action.inputs if feature not in item.action.local_features
    )
    if kind in {functions.VECTORIZE, functions.WRITE} and foreign_features:
        return errors.SpecError(
            f"{kind.capitalize()} action inputs must belong to its target dataset: "
            + ", ".join(foreign_features),
            code="invalid_mapping_feature_inputs",
            path=(*item.action.location.path, "features", "inputs"),
        )
    return None


def validate_collapse_source(
    item: ActionContract,
) -> context_module.ValidationResult:
    """Require collapse to consume its inferred source dataset."""
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
        return errors.SpecError(
            f"Collapse action must consume its source dataset {item.source.dataset.id}",
            code="invalid_mapping_dataset_input",
            path=(*item.action.location.path, "binding", "args"),
        )
    return None


def validate_collapse_dimensions(
    item: ActionContract,
) -> context_module.ValidationResult:
    """Require collapse to reduce source dimensionality."""
    if (
        item.action.kind == functions.COLLAPSE
        and item.source is not None
        and not item.action.dimensions < item.source.dimensions
    ):
        return errors.SpecError(
            "Collapse action source must have strictly higher dimensionality than its target",
            code="invalid_mapping_dimensions",
            path=(*item.action.location.path, "features", "inputs"),
        )
    return None


def validate_conform_dimensions(
    item: ActionContract,
) -> context_module.ValidationResult:
    """Require conform inputs to preserve target dimensionality."""
    if item.action.kind == functions.CONFORM and any(
        argument.source is not None and argument.source.dimensions != item.action.dimensions
        for argument in item.dataframe_arguments
    ):
        return errors.SpecError(
            "Conform action inputs must preserve target dimensionality",
            code="invalid_mapping_dimensions",
            path=(*item.action.location.path, "binding", "args"),
        )
    return None


def validate_expand_dimensions(
    item: ActionContract,
    last_feature_owner: collections.abc.Callable[[str], context_module.DatasetLocation | None],
) -> context_module.ValidationResult:
    """Require expand to use a declared feature from a lower-dimensional source."""
    if item.action.kind != functions.EXPAND:
        return None
    lower_dataset_ids = {
        argument.source.dataset.id
        for argument in item.dataframe_arguments
        if argument.source is not None and argument.source.dimensions < item.action.dimensions
    }
    has_lower_feature = any(
        (owner := last_feature_owner(feature)) is not None and owner.dataset.id in lower_dataset_ids
        for feature in item.action.inputs
    )
    if not lower_dataset_ids or not has_lower_feature:
        return errors.SpecError(
            EXPAND_INPUT_ERROR,
            code="invalid_mapping_dimensions",
            path=(*item.action.location.path, "binding", "args"),
        )
    return None
