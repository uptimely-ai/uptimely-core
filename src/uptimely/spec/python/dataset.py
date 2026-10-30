"""Python-friendly dataset declaration."""

from __future__ import annotations

import dataclasses
import typing
from collections import abc
from typing import TYPE_CHECKING

from uptimely.spec import catalog as function_catalog
from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model

from . import actions, ref
from . import dimension as dimension_module

if TYPE_CHECKING:
    from .entity import Entity

__all__ = [
    "Dataset",
    "Model",
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
        description: str | None = None,
        entity: str | Entity | None = None,
        row_scope: RowScope | None = None,
        order: abc.Sequence[Order] | None = None,
    ) -> None:
        if id is not None:
            self.id = id
        if not isinstance(getattr(self, "id", None), str) or not self.id.strip():
            raise ValueError("Dataset requires a non-empty id")
        if description is not None:
            self.description = description
        if entity is not None:
            self.entity = entity
        if row_scope is not None:
            self.row_scope = row_scope
        if order is not None:
            self.order = tuple(order)
        for collection, declarations in (
            ("producers", producers),
            ("publishers", publishers),
            ("pipelines", pipelines),
        ):
            supplied = declarations if declarations is not None else getattr(self, collection)
            if not isinstance(supplied, abc.Sequence) or isinstance(supplied, (str, bytes)):
                raise TypeError(f"Dataset '{self.id}' {collection} must be a sequence of Actions")
            setattr(self, collection, list(supplied))
        self._collect_actions()

    def _collect_actions(self) -> dict[str, actions.Action]:
        """Validate collection roles and collect actions without overwriting IDs."""
        collected: dict[str, actions.Action] = {}
        for collection, kinds in _ACTION_KINDS.items():
            declarations = getattr(self, collection)
            if not isinstance(declarations, abc.Sequence) or isinstance(declarations, (str, bytes)):
                raise TypeError(f"Dataset '{self.id}' {collection} must be a sequence of Actions")
            for declaration in declarations:
                if not isinstance(declaration, actions.Action):
                    raise TypeError(f"Dataset '{self.id}' {collection} must contain Actions")
                if declaration.kind not in kinds:
                    raise ValueError(
                        f"Dataset '{self.id}', action '{declaration.id}': "
                        f"kind '{declaration.kind}' is not allowed in {collection}; "
                        f"expected {', '.join(kinds)}"
                    )
                if (
                    declaration.outputs
                    and not functions.FUNCTION_KINDS[declaration.kind].produces_features
                ):
                    raise ValueError(
                        f"Dataset '{self.id}', action '{declaration.id}': "
                        f"{declaration.kind.capitalize()} action cannot produce features"
                    )
                if declaration.id in collected:
                    raise ValueError(
                        f"Dataset '{self.id}' has duplicate action ID '{declaration.id}'"
                    )
                collected[declaration.id] = declaration
        return collected

    def to_model(self) -> spec_model.Dataset:
        """Build the canonical dataset, rejecting duplicate feature producers."""
        actions: dict[str, spec_model.Action] = {}
        features: dict[str, spec_model.Feature] = {}
        producers: dict[str, str] = {}
        if isinstance(self.entity, str):
            raise ValueError("Resolve entity IDs through Spec before converting a dataset")
        entity_keys = self.entity.dimensions if self.entity is not None else ()
        resolved_entity_keys: list[dimension_module.Dimension] = []
        for key in entity_keys:
            if isinstance(key, str):
                raise ValueError("Resolve dimension IDs through Spec before converting a dataset")
            if not isinstance(key, dimension_module.Dimension):
                raise TypeError("dataset dimensions must contain Dimension declarations")
            resolved_entity_keys.append(key)
        for name, declaration in self._collect_actions().items():
            model = self._action_model(name, declaration)
            for metadata in declaration.outputs:
                identifier = metadata.name
                if identifier in producers:
                    raise ValueError(
                        f"Dataset '{self.id}' feature '{identifier}' has duplicate producers: "
                        f"'{producers[identifier]}' and '{name}'"
                    )
                producers[identifier] = name
                features[identifier] = metadata.to_model()
            if declaration.kind in {functions.READ, functions.COLLAPSE}:
                for key in resolved_entity_keys:
                    if key.id not in features:
                        features[key.id] = spec_model.Feature(
                            id=key.id, type=key.type, description=key.description
                        )
                key_outputs = [
                    f"{selectors.FEATURE_PREFIX}{key.id}"
                    for key in resolved_entity_keys
                    if f"{selectors.FEATURE_PREFIX}{key.id}" not in model.features.outputs
                ]
                model.features.outputs[:0] = key_outputs
            actions[name] = model
        return spec_model.Dataset(
            id=self.id,
            description=self.description,
            row_scope=self.row_scope.to_model(),
            order=[key.to_model() for key in self.order],
            features=features,
            actions=actions,
        )

    def _action_model(self, name: str, declaration: actions.Action) -> spec_model.Action:
        try:
            return declaration.to_model()
        except TypeError as error:
            raise TypeError(f"Dataset '{self.id}', action '{name}': {error}") from error
        except ValueError as error:
            raise ValueError(f"Dataset '{self.id}', action '{name}': {error}") from error

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Collect reusable function contracts without executing implementations."""
        catalogs: list[spec_model.FunctionCatalog] = []
        for name, declaration in self._collect_actions().items():
            self._action_model(name, declaration)
            catalogs.append(declaration.function_catalog())
        return spec_model.FunctionCatalog(root=function_catalog.merge_function_catalogs(catalogs))


class Model:
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
