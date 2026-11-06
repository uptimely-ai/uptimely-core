"""The spec document and its cached resource indexes."""

from __future__ import annotations

import dataclasses
import functools
import logging
import typing

import pydantic

from uptimely.spec import arg_types, functions, selectors

from . import common
from . import functions as functions_module
from . import profile as profile_module

logger = logging.getLogger(__name__)

SPEC_VERSION = 5
type ProfileKey = str
type ActionKey = tuple[ProfileKey, str]
type SpecPath = tuple[str | int, ...]
type DatasetArgument = tuple[str, object, str | None]


@dataclasses.dataclass
class _ResourceIndex:
    profile_items: list[tuple[ProfileKey, profile_module.Profile]] = dataclasses.field(
        default_factory=list
    )
    action_items: list[tuple[ActionKey, profile_module.Operator]] = dataclasses.field(
        default_factory=list
    )
    profiles: dict[str, profile_module.Profile] = dataclasses.field(default_factory=dict)
    profiles_by_key: dict[ProfileKey, profile_module.Profile] = dataclasses.field(
        default_factory=dict
    )
    profile_keys: dict[str, ProfileKey] = dataclasses.field(default_factory=dict)
    features: dict[str, profile_module.Feature] = dataclasses.field(default_factory=dict)
    actions: list[profile_module.Operator] = dataclasses.field(default_factory=list)
    actions_by_key: dict[ActionKey, profile_module.Operator] = dataclasses.field(
        default_factory=dict
    )
    action_profile_keys: dict[ActionKey, ProfileKey] = dataclasses.field(default_factory=dict)
    action_profiles: dict[ActionKey, profile_module.Profile] = dataclasses.field(
        default_factory=dict
    )
    feature_owners: dict[str, list[ProfileKey]] = dataclasses.field(default_factory=dict)
    actions_by_function: dict[str, list[ActionKey]] = dataclasses.field(default_factory=dict)
    feature_producers: dict[str, list[ActionKey]] = dataclasses.field(default_factory=dict)
    dimensions: dict[ProfileKey, frozenset[str]] = dataclasses.field(default_factory=dict)
    grain_keys: dict[ProfileKey, list[str]] = dataclasses.field(default_factory=dict)
    grain_key_types: dict[ProfileKey, dict[str, str]] = dataclasses.field(default_factory=dict)
    action_paths: dict[ActionKey, SpecPath] = dataclasses.field(default_factory=dict)
    declaration_paths: dict[ActionKey, SpecPath] = dataclasses.field(default_factory=dict)


