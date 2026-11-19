"""Index Python implementation entrypoints for one operation."""

from __future__ import annotations

import collections.abc
import dataclasses
import types

from . import address, origin


@dataclasses.dataclass(frozen=True)
class Codebase:
    """Operation-scoped index of Python implementation entrypoints."""

    _entrypoints_index: collections.abc.Mapping[str, address.Entrypoint]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_entrypoints_index",
            types.MappingProxyType(dict(self._entrypoints_index)),
        )

    @classmethod
    def from_locations(
        cls,
        locations: collections.abc.Iterable[str],
        packages: collections.abc.Mapping[str, origin.PackageOrigin] | None = None,
        entrypoint_type: collections.abc.Callable[
            [str, origin.PackageOrigin | None], address.Entrypoint
        ] = address.Entrypoint,
    ) -> Codebase:
        """Create an index for unique entrypoint strings.

        Args:
            locations: Entrypoint strings to parse and index.
            packages: Optional package origin keyed by entrypoint string.
            entrypoint_type: Entrypoint constructor used to create indexed objects.

        Returns:
            An immutable entrypoint index.
        """
        packages = packages or {}
        return cls(
            {
                location: (
                    entrypoint_type(location, packages[location])
                    if location in packages
                    else entrypoint_type(location)
                )
                for location in dict.fromkeys(locations)
            }
        )

    @property
    def entrypoints_index(
        self,
    ) -> collections.abc.Mapping[str, address.Entrypoint]:
        """Return entrypoints keyed by their import location."""
        return self._entrypoints_index
