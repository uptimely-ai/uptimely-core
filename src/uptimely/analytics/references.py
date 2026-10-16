"""Traversal and resolution helpers for analytics document bindings."""

from __future__ import annotations

import typing

import pydantic

from uptimely import contracts

if typing.TYPE_CHECKING:
    from . import model as analytics_model


def mapping_operation(
    mapping: analytics_model.Mapping, catalog: analytics_model.FunctionCatalog
) -> str:
    """Return the declared operation of a mapping's function."""
    function = catalog.get(mapping.binding.function)
    if function is None:
        raise ValueError(
            f"Mapping {mapping.id} function {mapping.binding.function} must resolve "
            "to a declared function"
        )
    return function.operation


def collapse_input_dataset(
    analytics_definition: analytics_model.Analytics, mapping: analytics_model.Mapping
) -> tuple[analytics_model.Entity, analytics_model.Dataset]:
    """Infer one input dataset from a collapse's bound non-dimension features.

    Args:
        analytics_definition: Analytics model containing feature ownership.
        mapping: Collapse binding whose inputs determine the dataset.

    Returns:
        The owning entity and the single inferred input dataset.

    Raises:
        ValueError: Inputs are missing, unknown, ambiguous, or span datasets.
    """
    inputs = [
        feature
        for feature in mapping.input_features
        if feature != contracts.CURRENT_ID and feature not in analytics_definition.dimensions
    ]
    if not inputs:
        raise ValueError(f"Collapse {mapping.id} must reference a source feature")
    owners: dict[str, tuple[analytics_model.Entity, analytics_model.Dataset]] = {}
    for feature in inputs:
        matches = [
            (entity, dataset)
            for entity in analytics_definition.entities.values()
            for dataset in entity.datasets
            if feature in dataset.features
        ]
        if not matches:
            raise ValueError(f"Collapse {mapping.id} references unknown input feature: {feature}")
        if len(matches) != 1:
            raise ValueError(f"Collapse {mapping.id} has ambiguous input feature: {feature}")
        entity, dataset = matches[0]
        owners[dataset.id] = (entity, dataset)
    if len(owners) != 1:
        raise ValueError(
            f"Collapse {mapping.id} input features must belong to one dataset; "
            "use expand to combine inputs from different datasets"
        )
    return next(iter(owners.values()))


def dataset_dependencies(args: dict[str, typing.Any], current_dataset: str) -> list[str]:
    """Return datasets required as dataframe arguments, excluding identifier selectors."""
    references: list[str] = []

    def collect(value: object) -> None:
        if (
            isinstance(value, str)
            and value.startswith(contracts.DATASET_PREFIX)
            and not value.endswith(contracts.ID_SELECTOR)
        ):
            identifier = value.removeprefix(contracts.DATASET_PREFIX).removesuffix(
                contracts.DATAFRAME_SELECTOR
            )
            references.append(current_dataset if identifier == contracts.CURRENT_ID else identifier)
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
) -> dict[str, typing.Any]:
    """Resolve structural references to identifiers used by the execution plan."""
    if not isinstance(args, dict):
        return args or {}

    def resolve_value(value: object) -> object:
        value = _as_plain(value)
        if isinstance(value, str):
            return resolve_structural_reference(value, dataset_id, feature_id)
        if isinstance(value, dict):
            return {key: resolve_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [resolve_value(item) for item in value]
        return value

    return {key: resolve_value(value) for key, value in args.items()}


def resolve_structural_reference(
    value: str, current_dataset_id: str, feature_id: str | None = None
) -> str:
    """Return the identifier represented by a structural binding reference."""
    if value in {
        f"{contracts.FEATURE_PREFIX}{contracts.CURRENT_ID}",
        f"{contracts.FEATURE_PREFIX}{contracts.CURRENT_ID}{contracts.ID_SELECTOR}",
    }:
        return feature_id if feature_id is not None else value
    for prefix in contracts.STRUCTURAL_PREFIXES:
        if value.startswith(prefix):
            identifier = value.removeprefix(prefix)
            if prefix == contracts.DATASET_PREFIX:
                identifier = identifier.removesuffix(contracts.DATAFRAME_SELECTOR).removesuffix(
                    contracts.ID_SELECTOR
                )
            else:
                identifier = identifier.removesuffix(contracts.ID_SELECTOR)
            return (
                current_dataset_id
                if prefix == contracts.DATASET_PREFIX and identifier == contracts.CURRENT_ID
                else identifier
            )
    return value


def _as_plain(value: object) -> object:
    """Convert Pydantic binding models before recursively inspecting them."""
    return value.model_dump() if isinstance(value, pydantic.BaseModel) else value