class Spec(common.StrictModel):
    """The complete JSON document; cached views assume declarations are unchanged."""

    name: str | None = None
    spec_version: typing.Literal[5] = SPEC_VERSION
    source: common.SpecSource = pydantic.Field(
        default_factory=lambda: common.SpecSource(name="manual", generated=False)
    )
    dimensions: dict[str, common.Dimension] = pydantic.Field(default_factory=dict)
    functions: functions_module.FunctionCatalog = pydantic.Field(
        default_factory=functions_module.FunctionCatalog
    )
    profiles: dict[str, profile_module.Profile] = pydantic.Field(default_factory=dict)

    @functools.cached_property
    def _indexes(self) -> _ResourceIndex:
        indexes = _ResourceIndex()
        profile_items = list(self.profiles.items())
        all_grain_keys: set[str] = set()
        for profile_id, profile in profile_items:
            dimension_ids: set[str] = set()
            keys: list[str] = []
            key_types: dict[str, str] = {}
            for reference in profile.grain:
                dimension_ids.add(reference.dimension)
                dimension = self.dimensions.get(reference.dimension)
                resolution = (
                    dimension.resolutions.get(reference.resolution)
                    if dimension is not None
                    else None
                )
                if resolution is not None:
                    keys.append(resolution.key)
                    key_types[resolution.key] = resolution.type
                    all_grain_keys.add(resolution.key)
            indexes.dimensions[profile_id] = frozenset(dimension_ids)
            indexes.grain_keys[profile_id] = keys
            indexes.grain_key_types[profile_id] = key_types

        for profile_id, profile in profile_items:
            indexes.profile_items.append((profile_id, profile))
            indexes.profiles[profile.id] = profile
            indexes.profiles_by_key[profile_id] = profile
            indexes.profile_keys[profile.id] = profile_id
            for feature_id, feature in profile.features.items():
                indexes.features[feature_id] = feature
                if feature_id not in all_grain_keys:
                    indexes.feature_owners.setdefault(feature_id, []).append(profile_id)
            for action_id, action in profile.assembly.items():
                key = (profile_id, action_id)
                indexes.action_items.append((key, action))
                indexes.actions.append(action)
                indexes.actions_by_key[key] = action
                indexes.action_profile_keys[key] = profile_id
                indexes.action_profiles[key] = profile
                base = ("profiles", profile.id, "assembly")
                indexes.action_paths[key] = (*base, action_id)
                indexes.declaration_paths[key] = (*base, action_id)
                indexes.actions_by_function.setdefault(action.compute.function, []).append(key)
                for feature_id in action.output_features:
                    indexes.feature_producers.setdefault(feature_id, []).append(key)
        return indexes

    @property
    def profile_items(self) -> list[tuple[ProfileKey, profile_module.Profile]]:
        """Return profiles with their global IDs in declaration order."""
        return self._indexes.profile_items

    @property
    def profiles_by_key(self) -> dict[ProfileKey, profile_module.Profile]:
        """Return profiles keyed by their globally unique IDs."""
        return self._indexes.profiles_by_key

    @property
    def profile_keys(self) -> dict[str, ProfileKey]:
        """Return each global profile ID's index key."""
        return self._indexes.profile_keys

    @property
    def profiles_by_id(self) -> dict[str, profile_module.Profile]:
        """Return original profile objects keyed by globally unique ID."""
        return self._indexes.profiles

    @property
    def features(self) -> dict[str, profile_module.Feature]:
        """Return original feature metadata keyed by ID, including dimensions."""
        return self._indexes.features

    @property
    def actions(self) -> list[profile_module.Operator]:
        """Return original Operator objects in declaration order, retaining aliases."""
        return self._indexes.actions

    @property
    def action_items(self) -> list[tuple[ActionKey, profile_module.Operator]]:
        """Return action occurrences with profile and dictionary keys."""
        return self._indexes.action_items

    @property
    def actions_by_key(self) -> dict[ActionKey, profile_module.Operator]:
        """Return original actions keyed by their declaration locations."""
        return self._indexes.actions_by_key

    @property
    def action_profile_keys(self) -> dict[ActionKey, ProfileKey]:
        """Return each action's owning profile ID."""
        return self._indexes.action_profile_keys

    @property
    def action_profiles(self) -> dict[ActionKey, profile_module.Profile]:
        """Return each action's owning profile."""
        return self._indexes.action_profiles

    def _row_context_profile_key(self, key: ActionKey) -> ProfileKey | None:
        """Resolve the profile whose observations an action's context describes."""
        action = self.actions_by_key[key]
        function = self.functions[action.compute.function]
        definition = functions.FUNCTION_KINDS[function.kind]
        return (
            self.input_sources[key]
            if definition.dimension_change == "remove"
            else self.action_profile_keys[key]
        )

    def get_row_context_profile(self, key: ActionKey) -> profile_module.Profile | None:
        """Return the context profile, or None when its source is unresolved."""
        source = self._row_context_profile_key(key)
        return self.profiles_by_key[source] if source is not None else None

    def get_row_context_dimensions(self, key: ActionKey) -> frozenset[str] | None:
        """Return context profile dimension IDs, or None for an unresolved source."""
        source = self._row_context_profile_key(key)
        return self.dimensions_by_profile[source] if source is not None else None

    def get_row_context_resolution(
        self, key: ActionKey, dimension_id: str
    ) -> common.Resolution | None:
        """Return the selected context resolution, or None when it is unavailable."""
        profile = self.get_row_context_profile(key)
        if profile is None:
            return None
        grain = next((item for item in profile.grain if item.dimension == dimension_id), None)
        if grain is None:
            return None
        dimension = self.dimensions.get(dimension_id)
        return dimension.resolutions.get(grain.resolution) if dimension is not None else None

    def grain_refines(self, coarser_profile: ProfileKey, finer_profile: ProfileKey) -> bool:
        """Return whether the finer profile selects descendants of every coarser key."""
        coarse = {
            reference.dimension: reference.resolution
            for reference in self.profiles_by_key[coarser_profile].grain
        }
        fine = {
            reference.dimension: reference.resolution
            for reference in self.profiles_by_key[finer_profile].grain
        }
        for dimension_id, coarse_resolution in coarse.items():
            finer_resolution = fine.get(dimension_id)
            if finer_resolution is None:
                return False
            dimension = self.dimensions.get(dimension_id)
            if dimension is None:
                return False
            current: str | None = finer_resolution
            while current is not None and current != coarse_resolution:
                resolution = dimension.resolutions.get(current)
                current = resolution.parent if resolution is not None else None
            if current != coarse_resolution:
                return False
        return True

    @property
    def arguments(self) -> dict[tuple[str, str], common.Argument]:
        """Return function argument declarations keyed by function and argument."""
        return self.functions.arguments

    @property
    def entrypoints(self) -> list[str]:
        """Return distinct catalog entrypoint strings in declaration order."""
        return list(dict.fromkeys(function.entrypoint for function in self.functions.root.values()))

    @property
    def feature_owners(self) -> dict[str, list[ProfileKey]]:
        """Return all occurrence keys owning each non-dimension feature."""
        return self._indexes.feature_owners

    @property
    def actions_by_function(self) -> dict[str, list[ActionKey]]:
        """Return action occurrence keys grouped by function ID."""
        return self._indexes.actions_by_function

    @property
    def feature_producers(self) -> dict[str, list[ActionKey]]:
        """Return all action occurrence keys declaring each output feature."""
        return self._indexes.feature_producers

    @property
    def dimensions_by_profile(self) -> dict[ProfileKey, frozenset[str]]:
        """Return each profile's dimension IDs."""
        return self._indexes.dimensions

    @property
    def grain_keys_by_profile(self) -> dict[ProfileKey, list[str]]:
        """Return dataframe key column names in profile grain order."""
        return self._indexes.grain_keys

    @property
    def grain_key_types_by_profile(self) -> dict[ProfileKey, dict[str, str]]:
        """Return logical types for dataframe key columns in each profile."""
        return self._indexes.grain_key_types

    @functools.cached_property
    def grain_key_ids(self) -> frozenset[str]:
        """Return all dataframe key column names selected by profile grains."""
        return frozenset(
            key_id for key_ids in self.grain_keys_by_profile.values() for key_id in key_ids
        )

    @property
    def action_paths(self) -> dict[ActionKey, SpecPath]:
        """Return model-ID paths used by action contracts."""
        return self._indexes.action_paths

    @property
    def declaration_paths(self) -> dict[ActionKey, SpecPath]:
        """Return dictionary-key paths used by binding validation."""
        return self._indexes.declaration_paths

    @functools.cached_property
    def local_features(self) -> dict[ProfileKey, frozenset[str]]:
        """Return feature IDs available in each profile, including grain keys."""
        return {
            key: frozenset(profile.features) | frozenset(self.grain_keys_by_profile[key])
            for key, profile in self.profile_items
        }

    @functools.cached_property
    def input_candidates(self) -> dict[ActionKey, tuple[tuple[str, list[ProfileKey]], ...]]:
        """Return ordered input feature owners, preserving unresolved and ambiguous inputs."""
        return {
            key: tuple(
                (feature, self.feature_owners.get(feature, []))
                for feature in action.input_features
                if feature != selectors.CURRENT_ID and feature not in self.grain_key_ids
            )
            for key, action in self.action_items
        }

    @functools.cached_property
    def input_sources(self) -> dict[ActionKey, ProfileKey | None]:
        """Return the unique source occurrence for each action, or None when unresolved."""
        result: dict[ActionKey, ProfileKey | None] = {}
        for key, candidates in self.input_candidates.items():
            sources = {owners[0]: owners[0] for _, owners in candidates if len(owners) == 1}
            result[key] = (
                next(iter(sources.values()))
                if len(sources) == 1 and all(len(owners) == 1 for _, owners in candidates)
                else None
            )
        return result

    @functools.cached_property
    def actions_arguments(self) -> dict[ActionKey, tuple[DatasetArgument, ...]]:
        """Return supplied dataset arguments and normalized dataset IDs per action."""
        result: dict[ActionKey, tuple[DatasetArgument, ...]] = {}
        for key, action in self.action_items:
            function = self.functions.root.get(action.compute.function)
            arguments: list[DatasetArgument] = []
            if function is not None:
                for name in function.arguments_by_type.get(arg_types.DATAFRAME, {}):
                    value = action.arguments.get(name)
                    source_id = None
                    if isinstance(value, str) and value.startswith(selectors.PROFILE_PREFIX):
                        reference = value.removeprefix(selectors.PROFILE_PREFIX).removesuffix(
                            selectors.DATAFRAME_SELECTOR
                        )
                        source_id = key[0] if reference == selectors.CURRENT_ID else reference
                    arguments.append((name, value, source_id))
            result[key] = tuple(arguments)
        return result

    @functools.cached_property
    def dataset_argument_sources(self) -> dict[ActionKey, tuple[ProfileKey, ...]]:
        """Return resolved profile IDs for dataset arguments in argument order."""
        return {
            key: tuple(
                self.profile_keys[source_id]
                for _, _, source_id in arguments
                if source_id is not None and source_id in self.profile_keys
            )
            for key, arguments in self.actions_arguments.items()
        }

    @functools.cached_property
    def dataset_argument_ids(self) -> dict[ActionKey, frozenset[str]]:
        """Return distinct resolved dataset argument IDs per action."""
        return {key: frozenset(sources) for key, sources in self.dataset_argument_sources.items()}

    @functools.cached_property
    def dataset_argument_grain_keys(self) -> dict[ActionKey, frozenset[str]]:
        """Return dataframe keys available across each action's dataset arguments."""
        return {
            key: frozenset().union(*(self.grain_keys_by_profile[source] for source in sources))
            for key, sources in self.dataset_argument_sources.items()
        }

    @functools.cached_property
    def binding_selectors(self) -> dict[ActionKey, tuple[tuple[object, str], ...]]:
        """Return supplied binding leaves with their inherited argument types."""
        result: dict[ActionKey, tuple[tuple[object, str], ...]] = {}
        for key, action in self.action_items:
            values: list[tuple[object, str]] = []
            function = self.functions.root.get(action.compute.function)
            if function is not None:
                for value, path in action.compute.values_with_paths:
                    argument = function.args.get(path[0]) if isinstance(path[0], str) else None
                    if argument is None:
                        continue
                    argument_type = argument.type
                    for segment in path[1:]:
                        item_type = (
                            arg_types.array_item_type(argument_type)
                            if isinstance(segment, int)
                            else arg_types.object_value_type(argument_type)
                        )
                        argument_type = item_type or arg_types.STRING
                    values.append((value, argument_type))
            result[key] = tuple(values)
        return result

    @functools.cached_property
    def binding_selectors_with_paths(self) -> tuple[tuple[SpecPath, object, str], ...]:
        """Return binding leaves and argument types with their binding argument paths."""
        return tuple(
            ((*self.declaration_paths[key], "compute", "args"), value, argument_type)
            for key, values in self.binding_selectors.items()
            for value, argument_type in values
        )

    @functools.cached_property
    def binding_resources(self) -> dict[str, dict[str, pydantic.BaseModel]]:
        """Return declaration metadata available to structural binding selectors."""
        return {
            selectors.PROFILE_PREFIX: dict(self.profiles),
            selectors.DIMENSION_PREFIX: dict(self.dimensions),
            selectors.FEATURE_PREFIX: {
                feature_id: feature
                for profile in self.profiles.values()
                for feature_id, feature in profile.features.items()
            },
        }

    @functools.cached_property
    def matching_profile_keys(self) -> dict[ActionKey, tuple[tuple[str, SpecPath], ...]]:
        """Return selected matching profile keys and their declaration paths."""
        result: dict[ActionKey, tuple[tuple[str, SpecPath], ...]] = {}
        for key, action in self.action_items:
            matches: list[tuple[str, SpecPath]] = []
            for value, path in action.compute.values_with_paths:
                if not (
                    isinstance(value, str)
                    and value.startswith(selectors.PROFILE_PREFIX)
                    and value.endswith(selectors.PROFILE_GRAIN_IDS_SELECTOR)
                ):
                    continue
                profile_id = value.removeprefix(selectors.PROFILE_PREFIX).removesuffix(
                    selectors.PROFILE_GRAIN_IDS_SELECTOR
                )
                if profile_id == selectors.CURRENT_ID:
                    profile_key = self.action_profile_keys[key]
                else:
                    profile_key = self.profile_keys.get(profile_id)
                if profile_key is None:
                    continue
                matches.extend(
                    (grain_key, (*self.declaration_paths[key], "compute", "args", *path))
                    for grain_key in self.grain_keys_by_profile[profile_key]
                )
            result[key] = tuple(matches)
        return result

    @pydantic.field_validator("spec_version", mode="before")
    @classmethod
    def validate_spec_version_type(cls, value: object) -> object:
        """Reject booleans, which Python otherwise treats as integer literals."""
        if type(value) is not int:
            raise ValueError("spec_version must be an integer")
        return value

    @pydantic.model_validator(mode="before")
    @classmethod
    def normalize_document(cls, value: typing.Any, info: pydantic.ValidationInfo) -> typing.Any:
        """Recover keyed resource IDs and resolve profile dimension references."""
        log_structure = not isinstance(info.context, dict) or info.context.get(
            "log_structure", True
        )
        if log_structure:
            logger.debug("\nSpec validation:\n  Document structure:")
        if not isinstance(value, dict):
            return value

        if log_structure and logger.isEnabledFor(logging.DEBUG):
            cls._log_structure_checks(value)
        normalized = dict(value)
        normalized["dimensions"] = cls._normalize_dimensions(cls.get_dimensions(normalized))
        if "functions" in normalized:
            normalized["functions"] = cls._normalize_functions(cls.get_functions(normalized))
        if "profiles" in normalized:
            normalized["profiles"] = cls._normalize_profiles(cls.get_profiles(normalized))
        return normalized

    @classmethod
    def get_dimensions(cls, document: dict[str, typing.Any]) -> typing.Any:
        """Return raw dimension declarations from a document."""
        return document.get("dimensions", {}) or {}

    @classmethod
    def get_functions(cls, document: dict[str, typing.Any]) -> typing.Any:
        """Return raw function declarations from a document."""
        return document.get("functions") or {}

    @classmethod
    def get_profiles(cls, document: dict[str, typing.Any]) -> typing.Any:
        """Return raw profile declarations from a document."""
        return document.get("profiles", {})

    @classmethod
    def _log_structure_checks(cls, document: dict[str, typing.Any]) -> None:
        """Summarize structural checks once instead of logging each nested resource."""
        dataset_count = 0
        action_count = 0
        profiles = cls.get_profiles(document)
        for profile in profiles.values() if isinstance(profiles, dict) else ():
            assembly = (
                profile.get("assembly", {})
                if isinstance(profile, dict)
                else profile.assembly
                if isinstance(profile, profile_module.Profile)
                else {}
            )
            if not isinstance(assembly, dict):
                continue
            dataset_count += 1
            action_count += len(assembly)
        logger.debug("    - checking object keys as identifiers for %d profiles", dataset_count)
        logger.debug("    - checking spec version is an integer")
        logger.debug("    - checking feature references for %d actions", action_count)

    @classmethod
    def _normalize_functions(cls, value: typing.Any) -> typing.Any:
        """Recover function and argument IDs from their object keys."""
        functions = cls._with_resource_ids(value)
        if isinstance(functions, dict):
            for function in functions.values():
                if isinstance(function, dict):
                    function["args"] = cls._with_resource_ids(function.get("args", {}) or {})
        return functions

    @classmethod
    def _normalize_dimensions(cls, value: typing.Any) -> typing.Any:
        """Recover dimension and resolution IDs from their object keys."""
        dimensions = cls._with_resource_ids(value)
        if isinstance(dimensions, dict):
            for dimension in dimensions.values():
                if isinstance(dimension, dict):
                    dimension["resolutions"] = cls._with_resource_ids(
                        dimension.get("resolutions", {}) or {}
                    )
        return dimensions

    @classmethod
    def _normalize_profiles(cls, value: typing.Any) -> typing.Any:
        """Recover profile IDs and normalize their features and assembly."""
        if isinstance(value, dict):
            for profile_id, profile in value.items():
                if isinstance(profile, dict) and "id" in profile:
                    raise ValueError(
                        f"Profile {profile_id} must use its object key as identifier, "
                        "not an 'id' attribute"
                    )
        profiles = cls._with_resource_ids(value)
        if isinstance(profiles, dict):
            for profile in profiles.values():
                if not isinstance(profile, dict):
                    continue
                profile["features"] = cls._with_resource_ids(profile.get("features", {}) or {})
                profile["assembly"] = cls._normalize_assembly(profile.get("assembly", {}) or {})
        return profiles

    @classmethod
    def _normalize_assembly(cls, value: typing.Any) -> typing.Any:
        """Infer operator IDs from assembly keys and reject explicit ID attributes."""
        if not isinstance(value, dict):
            return value
        for operator_id, operator in value.items():
            if isinstance(operator, dict) and "id" in operator:
                raise ValueError(
                    f"Operator {operator_id} must use its object key as identifier, "
                    "not an 'id' attribute"
                )
        return cls._with_resource_ids(value)

    @staticmethod
    def _with_resource_ids(value: typing.Any) -> typing.Any:
        """Add object keys as IDs before Pydantic validates keyed resources."""
        if not isinstance(value, dict):
            return value
        return {
            key: dict(item) | {"id": key} if isinstance(item, dict) else item
            for key, item in value.items()
        }
