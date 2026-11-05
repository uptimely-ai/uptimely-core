"""Shared types for spec document models."""

from __future__ import annotations

import dataclasses
import functools
import typing

import pydantic

from uptimely.spec import selectors


class StrictModel(pydantic.BaseModel):
    """Base model that rejects fields outside the spec contract."""

    model_config = pydantic.ConfigDict(extra="forbid")


def humanize_identifier(identifier: str) -> str:
    """Return a display name for a snake- or kebab-case identifier."""
    return identifier.replace("_", " ").replace("-", " ").title()


class SpecSource(StrictModel):
    """Describe how a spec document was authored or generated."""

    name: str
    generated: bool


class Resolution(StrictModel):
    """A keyed resolution of a dimension."""

    id: str = pydantic.Field(exclude=True)
    key: str
    type: str
    parent: str | None = None


class Dimension(StrictModel):
    """A globally defined observation dimension."""

    id: str = pydantic.Field(exclude=True)
    resolutions: dict[str, Resolution]
    description: str | None = None
    name: str | None = None

    @pydantic.model_validator(mode="after")
    def require_resolutions(self) -> typing.Self:
        """Require a dimension to expose at least one usable resolution."""
        if not self.resolutions:
            raise ValueError("A dimension must declare at least one resolution")
        return self

    @pydantic.model_validator(mode="after")
    def generate_name(self) -> typing.Self:
        """Generate a display name from the dimension ID when one is not supplied."""
        if self.name is None:
            self.name = humanize_identifier(self.id)
        return self


class Argument(StrictModel):
    """A single argument entry under a function template's `args`."""

    id: str = pydantic.Field(exclude=True)
    type: str
    comment: str | None = None


BindingArgument = dict[str, typing.Any] | list[typing.Any] | str | int | float | bool | None


class Binding(StrictModel):
    """Wires a catalog function to its arguments."""

    function: str
    args: dict[str, BindingArgument] = pydantic.Field(default_factory=dict)

    @functools.cached_property
    def values_with_paths(self) -> tuple[tuple[object, tuple[str | int, ...]], ...]:
        """Return nested argument leaves and their relative paths, in supplied order."""
        return tuple(_binding_values(self.args, ()))

    @functools.cached_property
    def dataset_input_references(self) -> tuple[str, ...]:
        """Return dataset data references in order, retaining duplicates and ``@``."""
        return tuple(
            selectors.structural_identifier(value, selectors.PROFILE_PREFIX)
            for value, _ in self.values_with_paths
            if (
                isinstance(value, str)
                and value.startswith(selectors.PROFILE_PREFIX)
                and not value.endswith(selectors.ID_SELECTOR)
                and not value.endswith(selectors.PROFILE_GRAIN_IDS_SELECTOR)
                and (
                    value.endswith(selectors.DATAFRAME_SELECTOR)
                    or "." not in value.removeprefix(selectors.PROFILE_PREFIX)
                )
            )
        )

    def dataset_dependencies(self, current_dataset: str) -> list[str]:
        """Return unique referenced datasets, resolving ``@`` to the current dataset."""
        return list(
            dict.fromkeys(
                current_dataset if identifier == selectors.CURRENT_ID else identifier
                for identifier in self.dataset_input_references
            )
        )

    def resolve_args(
        self,
        profile_id: str,
        feature_id: str | None = None,
        grain_keys_by_profile: typing.Mapping[str, typing.Sequence[str]] | None = None,
    ) -> dict[str, typing.Any]:
        """Resolve structural references in these arguments for an invocation."""
        resolver = BindingArgumentResolver(
            current_profile_id=profile_id,
            feature_id=feature_id,
            grain_keys_by_profile=grain_keys_by_profile,
        )
        return resolver.resolve_arguments(self.args)

    @functools.cached_property
    def references_by_prefix(
        self,
    ) -> dict[str, tuple[tuple[str, tuple[str | int, ...]], ...]]:
        """Group structural references after one traversal of nested arguments."""
        references: dict[str, list[tuple[str, tuple[str | int, ...]]]] = {
            prefix: [] for prefix in selectors.STRUCTURAL_PREFIXES
        }
        for value, path in self.values_with_paths:
            if isinstance(value, str):
                for prefix, matches in references.items():
                    if value.startswith(prefix):
                        matches.append((selectors.structural_identifier(value, prefix), path))
                        break
        return {prefix: tuple(matches) for prefix, matches in references.items()}


