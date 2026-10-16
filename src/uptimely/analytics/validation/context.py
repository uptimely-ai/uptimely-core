"""Shared analytics validation traversal helpers."""

from __future__ import annotations

import dataclasses
import typing

from uptimely import contracts

from .. import model as analytics_model
from ..model import functions as functions_module

__all__ = [
    "AnalyticsValidationContext",
    "DatasetLocation",
    "FeatureOwner",
    "MappingProducer",
    "_structural_references",
]


@dataclasses.dataclass(frozen=True)
class DatasetLocation:
    """A dataset together with the entity that declares it."""

    entity_id: str
    entity: analytics_model.Entity
    dataset: analytics_model.Dataset
    order: int


@dataclasses.dataclass(frozen=True)
class FeatureOwner:
    """The entity and dataset declaring a non-dimension feature."""

    entity_id: str
    entity: analytics_model.Entity
    dataset: analytics_model.Dataset
    order: int


@dataclasses.dataclass(frozen=True)
class MappingProducer:
    """A mapping that declares an output feature."""

    dataset_id: str
    mapping_id: str


@dataclasses.dataclass(frozen=True)
class AnalyticsValidationContext:
    """Precomputed indexes shared by the ordered analytics validation rules.

    Index values retain every candidate so duplicate IDs are not hidden during
    construction. Rules that require uniqueness still report errors at their
    original validation point.
    """

    model: analytics_model.Analytics
    dimension_ids: frozenset[str]
    datasets_by_id: dict[str, tuple[DatasetLocation, ...]]
    feature_names: frozenset[str]
    feature_owners: dict[str, tuple[FeatureOwner, ...]]
    feature_producers: dict[str, tuple[MappingProducer, ...]]
    function_categories: dict[str, dict[str, analytics_model.FunctionTemplate]]

    @classmethod
    def build(cls, model: analytics_model.Analytics) -> AnalyticsValidationContext:
        """Build all lookup indexes without raising validation errors."""
        dimension_ids = frozenset(model.dimensions)
        datasets: dict[str, list[DatasetLocation]] = {}
        feature_names: set[str] = set()
        feature_owners: dict[str, list[FeatureOwner]] = {}
        feature_producers: dict[str, list[MappingProducer]] = {}
        dataset_order = 0
        feature_order = 0

        for entity_id, entity in model.entities.items():
            for dataset in entity.datasets:
                location = DatasetLocation(entity_id, entity, dataset, dataset_order)
                dataset_order += 1
                datasets.setdefault(dataset.id, []).append(location)
                for feature_id in dataset.features:
                    feature_names.add(feature_id)
                    if feature_id not in dimension_ids:
                        feature_owners.setdefault(feature_id, []).append(
                            FeatureOwner(entity_id, entity, dataset, feature_order)
                        )
                    feature_order += 1
                for mapping in dataset.mappings.values():
                    for feature_id in mapping.output_features:
                        if feature_id not in dimension_ids:
                            feature_producers.setdefault(feature_id, []).append(
                                MappingProducer(dataset.id, mapping.id)
                            )

        categories = {
            operation: model.functions.by_operation(operation)
            for operation in functions_module.FUNCTION_OPERATIONS
        }
        return cls(
            model=model,
            dimension_ids=dimension_ids,
            datasets_by_id={key: tuple(value) for key, value in datasets.items()},
            feature_names=frozenset(feature_names),
            feature_owners={key: tuple(value) for key, value in feature_owners.items()},
            feature_producers={key: tuple(value) for key, value in feature_producers.items()},
            function_categories=categories,
        )

    def dataset(self, dataset_id: str) -> DatasetLocation | None:
        """Return the last matching dataset, preserving previous dict indexing."""
        candidates = self.datasets_by_id.get(dataset_id, ())
        return candidates[-1] if candidates else None

    def first_feature_owner(self, feature_id: str) -> FeatureOwner | None:
        """Return the first feature owner, matching ordered parser validation."""
        candidates = self.feature_owners.get(feature_id, ())
        return candidates[0] if candidates else None

    def last_feature_owner(self, feature_id: str) -> FeatureOwner | None:
        """Return the last feature owner, matching previous catalog indexing."""
        candidates = self.feature_owners.get(feature_id, ())
        return candidates[-1] if candidates else None

    def last_feature_producer(self, feature_id: str) -> MappingProducer | None:
        """Return the last mapping producer, matching previous index construction."""
        candidates = self.feature_producers.get(feature_id, ())
        return candidates[-1] if candidates else None

    def first_duplicate_dataset(self) -> tuple[DatasetLocation, DatasetLocation] | None:
        """Return the duplicate dataset occurrence encountered first in model order."""
        duplicates = (
            (candidates[0], candidates[1])
            for candidates in self.datasets_by_id.values()
            if len(candidates) > 1
        )
        return min(duplicates, key=lambda pair: pair[1].order, default=None)

    def first_duplicate_feature(self) -> str | None:
        """Return the first duplicated feature encountered in model order."""
        duplicates = (
            (candidates[1].order, feature_id)
            for feature_id, candidates in self.feature_owners.items()
            if len(candidates) > 1
        )
        return min(duplicates, default=(0, None))[1]


def _structural_references(value: typing.Any, prefix: str) -> list[str]:
    """Return identifiers from nested structural reference strings."""
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, str):
        return (
            [
                value.removeprefix(prefix)
                .removesuffix(contracts.ID_SELECTOR)
                .removesuffix(contracts.DATAFRAME_SELECTOR)
            ]
            if value.startswith(prefix)
            else []
        )
    if isinstance(value, dict):
        return [
            identifier
            for nested in value.values()
            for identifier in _structural_references(nested, prefix)
        ]
    if isinstance(value, list):
        return [
            identifier for nested in value for identifier in _structural_references(nested, prefix)
        ]
    return []
