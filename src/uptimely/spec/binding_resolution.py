"""Resolve structural references in spec binding arguments."""

from __future__ import annotations

import collections.abc
import typing

import pydantic

from . import selectors


def dataset_dependencies(args: dict[str, typing.Any], current_dataset: str) -> list[str]:
    """Return dataframe datasets required by nested arguments, in declaration order."""
    references: list[str] = []

    def collect(value: object) -> None:
        if (
            isinstance(value, str)
            and value.startswith(selectors.DATASET_PREFIX)
            and not value.endswith(selectors.ID_SELECTOR)
            and not value.endswith(selectors.DIMENSION_IDS_SELECTOR)
        ):
            identifier = value.removeprefix(selectors.DATASET_PREFIX).removesuffix(
                selectors.DATAFRAME_SELECTOR
            )
            references.append(current_dataset if identifier == selectors.CURRENT_ID else identifier)
        elif isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(args)
    return list(dict.fromkeys(references))


def resolve_binding_args(
    args: dict[str, typing.Any] | None,
    dataset_id: str,
    feature_id: str | None = None,
    dimension_ids_by_dataset: collections.abc.Mapping[str, collections.abc.Sequence[str]]
    | None = None,
) -> dict[str, typing.Any]:
    """Resolve structural references to identifiers used by the execution plan."""
    if args is None:
        return {}
    if not isinstance(args, dict):
        raise TypeError("Binding arguments must be a dictionary or None")

    def resolve_value(value: object) -> object:
        value = _as_plain(value)
        if isinstance(value, str):
            return resolve_structural_reference(
                value, dataset_id, feature_id, dimension_ids_by_dataset
            )
        if isinstance(value, dict):
            return {key: resolve_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [resolve_value(item) for item in value]
        return value

    return {key: resolve_value(value) for key, value in args.items()}


def resolve_structural_reference(
    value: str,
    current_dataset_id: str,
    feature_id: str | None = None,
    dimension_ids_by_dataset: collections.abc.Mapping[str, collections.abc.Sequence[str]]
    | None = None,
) -> str | list[str]:
    """Return the identifier represented by a structural binding reference."""
    if value in {
        f"{selectors.FEATURE_PREFIX}{selectors.CURRENT_ID}",
        f"{selectors.FEATURE_PREFIX}{selectors.CURRENT_ID}{selectors.ID_SELECTOR}",
    }:
        return feature_id if feature_id is not None else value
    for prefix in selectors.STRUCTURAL_PREFIXES:
        if value.startswith(prefix):
            identifier = value.removeprefix(prefix)
            if prefix == selectors.DATASET_PREFIX:
                if identifier.endswith(selectors.DIMENSION_IDS_SELECTOR):
                    identifier = identifier.removesuffix(selectors.DIMENSION_IDS_SELECTOR)
                    dataset_id = (
                        current_dataset_id if identifier == selectors.CURRENT_ID else identifier
                    )
                    if (
                        dimension_ids_by_dataset is None
                        or dataset_id not in dimension_ids_by_dataset
                    ):
                        raise ValueError(f"Cannot resolve dimension IDs for dataset {dataset_id}")
                    return list(dimension_ids_by_dataset[dataset_id])
                identifier = identifier.removesuffix(selectors.DATAFRAME_SELECTOR).removesuffix(
                    selectors.ID_SELECTOR
                )
            else:
                identifier = identifier.removesuffix(selectors.ID_SELECTOR)
            return (
                current_dataset_id
                if prefix == selectors.DATASET_PREFIX and identifier == selectors.CURRENT_ID
                else identifier
            )
    return value


def _as_plain(value: object) -> object:
    """Convert Pydantic binding models before recursively inspecting them."""
    return value.model_dump() if isinstance(value, pydantic.BaseModel) else value
