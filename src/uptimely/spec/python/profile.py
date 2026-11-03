"""Python-friendly profile declaration."""

from __future__ import annotations

import dataclasses
import typing
from collections import abc

from uptimely.spec import catalog as function_catalog
from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.model import common as spec_common

from . import actions
from . import dimension as dimension_module

__all__ = [
    "Profile",
    "ProfileRegistry",
    "Grain",
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
    """Descriptive filtering and coverage metadata for a profile."""

    filtering: str = ""
    coverage: str = ""

    def to_model(self) -> spec_model.RowScope:
        """Convert this row scope definition to its document model."""
        return spec_model.RowScope(
            filtering=self.filtering,
            coverage=self.coverage,
        )


@dataclasses.dataclass(frozen=True)
class Grain:
    """Select a resolution from a declared dimension for a profile's grain."""

    dimension: dimension_module.Dimension
    resolution: str

    def to_model(self) -> spec_model.Grain:
        """Convert this selected resolution to its document reference."""
        if not isinstance(self.dimension, dimension_module.Dimension):
            raise TypeError("Profile grain entries must reference Dimension declarations")
        dimension = self.dimension.to_model()
        if self.resolution not in dimension.resolutions:
            raise ValueError(
                f"Dimension '{self.dimension.id}' does not declare resolution '{self.resolution}'"
            )
        return spec_model.Grain(dimension=self.dimension.id, resolution=self.resolution)


@dataclasses.dataclass(frozen=True)
class Order(Grain):
    """Declare a logical profile ordering key, not a required physical sort."""

    direction: typing.Literal["asc", "desc"]

    def to_model(self) -> spec_model.Order:
        """Convert this ordering key to its document model."""
        return spec_model.Order(
            dimension=self.dimension.id,
            resolution=self.resolution,
            direction=self.direction,
        )


class Profile:
    """Observation profile with declarative producers, publishers, and pipelines.

    Each collection contains Actions with IDs unique across the profile.
    Subclasses inherit collections normally; assigning a collection replaces it.
    Feature metadata belongs to each action's outputs, not a separate inventory.
    """

    id: str
    name: str | None = None
    description: str | None = None
    category: str | None = None
    grain: abc.Sequence[Grain] = ()
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
        category: str | None = None,
        grain: abc.Sequence[Grain] | None = None,
        row_scope: RowScope | None = None,
        order: abc.Sequence[Order] | None = None,
    ) -> None:
        if id is not None:
            self.id = id
        if not isinstance(getattr(self, "id", None), str) or not self.id.strip():
            raise ValueError("Profile requires a non-empty id")
        if name is not None:
            self.name = name
        elif self.name is None:
            self.name = spec_common.humanize_identifier(self.id)
        if description is not None:
            self.description = description
        if category is not None:
            if not isinstance(category, str):
                raise TypeError("Profile category must be a string or None")
            self.category = category
        if grain is not None:
            if not isinstance(grain, abc.Sequence) or isinstance(grain, (str, bytes)):
                raise TypeError("Profile grain must be a sequence")
            if any(not isinstance(item, Grain) for item in grain):
                raise TypeError("Profile grain must contain Grain declarations")
            self.grain = tuple(grain)
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
                        f"Profile '{self.id}', action '{action.id}': "
                        f"kind '{action.kind}' is not allowed in {group_name}; "
                        f"expected {', '.join(allowed_kinds)}"
                    )
                if action.outputs and not functions.FUNCTION_KINDS[action.kind].produces_features:
                    raise ValueError(
                        f"Profile '{self.id}', action '{action.id}': "
                        f"{action.kind.capitalize()} action cannot produce features"
                    )
                if action.id in collected:
                    raise ValueError(f"Profile '{self.id}' has duplicate action ID '{action.id}'")
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
            raise TypeError(f"Profile '{self.id}' {group_name} must be a sequence of Actions")
        if any(not isinstance(action, actions.Action) for action in group_actions):
            raise TypeError(f"Profile '{self.id}' {group_name} must contain Actions")
        return list(group_actions)

    def to_model(self) -> spec_model.Profile:
        """Build the canonical profile, rejecting duplicate feature producers."""
        grain = self._grain()
        selected_resolutions = [
            item.dimension.to_model().resolutions[item.resolution] for item in self.grain
        ]
        return spec_model.Profile(
            id=self.id,
            name=self.name,
            description=self.description,
            category=self.category,
            grain=grain,
            row_scope=self.row_scope.to_model(),
            order=[key.to_model() for key in self.order],
            features=self._feature_metadata(self.grain),
            actions=self._action_models(selected_resolutions),
        )

    def _grain(self) -> list[spec_model.Grain]:
        """Convert and validate selected dimensional resolutions."""
        references: list[spec_model.Grain] = []
        dimensions: set[str] = set()
        keys: set[str] = set()
        for item in self.grain:
            if not isinstance(item, Grain):
                raise TypeError("Profile grain must contain Grain declarations")
            reference = item.to_model()
            resolution = item.dimension.to_model().resolutions[item.resolution]
            if reference.dimension in dimensions:
                raise ValueError(
                    f"Profile '{self.id}' selects multiple resolutions for dimension "
                    f"'{reference.dimension}'"
                )
            if resolution.key in keys:
                raise ValueError(
                    f"Profile '{self.id}' grain repeats dataframe key '{resolution.key}'"
                )
            dimensions.add(reference.dimension)
            keys.add(resolution.key)
            references.append(reference)
        return references

    def _action_models(
        self, resolutions: abc.Sequence[spec_model.Resolution]
    ) -> dict[str, spec_model.Action]:
        """Convert actions and add profile-key outputs to source actions."""
        actions_by_id: dict[str, spec_model.Action] = {}
        for name, declaration in self.actions.items():
            action_model = self._action_model(name, declaration)
            if declaration.kind in {functions.READ, functions.COLLAPSE}:
                key_outputs = [
                    f"{selectors.FEATURE_PREFIX}{resolution.key}"
                    for resolution in resolutions
                    if f"{selectors.FEATURE_PREFIX}{resolution.key}"
                    not in action_model.features.outputs
                ]
                action_model.features.outputs[:0] = key_outputs
            actions_by_id[name] = action_model
        return actions_by_id

    def _feature_metadata(self, grain: abc.Sequence[Grain]) -> dict[str, spec_model.Feature]:
        """Collect output metadata and selected grain keys, rejecting duplicate producers."""
        features: dict[str, spec_model.Feature] = {}
        producers: dict[str, str] = {}
        for name, declaration in self.actions.items():
            for metadata in declaration.outputs:
                identifier = metadata.id
                if identifier in producers:
                    raise ValueError(
                        f"Profile '{self.id}' feature '{identifier}' has duplicate producers: "
                        f"'{producers[identifier]}' and '{name}'"
                    )
                producers[identifier] = name
                features[identifier] = metadata.to_model()
            if declaration.kind in {functions.READ, functions.COLLAPSE}:
                for item in grain:
                    resolution = item.dimension.to_model().resolutions[item.resolution]
                    if resolution.key not in features:
                        features[resolution.key] = spec_model.Feature(
                            id=resolution.key,
                            name=spec_common.humanize_identifier(resolution.key),
                            type=resolution.type,
                            description=item.dimension.description,
                        )
        return features

    def _action_model(self, name: str, declaration: actions.Action) -> spec_model.Action:
        """Convert an action and add its dataset location to declaration errors."""
        try:
            return declaration.to_model()
        except TypeError as error:
            raise TypeError(f"Profile '{self.id}', action '{name}': {error}") from error
        except ValueError as error:
            raise ValueError(f"Profile '{self.id}', action '{name}': {error}") from error

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Collect reusable function contracts without executing implementations."""
        catalogs: list[spec_model.FunctionCatalog] = []
        for name, declaration in self.actions.items():
            self._action_model(name, declaration)
            catalogs.append(declaration.function_catalog())
        return spec_model.FunctionCatalog(root=function_catalog.merge_function_catalogs(catalogs))


class ProfileRegistry:
    """Register profile classes and instantiate their declarations without execution."""

    def __init__(self, profiles: abc.Sequence[type[Profile]]) -> None:
        self.profiles: dict[str, Profile] = {}
        for declaration in profiles:
            instance = declaration()
            if instance.id in self.profiles:
                raise ValueError(f"Duplicate profile ID: {instance.id}")
            self.profiles[instance.id] = instance

    def to_declarations(self) -> dict[str, Profile]:
        """Return registered profile declarations in composition order."""
        return self.profiles.copy()


def to_models(
    declarations: abc.Iterable[Profile | spec_model.Profile],
) -> dict[str, spec_model.Profile]:
    """Convert profiles to an ID-keyed registry without overwriting duplicates."""
    models: dict[str, spec_model.Profile] = {}
    for declaration in declarations:
        if isinstance(declaration, Profile):
            model = declaration.to_model()
        elif isinstance(declaration, spec_model.Profile):
            model = declaration
        else:
            raise TypeError("profiles must contain Profile declarations or canonical models")
        if model.id in models:
            raise ValueError(f"Duplicate profile id {model.id}")
        models[model.id] = model
    return models