def _binding_values(
    value: object, path: tuple[str | int, ...]
) -> typing.Iterator[tuple[object, tuple[str | int, ...]]]:
    """Flatten supplied argument containers once, retaining leaf order and paths."""
    if isinstance(value, pydantic.BaseModel):
        value = value.model_dump()
    if isinstance(value, dict):
        for name, nested in value.items():
            yield from _binding_values(nested, (*path, name))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _binding_values(nested, (*path, index))
    else:
        yield value, path


@dataclasses.dataclass(frozen=True)
class BindingArgumentResolver:
    """Resolve nested binding values using invocation-specific selector context."""

    current_profile_id: str
    feature_id: str | None
    grain_keys_by_profile: typing.Mapping[str, typing.Sequence[str]] | None
    resources: typing.Mapping[str, typing.Mapping[str, pydantic.BaseModel]] = dataclasses.field(
        default_factory=dict
    )

    def resolve_arguments(self, arguments: typing.Mapping[str, object]) -> dict[str, typing.Any]:
        """Resolve every binding argument using this invocation's context."""
        return {name: self._resolve_value(value) for name, value in arguments.items()}

    def _resolve_value(self, value: object) -> object:
        """Resolve structural references recursively within one binding value."""
        if isinstance(value, pydantic.BaseModel):
            value = value.model_dump()
        if isinstance(value, str):
            return self._resolve_reference(value)
        if isinstance(value, dict):
            return {key: self._resolve_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve_value(item) for item in value]
        return value

    def _resolve_reference(self, value: str) -> object:
        """Resolve one structural reference to its execution value."""
        if value in {
            f"{selectors.FEATURE_PREFIX}{selectors.CURRENT_ID}",
            f"{selectors.FEATURE_PREFIX}{selectors.CURRENT_ID}{selectors.ID_SELECTOR}",
        }:
            return self.feature_id if self.feature_id is not None else value

        for prefix in selectors.STRUCTURAL_PREFIXES:
            if not value.startswith(prefix):
                continue
            identifier = value.removeprefix(prefix)
            if prefix == selectors.PROFILE_PREFIX:
                if identifier.endswith(selectors.PROFILE_GRAIN_IDS_SELECTOR):
                    identifier = identifier.removesuffix(selectors.PROFILE_GRAIN_IDS_SELECTOR)
                    profile_id = (
                        self.current_profile_id
                        if identifier == selectors.CURRENT_ID
                        else identifier
                    )
                    if (
                        self.grain_keys_by_profile is None
                        or profile_id not in self.grain_keys_by_profile
                    ):
                        raise ValueError(f"Cannot resolve grain keys for profile {profile_id}")
                    return list(self.grain_keys_by_profile[profile_id])
                identifier = identifier.removesuffix(selectors.DATAFRAME_SELECTOR).removesuffix(
                    selectors.ID_SELECTOR
                )
            else:
                identifier = identifier.removesuffix(selectors.ID_SELECTOR)
            resource_id, separator, attribute = identifier.partition(".")
            if separator:
                if prefix == selectors.PROFILE_PREFIX and resource_id == selectors.CURRENT_ID:
                    resource_id = self.current_profile_id
                resource = self.resources.get(prefix, {}).get(resource_id)
                if resource is None:
                    raise ValueError(f"Cannot resolve resource metadata: {value}")
                if prefix == selectors.DIMENSION_PREFIX and attribute.startswith("resolutions."):
                    _, _, resolution_path = attribute.partition(".")
                    resolution_id, _, attribute = resolution_path.partition(".")
                    resolutions = resource.resolutions
                    resource = resolutions.get(resolution_id)
                    if resource is None:
                        raise ValueError(f"Cannot resolve resolution: {value}")
                    if not attribute:
                        return resource.id
                allowed = {
                    selectors.FEATURE_PREFIX: {"id", "name", "type", "unit", "description"},
                    selectors.PROFILE_PREFIX: {"id", "name", "description", "category", "scope"},
                    selectors.DIMENSION_PREFIX: {
                        "id",
                        "name",
                        "description",
                        "key",
                        "type",
                        "parent",
                    },
                }[prefix]
                if attribute not in allowed or attribute not in type(resource).model_fields:
                    raise ValueError(f"Unsupported resource selector: {value}")
                return getattr(resource, attribute)
            return (
                self.current_profile_id
                if prefix == selectors.PROFILE_PREFIX and identifier == selectors.CURRENT_ID
                else identifier
            )
        return value
