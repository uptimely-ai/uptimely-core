"""Traversal and structural reference discovery for spec document bindings."""

from __future__ import annotations

import typing

import pydantic

from . import selectors

if typing.TYPE_CHECKING:
    from . import model as spec_model


def iter_mappings(
    document: spec_model.Spec,
) -> typing.Iterator[tuple[str, spec_model.Dataset, spec_model.Mapping]]:
    """Yield entity identifiers, datasets, and mappings in declaration order."""
    for entity_id, dataset, _mapping_id, mapping in iter_mapping_items(document):
        yield entity_id, dataset, mapping


def iter_mapping_items(
    document: spec_model.Spec,
) -> typing.Iterator[tuple[str, spec_model.Dataset, str, spec_model.Mapping]]:
    """Yield mapping declarations with their dictionary keys in declaration order."""
    for entity_id, entity in document.entities.items():
        for dataset in entity.datasets.values():
            for mapping_id, mapping in dataset.mappings.items():
                yield entity_id, dataset, mapping_id, mapping


def mapping_operation(mapping: spec_model.Mapping, catalog: spec_model.FunctionCatalog) -> str:
    """Return the declared operation of a mapping's function."""
    function = catalog.get(mapping.binding.function)
    if function is None:
        raise ValueError(
            f"Mapping {mapping.id} function {mapping.binding.function} must resolve "
            "to a declared function"
        )
    return function.operation


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
