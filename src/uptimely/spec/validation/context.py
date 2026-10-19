"""Per-invocation indexes and resource locations for ordered spec validation.

Construction retains duplicate candidates without validating them. Domain
modules apply checks; :mod:`uptimely.spec.validation.spec` coordinates phases
and passes successfully resolved collapse sources between them.
"""

from __future__ import annotations

import dataclasses
import typing

from uptimely.spec import model as spec_model
from uptimely.spec import references

__all__ = [
    "SpecValidationContext",
    "DatasetLocation",
    "FeatureOwner",
    "MappingLocation",
    "CollapseSource",
]


@dataclasses.dataclass(frozen=True)
class DatasetLocation:
    """A dataset together with the entity that declares it."""

    entity_id: str
    entity: spec_model.Entity
    dataset: spec_model.Dataset
    order: int


@dataclasses.dataclass(frozen=True)
class FeatureOwner:
    """The entity and dataset declaring a non-dimension feature."""

    entity_id: str
    entity: spec_model.Entity
    dataset: spec_model.Dataset
    order: int


@dataclasses.dataclass(frozen=True)
class MappingLocation:
    """A mapping declaration and the entity and dataset containing it."""

    entity_id: str
    entity: spec_model.Entity
    dataset: spec_model.Dataset
    mapping_id: str
    mapping: spec_model.Mapping

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the declaration identity after dataset IDs have been validated."""
        return self.entity_id, self.dataset.id, self.mapping_id

    @property
    def path(self) -> tuple[str | int, ...]:
        """Return the model-ID path used by mapping contract validation."""
        return (
            "entities",
            self.entity_id,
            "datasets",
            self.dataset.id,
            "mappings",
            self.mapping.id,
        )

    @property
    def declaration_path(self) -> tuple[str | int, ...]:
        """Return the dictionary-key path used by binding validation."""
        return (*self.path[:-1], self.mapping_id)


@dataclasses.dataclass(frozen=True)
class CollapseSource:
    """The entity and dataset successfully inferred for a collapse mapping."""

    entity: spec_model.Entity
    dataset: spec_model.Dataset


type CollapseSources = dict[tuple[str, str, str], CollapseSource]


@dataclasses.dataclass(frozen=True)
class SpecValidationContext:
    """Precomputed indexes shared by the ordered spec validation rules.

    Index values retain every candidate so duplicate IDs are not hidden during
    construction. Rules that require uniqueness still report errors at their
    original validation point.
    """

    model: spec_model.Spec
    dimension_ids: frozenset[str]
    datasets_by_id: dict[str, tuple[DatasetLocation, ...]]
    feature_names: frozenset[str]
    feature_owners: dict[str, tuple[FeatureOwner, ...]]

    def iter_mappings(self) -> typing.Iterator[MappingLocation]:
        """Yield locations without resolving functions or rejecting declarations."""
        for entity_id, dataset, mapping_id, mapping in references.iter_mapping_items(self.model):
            yield MappingLocation(
                entity_id, self.model.entities[entity_id], dataset, mapping_id, mapping
            )

    @classmethod
    def build(cls, model: spec_model.Spec) -> SpecValidationContext:
        """Build all lookup indexes without raising validation errors."""
        dimension_ids = frozenset(model.dimensions)
        datasets: dict[str, list[DatasetLocation]] = {}
        feature_names: set[str] = set()
        feature_owners: dict[str, list[FeatureOwner]] = {}
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

        return cls(
            model=model,
            dimension_ids=dimension_ids,
            datasets_by_id={key: tuple(value) for key, value in datasets.items()},
            feature_names=frozenset(feature_names),
            feature_owners={key: tuple(value) for key, value in feature_owners.items()},
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
