"""Python-friendly dataset declaration."""

from __future__ import annotations

import dataclasses
import typing
from collections import abc
from typing import TYPE_CHECKING

from uptimely.spec import catalog as function_catalog
from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.model import common as spec_common

from . import actions, ref
from . import dimension as dimension_module

if TYPE_CHECKING:
    from .entity import Entity

__all__ = [
    "Dataset",
    "DatasetRegistry",
    "Order",
    "RowScope",
]

_ACTION_KINDS: typing.Final[dict[str, tuple[functions.FunctionKindId, ...]]] = {
    "producers": (
        functions.READ,
        functions.COLLAPSE,
        functions.CONFORM,
        functions.EXPAND,
        functions.VECTORIZE,
    ),
    "publishers": (functions.WRITE,),
    "pipelines": (functions.ESCAPE,),
}


@dataclasses.dataclass(frozen=True)
class RowScope:
    """The conceptual row subset represented by a dataset."""

    grain: str = ""
    filtering: str = ""
    coverage: str = ""

    def to_model(self) -> spec_model.RowScope:
        """Convert this row scope definition to its document model."""
        return spec_model.RowScope(
            grain=self.grain,
            filtering=self.filtering,
            coverage=self.coverage,
        )


@dataclasses.dataclass(frozen=True)
class Order:
    """Declare a logical ordering key, not a required physical sort.

    Args:
        dimension: A dimension reference created by ``ref.dimension`` or its
            ``$dimensions.<id>`` reference string used in spec documents.
        direction: Ascending (``asc``) or descending (``desc``) order.
    """

    dimension: ref.Reference | str
    direction: typing.Literal["asc", "desc"]

    def to_model(self) -> spec_model.Order:
        """Convert this ordering key to its document model."""
        return spec_model.Order(
            dimension=(
                self.dimension.to_model()
                if isinstance(self.dimension, ref.Reference)
                else self.dimension
            ),
            direction=self.direction,
        )


