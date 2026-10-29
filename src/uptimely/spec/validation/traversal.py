"""Read-only traversal and lookup helpers for atomic spec validators."""

from __future__ import annotations

import collections.abc
import dataclasses

from uptimely.spec import functions, references, selectors
from uptimely.spec import model as spec_model

type SpecPath = tuple[str | int, ...]
type ActionKey = tuple[str, str]


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
    def path(self) -> tuple[str, ...]:
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
    """One action's declarations, explicit dependencies, and structural selectors."""

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


def iter_datasets(model: spec_model.Spec) -> collections.abc.Iterator[DatasetLocation]:
    """Yield datasets with their owning entity and declaration location."""
    for entity_id, entity in model.entities.items():
        for dataset in entity.datasets.values():
            yield DatasetLocation(entity_id, entity, dataset, frozenset(entity.dimension_ids))


def iter_actions(model: spec_model.Spec) -> collections.abc.Iterator[ActionFacts]:
    """Yield action declarations and structural references without validating them."""
    for location in iter_datasets(model):
        for action_id, action in location.dataset.actions.items():
            action_location = ActionLocation(location, action_id, action)
            yield ActionFacts(
                location=action_location,
                function=model.functions.root.get(action.binding.function),
                inputs=tuple(action.input_features),
                outputs=tuple(action.output_features),
                feature_selectors=tuple(
                    references.structural_references(action.binding.args, selectors.FEATURE_PREFIX)
                ),
                dataset_references=tuple(
                    references.structural_references(action.binding.args, selectors.DATASET_PREFIX)
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
                        (*action_location.declaration_path, "binding", "args"),
                    )
                ),
            )


def dataset_index(model: spec_model.Spec) -> dict[str, DatasetLocation]:
    """Index datasets after dataset ID uniqueness has been validated."""
    return {location.dataset.id: location for location in iter_datasets(model)}


def feature_owners(model: spec_model.Spec) -> dict[str, tuple[DatasetLocation, ...]]:
    """Collect all non-dimension feature owners, retaining ambiguous declarations."""
    owners: dict[str, list[DatasetLocation]] = {}
    for location in iter_datasets(model):
        for feature in location.dataset.features:
            if feature not in model.dimensions:
                owners.setdefault(feature, []).append(location)
    return {feature: tuple(locations) for feature, locations in owners.items()}


def feature_owner_index(model: spec_model.Spec) -> dict[str, DatasetLocation]:
    """Index feature owners after feature ownership uniqueness has been validated."""
    return {feature: owners[0] for feature, owners in feature_owners(model).items()}


def feature_names(model: spec_model.Spec) -> frozenset[str]:
    """Return all declared features, including dimensions."""
    return frozenset(model.dimensions).union(
        *(location.dataset.features for location in iter_datasets(model))
    )
