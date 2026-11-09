"""Python-friendly profile declaration."""

from __future__ import annotations

import dataclasses
import typing
from collections import abc

from uptimely.spec import function_kinds as functions
from uptimely.spec import model as spec_model
from uptimely.spec import selectors
from uptimely.spec.model import base as model_base

from . import assembly, references
from . import dimension as dimension_module
from . import feature as feature_module

__all__ = [
    "Profile",
    "ProfileRegistry",
    "Order",
]


@dataclasses.dataclass(frozen=True)
class Order:
    """Declare a logical profile ordering key, not a required physical sort."""

    dimension: dimension_module.Dimension
    resolution: str | dimension_module.Resolution
    direction: typing.Literal["asc", "desc"]

    @property
    def resolution_id(self) -> str:
        """Return the selected resolution ID after validating dimension membership."""
        selected = (
            self.dimension.resolution(self.resolution.id)
            if isinstance(self.resolution, dimension_module.Resolution)
            else self.dimension.resolution(self.resolution)
        )
        return selected.id

    def to_model(self) -> spec_model.Order:
        """Convert this ordering key to its document model."""
        return spec_model.Order(
            dimension=self.dimension.id,
            resolution=self.resolution_id,
            direction=self.direction,
        )


class Profile:
    """Observation profile with a declarative assembly and feature metadata.

    The assembly may be declared in a list or grouped in a mapping; mapping
    groups are flattened in insertion order. Subclasses replace inherited
    assemblies unless they explicitly include the base assembly.
    A ProfileFeatures instance may group feature declarations referenced by
    assembly outputs.
    """

    id: str
    name: str | None = None
    description: str | None = None
    category: str | None = None
    scope: str | None = None
    features: feature_module.FeatureSet | None = None
    grain: abc.Sequence[dimension_module.Resolution] = ()
    order: abc.Sequence[Order] = ()
    assembly: (
        abc.Sequence[assembly.Operator] | abc.Mapping[str, abc.Sequence[assembly.Operator]]
    ) = ()

    @property
    def dataset(self) -> references.Reference:
        """Reference this profile's dataset without materializing it."""
        return references.ProfileReference(kind="string", value=f"$profiles.{self.id}").dataset

    @property
    def keys(self) -> list[str]:
        """Return all resolution keys for the dimensions used by this profile."""
        return list(self.key_types)

    @property
    def key_types(self) -> dict[str, str]:
        """Return all resolution key types without changing the declared grain."""
        return {
            resolution.key: resolution.type
            for item in self.grain
            for resolution in self._selected_resolution(item)[0].resolutions
        }

    def __init__(
        self,
        *,
        id: str | None = None,
        assembly: (
            abc.Sequence[assembly.Operator]
            | abc.Mapping[str, abc.Sequence[assembly.Operator]]
            | None
        ) = None,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
        scope: str | None = None,
        grain: abc.Sequence[dimension_module.Resolution] | None = None,
        order: abc.Sequence[Order] | None = None,
    ) -> None:
        if id is not None:
            self.id = id
        if name is not None:
            self.name = name
        profile_id = getattr(self, "id", None)
        if profile_id is None:
            profile_name = getattr(self, "name", None)
            source_name = profile_name if profile_name is not None else type(self).__name__
            profile_id = model_base.snake_case_identifier(source_name)
            self.id = profile_id
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Profile requires a non-empty id")
        if self.name is None:
            self.name = model_base.humanize_identifier(profile_id)
        if description is not None:
            self.description = description
        if category is not None:
            if not isinstance(category, str):
                raise TypeError("Profile category must be a string or None")
            self.category = category
        if scope is not None:
            if not isinstance(scope, str):
                raise TypeError("Profile scope must be a string or None")
            self.scope = scope
        elif self.scope is not None and not isinstance(self.scope, str):
            raise TypeError("Profile scope must be a string or None")
        if grain is not None:
            if not isinstance(grain, abc.Sequence) or isinstance(grain, (str, bytes)):
                raise TypeError("Profile grain must be a sequence")
            if any(not isinstance(item, dimension_module.Resolution) for item in grain):
                raise TypeError("Profile grain must contain resolution declarations")
            self.grain = tuple(grain)
        if order is not None:
            self.order = tuple(order)
        self.assembly = self._flatten_assembly(self.assembly if assembly is None else assembly)
        _ = self._assembly_by_id

    @property
    def _assembly_by_id(self) -> dict[str, assembly.Operator]:
        """Return declared assembly items keyed by ID after validating the collection."""
        collected: dict[str, assembly.Operator] = {}
        if not isinstance(self.assembly, abc.Sequence) or isinstance(self.assembly, (str, bytes)):
            raise TypeError(f"Profile '{self.id}' assembly must be a sequence of Operators")
        for operator in self.assembly:
            if not isinstance(operator, assembly.Operator):
                raise TypeError(f"Profile '{self.id}' assembly must contain Operators")
            if (
                operator.interface.outputs
                and not functions.FUNCTION_KINDS[operator.kind].produces_features
            ):
                raise ValueError(
                    f"Profile '{self.id}', operator '{operator.id}': "
                    f"{operator.kind.capitalize()} operator cannot produce features"
                )
            if operator.id in collected:
                raise ValueError(f"Profile '{self.id}' has duplicate operator ID '{operator.id}'")
            collected[operator.id] = operator
        return collected

    def _flatten_assembly(
        self,
        provided_assembly: (
            abc.Sequence[assembly.Operator] | abc.Mapping[str, abc.Sequence[assembly.Operator]]
        ),
    ) -> list[assembly.Operator]:
        """Copy assembly declarations, flattening named groups in insertion order."""
        if isinstance(provided_assembly, abc.Mapping):
            flattened: list[assembly.Operator] = []
            for group_name, group_items in provided_assembly.items():
                if not isinstance(group_name, str) or not group_name.strip():
                    raise TypeError("Profile assembly group names must be non-empty strings")
                if not isinstance(group_items, abc.Sequence) or isinstance(
                    group_items, (str, bytes)
                ):
                    raise TypeError(
                        f"Profile '{self.id}' assembly group '{group_name}' "
                        "must be a sequence of Operators"
                    )
                if any(not isinstance(operator, assembly.Operator) for operator in group_items):
                    raise TypeError(
                        f"Profile '{self.id}' assembly group '{group_name}' must contain Operators"
                    )
                flattened.extend(group_items)
            return flattened
        if not isinstance(provided_assembly, abc.Sequence) or isinstance(
            provided_assembly, (str, bytes)
        ):
            raise TypeError(
                f"Profile '{self.id}' assembly must be a sequence or mapping of Operators"
            )
        if any(not isinstance(operator, assembly.Operator) for operator in provided_assembly):
            raise TypeError(f"Profile '{self.id}' assembly must contain Operators")
        return list(provided_assembly)

    def to_model(self) -> spec_model.Profile:
        """Build the canonical profile, rejecting duplicate feature producers."""
        grain = self._grain()
        selected_resolutions = [self._selected_resolution(item)[1] for item in self.grain]
        return spec_model.Profile(
            id=self.id,
            name=self.name,
            description=self.description,
            category=self.category,
            scope=self.scope,
            grain=grain,
            order=[key.to_model() for key in self.order],
            features=self._feature_metadata(self.grain),
            assembly=self._operator_models(selected_resolutions),
        )

    def _selected_resolution(
        self, item: dimension_module.Resolution
    ) -> tuple[dimension_module.Dimension, dimension_module.Resolution]:
        """Resolve a profile grain item to its owning dimension and declaration."""
        if not isinstance(item, dimension_module.Resolution):
            raise TypeError("Profile grain must contain resolution declarations")
        if item.dimension is None:
            raise ValueError(
                f"Profile '{self.id}' grain resolutions must be selected through "
                "Dimension.resolution()"
            )
        if item not in item.dimension.resolutions:
            raise ValueError(
                f"Dimension '{item.dimension.id}' does not declare resolution "
                f"'{item.id}' with matching metadata"
            )
        return item.dimension, item

    def _grain(self) -> list[spec_model.Grain]:
        """Convert and validate selected dimensional resolutions."""
        references: list[spec_model.Grain] = []
        dimensions: set[str] = set()
        keys: set[str] = set()
        for item in self.grain:
            dimension, resolution = self._selected_resolution(item)
            reference = spec_model.Grain(dimension=dimension.id, resolution=resolution.id)
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

    def _operator_models(
        self, resolutions: abc.Sequence[spec_model.Resolution]
    ) -> dict[str, spec_model.Operator]:
        """Convert operators and add profile-key outputs to source operators."""
        operators_by_id: dict[str, spec_model.Operator] = {}
        for operator_id, declaration in self._assembly_by_id.items():
            operator_model = self._operator_model(operator_id, declaration)
            if declaration.kind in {functions.READ, functions.COLLAPSE}:
                key_outputs = [
                    f"{selectors.FEATURE_PREFIX}{resolution.key}"
                    for resolution in resolutions
                    if f"{selectors.FEATURE_PREFIX}{resolution.key}"
                    not in operator_model.interface.outputs
                ]
                operator_model.interface.outputs[:0] = key_outputs
            operators_by_id[operator_id] = operator_model
        return operators_by_id

    def _feature_metadata(
        self, grain: abc.Sequence[dimension_module.Resolution]
    ) -> dict[str, spec_model.Feature]:
        """Collect output metadata and selected grain keys, rejecting duplicate producers."""
        features: dict[str, spec_model.Feature] = {}
        producers: dict[str, str] = {}
        for name, declaration in self._assembly_by_id.items():
            for metadata in declaration.interface.outputs:
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
                    _, resolution = self._selected_resolution(item)
                    if resolution.key not in features:
                        features[resolution.key] = spec_model.Feature(
                            id=resolution.key,
                            name=model_base.humanize_identifier(resolution.key),
                            type=resolution.type,
                            description=item.dimension.description,
                        )
        return features

    def _operator_model(self, name: str, declaration: assembly.Operator) -> spec_model.Operator:
        """Convert an operator and add its profile location to declaration errors."""
        try:
            return declaration.to_model()
        except TypeError as error:
            raise TypeError(f"Profile '{self.id}', operator '{name}': {error}") from error
        except ValueError as error:
            raise ValueError(f"Profile '{self.id}', operator '{name}': {error}") from error

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Collect reusable function contracts without executing implementations."""
        catalogs: list[spec_model.FunctionCatalog] = []
        for name, declaration in self._assembly_by_id.items():
            self._operator_model(name, declaration)
            catalogs.append(declaration.function_catalog())
        return spec_model.FunctionCatalog.merge(catalogs)


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
