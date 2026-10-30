"""Traversal and structural reference discovery for spec document bindings."""

from __future__ import annotations

import typing

import pydantic

from . import functions, selectors

if typing.TYPE_CHECKING:
    from . import model as spec_model


def iter_actions(
    document: spec_model.Spec,
) -> typing.Iterator[tuple[str, spec_model.Dataset, spec_model.Action]]:
    """Yield entity identifiers, datasets, and actions in declaration order."""
    for entity_id, dataset, _action_id, action in iter_action_items(document):
        yield entity_id, dataset, action


def iter_action_items(
    document: spec_model.Spec,
) -> typing.Iterator[tuple[str, spec_model.Dataset, str, spec_model.Action]]:
    """Yield action declarations with their dictionary keys in declaration order."""
    for entity_id, entity in document.entities.items():
        for dataset in entity.datasets.values():
            for action_id, action in dataset.actions.items():
                yield entity_id, dataset, action_id, action


def action_kind(
    action: spec_model.Action, catalog: spec_model.FunctionCatalog
) -> functions.FunctionKindId:
    """Return the declared kind of a action's function."""
    function = catalog.get(action.binding.function)
    if function is None:
        raise ValueError(
            f"Action {action.id} function {action.binding.function} must resolve "
            "to a declared function"
        )
    return function.kind


def structural_references(value: typing.Any, prefix: str) -> list[str]:
    """Collect reference identifiers from nested bindings, retaining their order."""
    return [identifier for identifier, _ in _structural_reference_paths(value, prefix, ())]


def structural_reference_paths(
    value: typing.Any, prefix: str, path: tuple[str | int, ...]
) -> list[tuple[str, tuple[str | int, ...]]]:
    """Collect structural references with their binding paths."""
    return _structural_reference_paths(value, prefix, path)


def _structural_reference_paths(
    value: typing.Any, prefix: str, path: tuple[str | int, ...]
) -> list[tuple[str, tuple[str | int, ...]]]:
    """Walk nested binding values once, retaining each matching reference path."""
    if isinstance(value, pydantic.BaseModel):
        value = value.model_dump()
    if isinstance(value, str):
        return [(_structural_identifier(value, prefix), path)] if value.startswith(prefix) else []
    if isinstance(value, dict):
        return [
            reference
            for key, nested in value.items()
            for reference in _structural_reference_paths(nested, prefix, (*path, key))
        ]
    if isinstance(value, list):
        return [
            reference
            for index, nested in enumerate(value)
            for reference in _structural_reference_paths(nested, prefix, (*path, index))
        ]
    return []


def _structural_identifier(value: str, prefix: str) -> str:
    """Remove a structural selector suffix while retaining its resource ID."""
    identifier = value.removeprefix(prefix)
    if prefix == selectors.DATASET_PREFIX:
        return (
            identifier.removesuffix(selectors.DIMENSION_IDS_SELECTOR)
            .removesuffix(selectors.DATAFRAME_SELECTOR)
            .removesuffix(selectors.ID_SELECTOR)
        )
    return identifier.removesuffix(selectors.ID_SELECTOR)
