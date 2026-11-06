"""Bound values, structural selectors, and invocation-specific resolution."""

from __future__ import annotations

import dataclasses
import functools
import typing

import pydantic

from uptimely.spec import arg_types, selectors

from . import dimension

type ArgumentPath = tuple[str | int, ...]

METADATA_ATTRIBUTES = {
    selectors.FEATURE_PREFIX: frozenset({"id", "name", "type", "unit", "description"}),
    selectors.PROFILE_PREFIX: frozenset({"id", "name", "description", "category", "scope"}),
    selectors.DIMENSION_PREFIX: frozenset({"id", "name", "description", "key", "type", "parent"}),
}
VALUE_SELECTORS = {
    selectors.PROFILE_PREFIX: frozenset({"id", "dataframe", "grain.ids"}),
    selectors.FEATURE_PREFIX: frozenset({"id"}),
    selectors.DIMENSION_PREFIX: frozenset({"id"}),
}


class BindingArgument(pydantic.RootModel[pydantic.JsonValue]):
    """One bound JSON value, serialized without an additional object wrapper.

    Nested values retain their supplied order. Treat values and cached views as
    read-only after inspection; construct a new argument after editing.
    """

    @pydantic.model_validator(mode="before")
    @classmethod
    def normalize_models(cls, value: object) -> object:
        """Convert nested Pydantic declarations to their document values."""
        if isinstance(value, pydantic.BaseModel):
            return cls.normalize_models(value.model_dump())
        if isinstance(value, dict):
            return {key: cls.normalize_models(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls.normalize_models(item) for item in value]
        return value

    def __eq__(self, other: object) -> bool:
        """Compare bound values, excluding self-referential cached traversal views."""
        if not isinstance(other, BindingArgument):
            return NotImplemented
        return self.root == other.root

    @functools.cached_property
    def children(self) -> dict[str | int, BindingArgument]:
        """Return immediate object or array children in supplied order."""
        if isinstance(self.root, dict):
            return {key: BindingArgument(value) for key, value in self.root.items()}
        if isinstance(self.root, list):
            return {index: BindingArgument(value) for index, value in enumerate(self.root)}
        return {}

    @functools.cached_property
    def leaves_with_paths(self) -> tuple[tuple[BindingArgument, ArgumentPath], ...]:
        """Return scalar arguments and relative paths, retaining duplicates."""
        if isinstance(self.root, (dict, list)):
            return tuple(
                (leaf, (key, *path))
                for key, child in self.children.items()
                for leaf, path in child.leaves_with_paths
            )
        return ((self, ()),)

    @functools.cached_property
    def prefix(self) -> str | None:
        """Return the structural resource prefix of a scalar reference."""
        value = self.root
        if not isinstance(value, str):
            return None
        return next(
            (prefix for prefix in selectors.STRUCTURAL_PREFIXES if value.startswith(prefix)),
            None,
        )

    @functools.cached_property
    def identifier(self) -> str | None:
        """Return the reference's resource ID, retaining the current marker."""
        if self.prefix is None or not isinstance(self.root, str):
            return None
        return selectors.structural_identifier(self.root, self.prefix)

    @functools.cached_property
    def selector(self) -> str | None:
        """Return the selected resource attribute, or None for a bare reference."""
        if self.prefix is None or not isinstance(self.root, str):
            return None
        return self.root.removeprefix(self.prefix).partition(".")[2] or None

    @property
    def is_metadata_reference(self) -> bool:
        """Whether this argument selects resource metadata beyond an execution value."""
        return (
            self.prefix is not None
            and self.selector is not None
            and self.selector not in VALUE_SELECTORS[self.prefix]
        )

    @property
    def is_dataset_input(self) -> bool:
        """Whether this scalar references profile data rather than metadata."""
        return self.prefix == selectors.PROFILE_PREFIX and (
            self.selector is None or self.selector == "dataframe"
        )

    def profile_id(self, current_profile_id: str) -> str | None:
        """Return a profile reference's ID in the invocation's context."""
        if self.prefix != selectors.PROFILE_PREFIX:
            return None
        return current_profile_id if self.identifier == selectors.CURRENT_ID else self.identifier

    @functools.cached_property
    def references_with_paths(self) -> tuple[tuple[BindingArgument, ArgumentPath], ...]:
        """Return nested structural reference arguments and their relative paths."""
        return tuple(
            (leaf, path) for leaf, path in self.leaves_with_paths if leaf.prefix is not None
        )

    @functools.cached_property
    def dataset_input_references(self) -> tuple[str, ...]:
        """Return ordered profile data IDs, excluding metadata and retaining duplicates."""
        return tuple(
            leaf.identifier
            for leaf, _ in self.references_with_paths
            if leaf.is_dataset_input and leaf.identifier is not None
        )

    def dataset_dependencies(self, current_profile_id: str) -> list[str]:
        """Return unique inferred profile-data dependencies in supplied order."""
        return list(
            dict.fromkeys(
                current_profile_id if identifier == selectors.CURRENT_ID else identifier
                for identifier in self.dataset_input_references
            )
        )

    @functools.cached_property
    def feature_references(self) -> tuple[str, ...]:
        """Return feature IDs in supplied order, including metadata selectors."""
        return tuple(
            leaf.identifier
            for leaf, _ in self.references_with_paths
            if leaf.prefix == selectors.FEATURE_PREFIX and leaf.identifier is not None
        )

    @property
    def inferred_feature_inputs(self) -> tuple[str, ...]:
        """Return unique bare feature references for Python input inference.

        Metadata selectors and the current-output marker do not imply inputs.
        Explicit document interfaces remain authoritative.
        """
        return tuple(
            dict.fromkeys(
                leaf.identifier
                for leaf, _ in self.references_with_paths
                if leaf.prefix == selectors.FEATURE_PREFIX
                and leaf.selector is None
                and leaf.identifier is not None
                and leaf.identifier != selectors.CURRENT_ID
            )
        )

    def typed_values(self, argument_type: str) -> typing.Iterator[tuple[object, str]]:
        """Yield scalar values with types inherited through arrays and objects."""
        for leaf, path in self.leaves_with_paths:
            value_type = argument_type
            for segment in path:
                item_type = (
                    arg_types.array_item_type(value_type)
                    if isinstance(segment, int)
                    else arg_types.object_value_type(value_type)
                )
                value_type = item_type or arg_types.STRING
            yield leaf.root, value_type

    def resolve(self, context: BindingArgumentResolver) -> object:
        """Resolve this value recursively using invocation-specific context.

        Args:
            context: Current profile, output feature, grain keys, and resource metadata.

        Returns:
            The resolved scalar or nested container, without mutating the argument.

        Raises:
            ValueError: A selected grain, resource, resolution, or attribute is unavailable.
        """
        if isinstance(self.root, dict):
            return {key: child.resolve(context) for key, child in self.children.items()}
        if isinstance(self.root, list):
            return [child.resolve(context) for child in self.children.values()]
        if self.prefix is None:
            return self.root
        if (
            self.prefix == selectors.FEATURE_PREFIX
            and self.identifier == selectors.CURRENT_ID
            and self.selector in {None, "id"}
        ):
            return context.feature_id if context.feature_id is not None else self.root
        if self.prefix == selectors.PROFILE_PREFIX and self.selector == "grain.ids":
            profile_id = self.profile_id(context.current_profile_id)
            if (
                context.grain_keys_by_profile is None
                or profile_id is None
                or profile_id not in context.grain_keys_by_profile
            ):
                raise ValueError(f"Cannot resolve grain keys for profile {profile_id}")
            return list(context.grain_keys_by_profile[profile_id])
        if self.is_metadata_reference:
            return self._resolve_metadata(context)
        return (
            self.profile_id(context.current_profile_id)
            if self.prefix == selectors.PROFILE_PREFIX
            else self.identifier
        )

    def _resolve_metadata(self, context: BindingArgumentResolver) -> object:
        """Resolve a selected attribute on a declared resource or dimension resolution."""
        prefix = self.prefix
        attribute = self.selector
        resource_id = (
            self.profile_id(context.current_profile_id)
            if prefix == selectors.PROFILE_PREFIX
            else self.identifier
        )
        if prefix is None or resource_id is None or attribute is None:
            raise ValueError(f"Unsupported resource selector: {self.root}")
        resource = context.resources.get(prefix, {}).get(resource_id)
        if resource is None:
            raise ValueError(f"Cannot resolve resource metadata: {self.root}")
        if isinstance(resource, dimension.Dimension) and attribute.startswith("resolutions."):
            resolution_id, _, attribute = attribute.removeprefix("resolutions.").partition(".")
            resource = resource.resolutions.get(resolution_id)
            if resource is None:
                raise ValueError(f"Cannot resolve resolution: {self.root}")
            if not attribute:
                return resource.id
        if (
            attribute not in METADATA_ATTRIBUTES[prefix]
            or attribute not in type(resource).model_fields
        ):
            raise ValueError(f"Unsupported resource selector: {self.root}")
        return getattr(resource, attribute)


@dataclasses.dataclass(frozen=True)
class BindingArgumentResolver:
    """Invocation context and compatibility adapter for resolving argument mappings.

    Resolution behavior belongs to BindingArgument; this object only supplies
    context shared by the arguments of an invocation.
    """

    current_profile_id: str
    feature_id: str | None
    grain_keys_by_profile: typing.Mapping[str, typing.Sequence[str]] | None
    resources: typing.Mapping[str, typing.Mapping[str, pydantic.BaseModel]] = dataclasses.field(
        default_factory=dict
    )

    def resolve_arguments(self, arguments: typing.Mapping[str, object]) -> dict[str, object]:
        """Resolve raw or modeled arguments with this invocation's context."""
        return {
            name: BindingArgument.model_validate(value).resolve(self)
            for name, value in arguments.items()
        }
