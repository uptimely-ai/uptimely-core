"""The spec document and its cached declaration views."""

from __future__ import annotations

import functools
import logging
import typing

import pydantic

from uptimely.spec import arg_types, selectors
from uptimely.spec import function_kinds as functions

from . import base, binding_argument, merge
from . import dimension as dimension_module
from . import functions as functions_module
from . import profile as profile_module

logger = logging.getLogger(__name__)

SPEC_VERSION = 7
type ProfileKey = str
type OperatorKey = tuple[ProfileKey, str]
type SpecPath = tuple[str | int, ...]
type DataFrameArgument = tuple[str, object, str | None]


class SpecSource(base.StrictModel):
    """Describe how a spec document was authored or generated."""

    name: str
    generated: bool


class Spec(base.StrictModel):
    """The complete JSON document with cached views of its declarations."""

    name: str | None = None
    spec_version: typing.Literal[7] = SPEC_VERSION
    source: SpecSource = pydantic.Field(
        default_factory=lambda: SpecSource(name="manual", generated=False)
    )
    dimensions: dict[str, dimension_module.Dimension] = pydantic.Field(default_factory=dict)
    functions: functions_module.FunctionCatalog = pydantic.Field(
        default_factory=functions_module.FunctionCatalog
    )
    profiles: dict[str, profile_module.Profile] = pydantic.Field(default_factory=dict)

    def model_post_init(self, context: typing.Any, /) -> None:
        """Run Spec post-initialization hooks."""
        merge.bind_default_merges(self)

    def rebuild(self) -> typing.Self:
        """Return a fresh Spec after declarations have been edited.

        Cached views on this instance are not invalidated when nested declarations
        change. Rebuild before validating or compiling an edited document.
        """
        return type(self).model_validate(self.model_dump())

    @functools.cached_property
    def profile_items(self) -> list[tuple[ProfileKey, profile_module.Profile]]:
        """Return profiles with their global IDs in declaration order."""
        return list(self.profiles.items())

    @functools.cached_property
    def profiles_by_key(self) -> dict[ProfileKey, profile_module.Profile]:
        """Return profiles keyed by their globally unique IDs."""
        return dict(self.profile_items)

    @functools.cached_property
    def profile_keys(self) -> dict[str, ProfileKey]:
        """Return each global profile ID's declaration key."""
        return {profile.id: key for key, profile in self.profile_items}

    @functools.cached_property
    def features(self) -> dict[str, profile_module.Feature]:
        """Return original feature metadata keyed by ID, including dimensions."""
        return {
            feature_id: feature
            for _, profile in self.profile_items
            for feature_id, feature in profile.features.items()
        }

    @functools.cached_property
    def operators(self) -> list[profile_module.Operator]:
        """Return original Operator objects in declaration order, retaining aliases."""
        return [operator for _, operator in self.operator_items]

    @functools.cached_property
    def operator_items(self) -> list[tuple[OperatorKey, profile_module.Operator]]:
        """Return operator occurrences with profile and dictionary keys."""
        return [
            ((profile_key, operator_id), operator)
            for profile_key, profile in self.profile_items
            for operator_id, operator in profile.assembly.items()
        ]

    @functools.cached_property
    def operators_by_key(self) -> dict[OperatorKey, profile_module.Operator]:
        """Return original Operators keyed by their declaration locations."""
        return dict(self.operator_items)

    @functools.cached_property
    def operator_profile_keys(self) -> dict[OperatorKey, ProfileKey]:
        """Return each operator's owning profile ID."""
        return {key: key[0] for key, _ in self.operator_items}

    @functools.cached_property
    def operator_profiles(self) -> dict[OperatorKey, profile_module.Profile]:
        """Return each operator's owning profile."""
        return {key: self.profiles_by_key[key[0]] for key, _ in self.operator_items}

    def _row_context_profile_key(self, key: OperatorKey) -> ProfileKey | None:
        """Resolve the profile whose observations an operator's context describes."""
        operator = self.operators_by_key[key]
        function = self.functions[operator.compute.function]
        definition = functions.FUNCTION_KINDS[function.kind]
        return (
            self.input_sources[key]
            if definition.dimension_change == "remove"
            else self.operator_profile_keys[key]
        )

    def get_row_context_profile(self, key: OperatorKey) -> profile_module.Profile | None:
        """Return the context profile, or None when its source is unresolved."""
        source = self._row_context_profile_key(key)
        return self.profiles_by_key[source] if source is not None else None

    def get_row_context_dimensions(self, key: OperatorKey) -> frozenset[str] | None:
        """Return context profile dimension IDs, or None for an unresolved source."""
        source = self._row_context_profile_key(key)
        return self.dimensions_by_profile[source] if source is not None else None

    def get_row_context_resolution(
        self, key: OperatorKey, dimension_id: str
    ) -> dimension_module.Resolution | None:
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
    def arguments(self) -> dict[tuple[str, str], functions_module.Argument]:
        """Return function argument declarations keyed by function and argument."""
        return self.functions.arguments

    @property
    def entrypoints(self) -> list[str]:
        """Return distinct catalog entrypoint strings in declaration order."""
        return list(dict.fromkeys(function.entrypoint for function in self.functions.root.values()))

    @functools.cached_property
    def feature_owners(self) -> dict[str, list[ProfileKey]]:
        """Return all occurrence keys owning each non-dimension feature."""
        owners: dict[str, list[ProfileKey]] = {}
        grain_keys = self.grain_key_ids
        for profile_key, profile in self.profile_items:
            for feature_id in profile.features:
                if feature_id not in grain_keys:
                    owners.setdefault(feature_id, []).append(profile_key)
        return owners

    @functools.cached_property
    def operators_by_function(self) -> dict[str, list[OperatorKey]]:
        """Return operator occurrence keys grouped by function ID."""
        grouped: dict[str, list[OperatorKey]] = {}
        for key, operator in self.operator_items:
            for operator_binding in operator.bindings.values():
                grouped.setdefault(operator_binding.function, []).append(key)
        return grouped

    @functools.cached_property
    def feature_producers(self) -> dict[str, list[OperatorKey]]:
        """Return all operator occurrence keys declaring each output feature."""
        producers: dict[str, list[OperatorKey]] = {}
        for key, operator in self.operator_items:
            for feature_id in operator.output_features:
                producers.setdefault(feature_id, []).append(key)
        return producers

    @functools.cached_property
    def dimensions_by_profile(self) -> dict[ProfileKey, frozenset[str]]:
        """Return each profile's dimension IDs."""
        return {
            profile_key: frozenset(reference.dimension for reference in profile.grain)
            for profile_key, profile in self.profile_items
        }

    @functools.cached_property
    def grain_keys_by_profile(self) -> dict[ProfileKey, list[str]]:
        """Return dataframe key column names in profile grain order."""
        return {
            profile_key: [
                dimension.resolutions[reference.resolution].key
                for reference in profile.grain
                if (dimension := self.dimensions.get(reference.dimension)) is not None
                and reference.resolution in dimension.resolutions
            ]
            for profile_key, profile in self.profile_items
        }

    @functools.cached_property
    def grain_key_types_by_profile(self) -> dict[ProfileKey, dict[str, str]]:
        """Return logical types for dataframe key columns in each profile."""
        return {
            profile_key: {
                dimension.resolutions[reference.resolution].key: dimension.resolutions[
                    reference.resolution
                ].type
                for reference in profile.grain
                if (dimension := self.dimensions.get(reference.dimension)) is not None
                and reference.resolution in dimension.resolutions
            }
            for profile_key, profile in self.profile_items
        }

    @functools.cached_property
    def identifier_types_by_profile(self) -> dict[ProfileKey, dict[str, str]]:
        """Return all resolution key types for the dimensions used by each profile."""
        return {
            profile_key: profile.key_types(self.dimensions)
            for profile_key, profile in self.profile_items
        }

    @functools.cached_property
    def grain_key_ids(self) -> frozenset[str]:
        """Return all dataframe key column names selected by profile grains."""
        return frozenset(
            key_id for key_ids in self.grain_keys_by_profile.values() for key_id in key_ids
        )

    @functools.cached_property
    def operator_paths(self) -> dict[OperatorKey, SpecPath]:
        """Return model-ID paths used by operator contracts."""
        return {
            key: ("profiles", self.profiles_by_key[key[0]].id, "assembly", key[1])
            for key, _ in self.operator_items
        }

    @functools.cached_property
    def declaration_paths(self) -> dict[OperatorKey, SpecPath]:
        """Return dictionary-key paths used by binding validation."""
        return {
            key: ("profiles", self.profiles_by_key[key[0]].id, "assembly", key[1])
            for key, _ in self.operator_items
        }

    @functools.cached_property
    def local_features(self) -> dict[ProfileKey, frozenset[str]]:
        """Return feature IDs available in each profile, including grain keys."""
        return {
            key: frozenset(profile.features) | frozenset(self.grain_keys_by_profile[key])
            for key, profile in self.profile_items
        }

    @functools.cached_property
    def input_candidates(self) -> dict[OperatorKey, tuple[tuple[str, list[ProfileKey]], ...]]:
        """Return ordered input feature owners, preserving unresolved and ambiguous inputs."""
        return {
            key: tuple(
                (feature, self.feature_owners.get(feature, []))
                for feature in operator.input_features
                if feature != selectors.CURRENT_ID and feature not in self.grain_key_ids
            )
            for key, operator in self.operator_items
        }

    @functools.cached_property
    def input_sources(self) -> dict[OperatorKey, ProfileKey | None]:
        """Return the unique source occurrence for each operator, or None when unresolved."""
        result: dict[OperatorKey, ProfileKey | None] = {}
        for key, candidates in self.input_candidates.items():
            sources = {owners[0]: owners[0] for _, owners in candidates if len(owners) == 1}
            result[key] = (
                next(iter(sources.values()))
                if len(sources) == 1 and all(len(owners) == 1 for _, owners in candidates)
                else None
            )
        return result

    @functools.cached_property
    def operator_dataframe_arguments(self) -> dict[OperatorKey, tuple[DataFrameArgument, ...]]:
        """Return supplied dataframe arguments and their referenced profile IDs."""
        result: dict[OperatorKey, tuple[DataFrameArgument, ...]] = {}
        for key, operator in self.operator_items:
            function = self.functions.root.get(operator.compute.function)
            arguments: list[DataFrameArgument] = []
            if function is not None:
                for name in function.arguments_by_type.get(arg_types.DATAFRAME, {}):
                    argument = operator.arguments.get(name)
                    arguments.append(
                        (
                            name,
                            argument.root if argument is not None else None,
                            argument.profile_id(key[0]) if argument is not None else None,
                        )
                    )
            result[key] = tuple(arguments)
        return result

    @functools.cached_property
    def dataframe_argument_profiles(self) -> dict[OperatorKey, tuple[ProfileKey, ...]]:
        """Return resolved profile keys for dataframe arguments in argument order."""
        return {
            key: tuple(
                self.profile_keys[source_id]
                for _, _, source_id in arguments
                if source_id is not None and source_id in self.profile_keys
            )
            for key, arguments in self.operator_dataframe_arguments.items()
        }

    @functools.cached_property
    def dataframe_argument_profile_ids(self) -> dict[OperatorKey, frozenset[str]]:
        """Return distinct resolved profile IDs for each operator's dataframe arguments."""
        return {
            key: frozenset(sources) for key, sources in self.dataframe_argument_profiles.items()
        }

    @functools.cached_property
    def dataframe_argument_grain_keys(self) -> dict[OperatorKey, frozenset[str]]:
        """Return dataframe keys available from each operator's referenced profiles."""
        return {
            key: frozenset().union(*(self.grain_keys_by_profile[source] for source in sources))
            for key, sources in self.dataframe_argument_profiles.items()
        }

    @functools.cached_property
    def binding_selectors_with_paths(self) -> tuple[tuple[SpecPath, object, str], ...]:
        """Return binding leaves and argument types with their binding argument paths."""
        return tuple(
            (path, argument.root, argument_type)
            for path, argument, argument_type in self.binding_arguments_with_paths
        )

    @functools.cached_property
    def binding_arguments_with_paths(
        self,
    ) -> tuple[tuple[SpecPath, binding_argument.BindingArgument, str], ...]:
        """Return typed bound leaves with their binding-collection diagnostic paths."""
        arguments: list[tuple[SpecPath, binding_argument.BindingArgument, str]] = []
        for key, operator in self.operator_items:
            for name, operator_binding in operator.bindings.items():
                function = self.functions.root.get(operator_binding.function)
                if function is not None:
                    path = (*self.declaration_paths[key], name, "args")
                    arguments.extend(
                        (path, argument, argument_type)
                        for argument, argument_type in operator_binding.typed_arguments(function)
                    )
        return tuple(arguments)

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
    def matching_profile_keys(self) -> dict[OperatorKey, tuple[tuple[str, SpecPath], ...]]:
        """Return selected matching profile keys and their declaration paths."""
        result: dict[OperatorKey, tuple[tuple[str, SpecPath], ...]] = {}
        for key, operator in self.operator_items:
            matches: list[tuple[str, SpecPath]] = []
            for reference, path in operator.compute.grain_references_with_paths:
                profile_id = reference.profile_id(key[0])
                profile_key = self.profile_keys.get(profile_id) if profile_id is not None else None
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
        profile_count = 0
        operator_count = 0
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
            profile_count += 1
            operator_count += len(assembly)
        logger.debug("Check object keys as identifiers for %d profiles", profile_count)
        logger.debug("Check spec version is an integer")
        logger.debug("Check feature references for %d operators", operator_count)

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
