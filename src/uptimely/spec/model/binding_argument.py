"""Bound values, structural selectors, and invocation-specific resolution."""

from __future__ import annotations

import functools
import typing

import pydantic

from uptimely.spec import arg_types, selectors
from uptimely.spec import row_context as row_context_values

from . import dimension

type ArgumentPath = tuple[str | int, ...]

METADATA_ATTRIBUTES = {
    selectors.FEATURE_PREFIX: frozenset({"id", "name", "type", "unit", "description"}),
    selectors.PROFILE_PREFIX: frozenset({"id", "name", "description", "category", "scope"}),
    selectors.DIMENSION_PREFIX: frozenset({"id", "name", "description", "key", "type", "parent"}),
}
VALUE_SELECTORS = {
    selectors.PROFILE_PREFIX: frozenset({"id", "dataset", "grain.ids"}),
    selectors.FEATURE_PREFIX: frozenset({"id"}),
    selectors.DIMENSION_PREFIX: frozenset({"id"}),
}
type BindingResources = typing.Mapping[str, typing.Mapping[str, pydantic.BaseModel]]


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
        return self.row_context_attribute is not None or (
            self.prefix is not None
            and self.selector is not None
            and self.selector not in VALUE_SELECTORS[self.prefix]
        )

    @functools.cached_property
    def row_context_attribute(self) -> str | None:
        """Return the selected current-operator row-context attribute, if any."""
        value = self.root
        if not isinstance(value, str) or not value.startswith(selectors.ROW_CONTEXT_PREFIX):
            return None
        return value.removeprefix(selectors.ROW_CONTEXT_PREFIX)

    @property
    def is_profile_dataframe_reference(self) -> bool:
        """Whether this scalar selects a profile dataframe rather than metadata."""
        return self.prefix == selectors.PROFILE_PREFIX and (
            self.selector is None or self.selector == "dataset"
        )

    @property
    def is_current_profile_dataframe(self) -> bool:
        """Whether this value explicitly selects the current profile dataframe."""
        return self.root == (
            f"{selectors.PROFILE_PREFIX}{selectors.CURRENT_ID}{selectors.DATASET_SELECTOR}"
        )

    @property
    def is_current_fragment(self) -> bool:
        """Whether this value selects the current operator's staged fragment."""
        return self.root == f"{selectors.OPERATOR_PREFIX}{selectors.CURRENT_ID}.fragment"

    @property
    def is_grain_reference(self) -> bool:
        """Whether this value selects a profile's grain keys."""
        return self.prefix == selectors.PROFILE_PREFIX and self.selector == "grain.ids"

    @property
    def is_current_feature_reference(self) -> bool:
        """Whether this reference uses the current output feature marker."""
        return self.prefix == selectors.FEATURE_PREFIX and self.identifier == selectors.CURRENT_ID

    @functools.cached_property
    def selector_value_type(self) -> str | None:
        """Return the required selector value type, or None for an unconstrained value."""
        value = self.root
        if not isinstance(value, str) or not value.startswith(selectors.REFERENCE_PREFIX):
            return None
        if value.startswith(selectors.OPERATOR_PREFIX):
            if self.row_context_attribute is not None:
                return None
            return arg_types.DATAFRAME
        if self.prefix == selectors.PROFILE_PREFIX:
            if value.endswith(selectors.DATASET_SELECTOR):
                return arg_types.DATAFRAME
            if value.endswith(selectors.PROFILE_GRAIN_IDS_SELECTOR):
                return arg_types.array_of(arg_types.STRING)
        if value.endswith(selectors.ID_SELECTOR) or (
            self.prefix is not None and "." in value.removeprefix(self.prefix)
        ):
            return arg_types.STRING
        return None

    def required_type(self, argument_type: str) -> str | None:
        """Return a selector's required type, preserving nullable profile-data arguments."""
        if (
            self.prefix == selectors.PROFILE_PREFIX
            and self.selector_value_type == arg_types.DATAFRAME
            and argument_type == arg_types.OPTIONAL_DATAFRAME
        ):
            return arg_types.OPTIONAL_DATAFRAME
        return self.selector_value_type

    def profile_id(self, current_profile_id: str) -> str | None:
        """Return a profile reference's ID in the invocation's context."""
        if self.prefix != selectors.PROFILE_PREFIX:
            return None
        return current_profile_id if self.identifier == selectors.CURRENT_ID else self.identifier

    @functools.cached_property
    def references_with_paths(self) -> tuple[tuple[BindingArgument, ArgumentPath], ...]:
        """Return nested structural reference arguments and their relative paths."""
        return tuple(
            (leaf, path)
            for leaf, path in self.leaves_with_paths
            if leaf.prefix is not None or leaf.row_context_attribute is not None
        )

    @functools.cached_property
    def profile_dataframe_references(self) -> tuple[str, ...]:
        """Return ordered profile IDs selected as dataframes, retaining duplicates."""
        return tuple(
            leaf.identifier
            for leaf, _ in self.references_with_paths
            if leaf.is_profile_dataframe_reference and leaf.identifier is not None
        )

    def profile_dependencies(self, current_profile_id: str) -> list[str]:
        """Return unique referenced profile IDs in supplied order."""
        return list(
            dict.fromkeys(
                current_profile_id if identifier == selectors.CURRENT_ID else identifier
                for identifier in self.profile_dataframe_references
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
        for leaf, value_type in self.typed_arguments(argument_type):
            yield leaf.root, value_type

    def typed_arguments(self, argument_type: str) -> typing.Iterator[tuple[BindingArgument, str]]:
        """Yield scalar argument objects with their inherited declared types."""
        for leaf, path in self.leaves_with_paths:
            value_type = argument_type
            for segment in path:
                item_type = (
                    arg_types.array_item_type(value_type)
                    if isinstance(segment, int)
                    else arg_types.object_value_type(value_type)
                )
                value_type = item_type or arg_types.STRING
            yield leaf, value_type

    def resolve(
        self,
        current_profile_id: str,
        feature_id: str | None = None,
        grain_keys_by_profile: typing.Mapping[str, typing.Sequence[str]] | None = None,
        resources: BindingResources | None = None,
        *,
        row_context: row_context_values.RowContext | None = None,
    ) -> object:
        """Resolve this value recursively using invocation-specific context.

        Args:
            current_profile_id: Profile containing the operator.
            feature_id: The operator's sole output feature, when unambiguous.
            grain_keys_by_profile: Profile grain keys available to selectors.
            resources: Declared profile, feature, and dimension metadata.
            row_context: Observation requirements declared by the current operator.

        Returns:
            The resolved scalar or nested container, without mutating the argument.

        Raises:
            ValueError: A selected grain, resource, resolution, or attribute is unavailable.
        """
        if isinstance(self.root, dict):
            return {
                key: child.resolve(
                    current_profile_id,
                    feature_id,
                    grain_keys_by_profile,
                    resources,
                    row_context=row_context,
                )
                for key, child in self.children.items()
            }
        if isinstance(self.root, list):
            return [
                child.resolve(
                    current_profile_id,
                    feature_id,
                    grain_keys_by_profile,
                    resources,
                    row_context=row_context,
                )
                for child in self.children.values()
            ]
        if self.row_context_attribute is not None:
            return self._resolve_row_context(row_context)
        if self.prefix is None:
            return self.root
        if self.is_current_feature_reference and self.selector in {None, "id"}:
            return feature_id if feature_id is not None else self.root
        if self.is_grain_reference:
            profile_id = self.profile_id(current_profile_id)
            if (
                grain_keys_by_profile is None
                or profile_id is None
                or profile_id not in grain_keys_by_profile
            ):
                raise ValueError(f"Cannot resolve grain keys for profile {profile_id}")
            return list(grain_keys_by_profile[profile_id])
        if self.is_metadata_reference:
            return self._resolve_metadata(current_profile_id, resources)
        return (
            self.profile_id(current_profile_id)
            if self.prefix == selectors.PROFILE_PREFIX
            else self.identifier
        )

    def _resolve_row_context(self, row_context: row_context_values.RowContext | None) -> object:
        """Resolve a row-context selector to its scalar extent."""
        attribute = self.row_context_attribute
        if attribute not in selectors.ROW_CONTEXT_ATTRIBUTES:
            raise ValueError(f"Unsupported row-context selector: {self.root}")
        if row_context is None:
            raise ValueError("Cannot resolve row-context selector without operator row context")
        if attribute == "dimension":
            if row_context.dimension is None:
                raise ValueError(f"Row-context dimension is unavailable: {self.root}")
            return row_context.dimension.removeprefix(selectors.DIMENSION_PREFIX)
        extent = getattr(row_context, attribute)
        if extent == row_context_values.UNBOUNDED:
            return extent
        measurements = extent.model_dump(exclude_none=True)
        return next(iter(measurements.values()), 0)

    def _resolve_metadata(
        self, current_profile_id: str, resources: BindingResources | None
    ) -> object:
        """Resolve a selected attribute on a declared resource or dimension resolution."""
        prefix = self.prefix
        attribute = self.selector
        resource_id = (
            self.profile_id(current_profile_id)
            if prefix == selectors.PROFILE_PREFIX
            else self.identifier
        )
        if prefix is None or resource_id is None or attribute is None:
            raise ValueError(f"Unsupported resource selector: {self.root}")
        resource = (resources or {}).get(prefix, {}).get(resource_id)
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