class Dataset:
    """Observation scope with declarative producers, publishers, and pipelines.

    Each collection contains Actions with IDs unique across the dataset.
    Subclasses inherit collections normally; assigning a collection replaces it.
    Feature metadata belongs to each action's outputs, not a separate inventory.
    """

    id: str
    name: str | None = None
    description: str | None = None
    entity: str | Entity | None = None
    row_scope = RowScope()
    order: abc.Sequence[Order] = ()
    producers: abc.Sequence[actions.Action] = ()
    publishers: abc.Sequence[actions.Action] = ()
    pipelines: abc.Sequence[actions.Action] = ()

    def __init__(
        self,
        *,
        id: str | None = None,
        producers: abc.Sequence[actions.Action] | None = None,
        publishers: abc.Sequence[actions.Action] | None = None,
        pipelines: abc.Sequence[actions.Action] | None = None,
        name: str | None = None,
        description: str | None = None,
        entity: str | Entity | None = None,
        row_scope: RowScope | None = None,
        order: abc.Sequence[Order] | None = None,
    ) -> None:
        if id is not None:
            self.id = id
        if not isinstance(getattr(self, "id", None), str) or not self.id.strip():
            raise ValueError("Dataset requires a non-empty id")
        if name is not None:
            self.name = name
        elif self.name is None:
            self.name = spec_common.humanize_identifier(self.id)
        if description is not None:
            self.description = description
        if entity is not None:
            self.entity = entity
        if row_scope is not None:
            self.row_scope = row_scope
        if order is not None:
            self.order = tuple(order)
        self.producers = self._action_group("producers", producers, self.producers)
        self.publishers = self._action_group("publishers", publishers, self.publishers)
        self.pipelines = self._action_group("pipelines", pipelines, self.pipelines)
        _ = self.actions

    @property
    def actions(self) -> dict[str, actions.Action]:
        """Return all declared actions keyed by ID after validating their groups."""
        collected: dict[str, actions.Action] = {}
        for group_name, group_actions, allowed_kinds in (
            ("producers", self.producers, _ACTION_KINDS["producers"]),
            ("publishers", self.publishers, _ACTION_KINDS["publishers"]),
            ("pipelines", self.pipelines, _ACTION_KINDS["pipelines"]),
        ):
            group_actions = self._action_group(group_name, group_actions, ())
            for action in group_actions:
                if action.kind not in allowed_kinds:
                    raise ValueError(
                        f"Dataset '{self.id}', action '{action.id}': "
                        f"kind '{action.kind}' is not allowed in {group_name}; "
                        f"expected {', '.join(allowed_kinds)}"
                    )
                if action.outputs and not functions.FUNCTION_KINDS[action.kind].produces_features:
                    raise ValueError(
                        f"Dataset '{self.id}', action '{action.id}': "
                        f"{action.kind.capitalize()} action cannot produce features"
                    )
                if action.id in collected:
                    raise ValueError(f"Dataset '{self.id}' has duplicate action ID '{action.id}'")
                collected[action.id] = action
        return collected

    def _action_group(
        self,
        group_name: str,
        provided_actions: abc.Sequence[actions.Action] | None,
        inherited_actions: abc.Sequence[actions.Action],
    ) -> list[actions.Action]:
        """Validate and copy one producer, publisher, or pipeline action group."""
        group_actions = provided_actions if provided_actions is not None else inherited_actions
        if not isinstance(group_actions, abc.Sequence) or isinstance(group_actions, (str, bytes)):
            raise TypeError(f"Dataset '{self.id}' {group_name} must be a sequence of Actions")
        if any(not isinstance(action, actions.Action) for action in group_actions):
            raise TypeError(f"Dataset '{self.id}' {group_name} must contain Actions")
        return list(group_actions)

    def to_model(self) -> spec_model.Dataset:
        """Build the canonical dataset, rejecting duplicate feature producers."""
        return spec_model.Dataset(
            id=self.id,
            name=self.name,
            description=self.description,
            row_scope=self.row_scope.to_model(),
            order=[key.to_model() for key in self.order],
            features=self._feature_metadata,
            actions=self._action_models,
        )

    @property
    def _entity_dimensions(self) -> tuple[dimension_module.Dimension, ...]:
        """Resolve the owning entity's dimension declarations."""
        if isinstance(self.entity, str):
            raise ValueError("Resolve entity IDs through Spec before converting a dataset")
        dimensions = self.entity.dimensions if self.entity is not None else ()
        resolved: list[dimension_module.Dimension] = []
        for key in dimensions:
            if isinstance(key, str):
                raise ValueError("Resolve dimension IDs through Spec before converting a dataset")
            if not isinstance(key, dimension_module.Dimension):
                raise TypeError("dataset dimensions must contain Dimension declarations")
            resolved.append(key)
        return tuple(resolved)

    @property
    def _action_models(self) -> dict[str, spec_model.Action]:
        """Convert actions and add entity-key outputs to source actions."""
        actions_by_id: dict[str, spec_model.Action] = {}
        for name, declaration in self.actions.items():
            action_model = self._action_model(name, declaration)
            if declaration.kind in {functions.READ, functions.COLLAPSE}:
                key_outputs = [
                    f"{selectors.FEATURE_PREFIX}{key.id}"
                    for key in self._entity_dimensions
                    if f"{selectors.FEATURE_PREFIX}{key.id}" not in action_model.features.outputs
                ]
                action_model.features.outputs[:0] = key_outputs
            actions_by_id[name] = action_model
        return actions_by_id

    @property
    def _feature_metadata(self) -> dict[str, spec_model.Feature]:
        """Collect output metadata and entity dimensions, rejecting duplicate producers."""
        features: dict[str, spec_model.Feature] = {}
        producers: dict[str, str] = {}
        dimensions = self._entity_dimensions
        for name, declaration in self.actions.items():
            for metadata in declaration.outputs:
                identifier = metadata.id
                if identifier in producers:
                    raise ValueError(
                        f"Dataset '{self.id}' feature '{identifier}' has duplicate producers: "
                        f"'{producers[identifier]}' and '{name}'"
                    )
                producers[identifier] = name
                features[identifier] = metadata.to_model()
            if declaration.kind in {functions.READ, functions.COLLAPSE}:
                for key in dimensions:
                    if key.id not in features:
                        features[key.id] = spec_model.Feature(
                            id=key.id,
                            name=spec_common.humanize_identifier(key.id),
                            type=key.type,
                            description=key.description,
                        )
        return features

    def _action_model(self, name: str, declaration: actions.Action) -> spec_model.Action:
        """Convert an action and add its dataset location to declaration errors."""
        try:
            return declaration.to_model()
        except TypeError as error:
            raise TypeError(f"Dataset '{self.id}', action '{name}': {error}") from error
        except ValueError as error:
            raise ValueError(f"Dataset '{self.id}', action '{name}': {error}") from error

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Collect reusable function contracts without executing implementations."""
        catalogs: list[spec_model.FunctionCatalog] = []
        for name, declaration in self.actions.items():
            self._action_model(name, declaration)
            catalogs.append(declaration.function_catalog())
        return spec_model.FunctionCatalog(root=function_catalog.merge_function_catalogs(catalogs))


class DatasetRegistry:
    """Register dataset classes and instantiate their declarations without execution."""

    def __init__(self, datasets: abc.Sequence[type[Dataset]]) -> None:
        self.datasets: dict[str, Dataset] = {}
        for declaration in datasets:
            instance = declaration()
            if instance.id in self.datasets:
                raise ValueError(f"Duplicate dataset ID: {instance.id}")
            self.datasets[instance.id] = instance

    def to_declarations(self) -> dict[str, Dataset]:
        """Return registered dataset declarations in composition order."""
        return self.datasets.copy()


def to_models(
    declarations: abc.Iterable[Dataset | spec_model.Dataset],
) -> dict[str, spec_model.Dataset]:
    """Convert datasets to an ID-keyed registry without overwriting duplicates."""
    models: dict[str, spec_model.Dataset] = {}
    for declaration in declarations:
        if isinstance(declaration, Dataset):
            model = declaration.to_model()
        elif isinstance(declaration, spec_model.Dataset):
            model = declaration
        else:
            raise TypeError("datasets must contain Dataset declarations or canonical models")
        if model.id in models:
            raise ValueError(f"Duplicate dataset id {model.id}")
        models[model.id] = model
    return models
