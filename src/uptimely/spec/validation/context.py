"""Shared declaration indexes and compact validation location types.

Index construction retains unresolved references and duplicate candidates.
Topic-specific rules own their preparation and decide which facts are invalid.
"""

from __future__ import annotations

import dataclasses
import typing

from uptimely.spec import model as spec_model
from uptimely.spec import references

from .. import functions, selectors

type SpecPath = tuple[str | int, ...]
type ActionKey = tuple[str, str]
type ValidationResult = ValueError | None


@dataclasses.dataclass(frozen=True)
class DatasetLocation:
    """A dataset and the entity declaring it, also used for owners and sources."""

    entity_id: str
    entity: spec_model.Entity
    dataset: spec_model.Dataset
    dimensions: frozenset[str]

    @property
    def key(self) -> tuple[str, str]:
        """Return the entity and dataset identity."""
        return self.entity_id, self.dataset.id

    @property
    def path(self) -> SpecPath:
        """Return the dataset's semantic path."""
        return ("entities", self.entity_id, "datasets", self.dataset.id)


@dataclasses.dataclass(frozen=True)
class ActionLocation:
    """An action location retaining dictionary-key and model-ID identities."""

    dataset_location: DatasetLocation
    action_id: str
    action: spec_model.Action

    @property
    def entity_id(self) -> str:
        """Return the declaring entity ID."""
        return self.dataset_location.entity_id

    @property
    def entity(self) -> spec_model.Entity:
        """Return the declaring entity."""
        return self.dataset_location.entity

    @property
    def dataset(self) -> spec_model.Dataset:
        """Return the declared dataset."""
        return self.dataset_location.dataset

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the declaration identity."""
        return (*self.dataset_location.key, self.action_id)

    @property
    def path(self) -> SpecPath:
        """Return the model-ID path used by action contracts."""
        return (*self.dataset_location.path, "actions", self.action.id)

    @property
    def declaration_path(self) -> SpecPath:
        """Return the dictionary-key path used by bindings."""
        return (*self.path[:-1], self.action_id)


@dataclasses.dataclass(frozen=True)
class ActionFacts:
    """Shared action declarations, explicit dependencies, and validated selectors."""

    location: ActionLocation
    function: spec_model.FunctionTemplate | None
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    feature_selectors: tuple[str, ...]
    dataset_references: tuple[str, ...]
    dimension_references: tuple[str, ...]
    dimension_reference_paths: tuple[tuple[str, SpecPath], ...]

    @property
    def dimensions(self) -> frozenset[str]:
        """Return the dimensions declared by this action's entity."""
        return self.location.dataset_location.dimensions

    @property
    def local_features(self) -> frozenset[str]:
        """Return the dataset's features together with its entity dimensions."""
        return frozenset(self.location.dataset.features) | self.dimensions

    @property
    def kind(self) -> functions.FunctionKind | None:
        """Return the declared kind without requiring function resolution."""
        return self.function.kind if self.function is not None else None


@dataclasses.dataclass(frozen=True)
class SpecValidationContext:
    """Fresh, non-validating indexes shared by topic-specific validation."""

    model: spec_model.Spec
    dimension_ids: frozenset[str]
    datasets: tuple[DatasetLocation, ...]
    datasets_by_id: dict[str, tuple[DatasetLocation, ...]]
    feature_names: frozenset[str]
    feature_owners: dict[str, tuple[DatasetLocation, ...]]
    actions: tuple[ActionFacts, ...]
    duplicate_dataset: tuple[DatasetLocation, DatasetLocation] | None
    duplicate_feature: str | None

    @classmethod
    def build(cls, model: spec_model.Spec) -> SpecValidationContext:
        """Collect shared declarations without rejecting duplicates or missing functions."""
        dimension_ids = frozenset(model.dimensions)
        datasets: list[DatasetLocation] = []
        datasets_by_id: dict[str, list[DatasetLocation]] = {}
        feature_names: set[str] = set()
        owners: dict[str, list[DatasetLocation]] = {}
        duplicate_dataset = None
        duplicate_feature = None
        actions: list[ActionFacts] = []
        for entity_id, entity in model.entities.items():
            for dataset in entity.datasets.values():
                location = DatasetLocation(
                    entity_id, entity, dataset, frozenset(entity.dimension_ids)
                )
                datasets.append(location)
                dataset_candidates = datasets_by_id.setdefault(dataset.id, [])
                if duplicate_dataset is None and dataset_candidates:
                    duplicate_dataset = location, dataset_candidates[0]
                dataset_candidates.append(location)
                feature_names.update(dataset.features)
                for feature_id in dataset.features:
                    if feature_id not in dimension_ids:
                        feature_candidates = owners.setdefault(feature_id, [])
                        if duplicate_feature is None and feature_candidates:
                            duplicate_feature = feature_id
                        feature_candidates.append(location)
                for action_id, action in dataset.actions.items():
                    action_location = ActionLocation(location, action_id, action)
                    actions.append(
                        ActionFacts(
                            location=action_location,
                            function=model.functions.get(action.binding.function),
                            inputs=tuple(action.input_features),
                            outputs=tuple(action.output_features),
                            feature_selectors=tuple(
                                references.structural_references(
                                    action.binding.args, selectors.FEATURE_PREFIX
                                )
                            ),
                            dataset_references=tuple(
                                references.structural_references(
                                    action.binding.args, selectors.DATASET_PREFIX
                                )
                            ),
                            dimension_references=tuple(
                                references.structural_references(
                                    action.binding.args, selectors.DIMENSION_PREFIX
                                )
                            ),
                            dimension_reference_paths=tuple(
                                references.structural_reference_paths(
                                    action.binding.args,
                                    selectors.DIMENSION_PREFIX,
                                    (
                                        *action_location.declaration_path,
                                        "binding",
                                        "args",
                                    ),
                                )
                            ),
                        )
                    )
        return cls(
            model=model,
            dimension_ids=dimension_ids,
            datasets=tuple(datasets),
            datasets_by_id={key: tuple(value) for key, value in datasets_by_id.items()},
            feature_names=frozenset(feature_names) | dimension_ids,
            feature_owners={key: tuple(value) for key, value in owners.items()},
            actions=tuple(actions),
            duplicate_dataset=duplicate_dataset,
            duplicate_feature=duplicate_feature,
        )

    def iter_actions(self) -> typing.Iterator[ActionLocation]:
        """Yield action locations in declaration order."""
        return (item.location for item in self.actions)

    def dataset(self, dataset_id: str) -> DatasetLocation | None:
        """Return the last candidate, matching historical catalog indexing."""
        candidates = self.datasets_by_id.get(dataset_id, ())
        return candidates[-1] if candidates else None

    def first_feature_owner(self, feature_id: str) -> DatasetLocation | None:
        """Return the first owner, matching early dependency validation."""
        candidates = self.feature_owners.get(feature_id, ())
        return candidates[0] if candidates else None

    def last_feature_owner(self, feature_id: str) -> DatasetLocation | None:
        """Return the last owner, matching action contract lookup."""
        candidates = self.feature_owners.get(feature_id, ())
        return candidates[-1] if candidates else None
