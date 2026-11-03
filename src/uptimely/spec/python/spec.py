"""Python-friendly spec declarations."""

from __future__ import annotations

import dataclasses
import functools
import typing
from collections import abc

from uptimely.spec import catalog as function_catalog
from uptimely.spec import model as spec_model

from . import conversion, dimension
from . import profile as profile_module

__all__ = [
    "Spec",
]


@dataclasses.dataclass(frozen=True)
class Spec:
    """Build a spec from explicitly registered dimensions and profiles.

    Args:
        profiles: Profile classes or declarations with globally unique IDs.
        dimensions: Shared dimensions referenced by profile declarations.
        name: Optional spec display name.
    """

    name: str | None = None
    _profile_sources: abc.Sequence[type[profile_module.Profile] | profile_module.Profile] = (
        dataclasses.field(init=False, repr=False)
    )
    _dimension_sources: abc.Sequence[dimension.Dimension] = dataclasses.field(
        init=False, repr=False
    )

    def __init__(
        self,
        profiles: abc.Sequence[type[profile_module.Profile] | profile_module.Profile],
        dimensions: abc.Sequence[dimension.Dimension] = (),
        name: str | None = None,
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "_profile_sources", profiles)
        object.__setattr__(self, "_dimension_sources", dimensions)

    @functools.cached_property
    def dimensions(self) -> list[dimension.Dimension]:
        """Return explicitly registered dimensions, rejecting duplicate IDs."""
        if not isinstance(self._dimension_sources, abc.Sequence):
            raise TypeError("dimensions must be a sequence of Dimension declarations")
        registered: dict[str, dimension.Dimension] = {}
        for item in self._dimension_sources:
            if not isinstance(item, dimension.Dimension):
                raise TypeError("dimensions must contain Dimension declarations")
            if item.id in registered:
                raise ValueError(f"Duplicate dimension id {item.id}")
            registered[item.id] = item
        return list(registered.values())

    @functools.cached_property
    def profiles(self) -> tuple[profile_module.Profile, ...]:
        """Instantiate profile classes and reject duplicate global IDs."""
        if not isinstance(self._profile_sources, abc.Sequence):
            raise TypeError("profiles must be a sequence of Profile classes or declarations")
        declarations: list[profile_module.Profile] = []
        identifiers: set[str] = set()
        for item in self._profile_sources:
            if isinstance(item, type) and issubclass(item, profile_module.Profile):
                declaration = item()
            elif isinstance(item, profile_module.Profile):
                declaration = item
            else:
                raise TypeError("profiles must contain Profile classes or declarations")
            if declaration.id in identifiers:
                raise ValueError(f"Duplicate profile id {declaration.id}")
            identifiers.add(declaration.id)
            declarations.append(declaration)
        return tuple(declarations)

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Collect and merge the function catalog across all profiles."""
        functions = function_catalog.merge_function_catalogs(
            (profile.function_catalog() for profile in self.profiles),
        )
        return spec_model.FunctionCatalog(root=functions)

    def to_model(self) -> spec_model.Spec:
        """Return the spec document model without resolving entrypoints."""
        return conversion.to_model(
            profiles=self.profiles,
            functions=self.function_catalog(),
            name=self.name,
            dimensions=self.dimensions,
        )

    def to_dict(self) -> dict[str, typing.Any]:
        """Return the spec document as a dictionary."""
        return conversion.to_dict(
            profiles=self.profiles,
            functions=self.function_catalog(),
            name=self.name,
            dimensions=self.dimensions,
        )
