"""Index Python implementation entrypoints for one operation."""

from __future__ import annotations

import collections.abc
import dataclasses
import types

from . import address


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
        entrypoint_type: collections.abc.Callable[[str], address.Entrypoint] = address.Entrypoint,
    ) -> Codebase:
        """Create an index for unique entrypoint strings.

        Args:
            locations: Entrypoint strings to parse and index.
            entrypoint_type: Entrypoint constructor used to create indexed objects.

        Returns:
            An immutable entrypoint index.
        """
        return cls({location: entrypoint_type(location) for location in dict.fromkeys(locations)})

    @property
    def entrypoints_index(
        self,
    ) -> collections.abc.Mapping[str, address.Entrypoint]:
        """Return entrypoints keyed by their import location."""
        return self._entrypoints_index
