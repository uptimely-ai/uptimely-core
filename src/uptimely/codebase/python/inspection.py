"""Aggregate metadata discovered from a Python entrypoint."""

from __future__ import annotations

import dataclasses
import inspect
import pathlib

from . import address, origin, signatures


@dataclasses.dataclass(frozen=True)
class CallableInspection:
    """Metadata loaded from one validated Python entrypoint."""

    source_file: str
    source_origin: origin.SourceOrigin
    signature: signatures.Signature
    docstring: str | None

    @classmethod
    def read(
        cls, implementation: address.Entrypoint, project_root: pathlib.Path | None
    ) -> CallableInspection:
        """Inspect an entrypoint's source, origin, signature, and documentation."""
        function = implementation.function.load()
        return cls(
            source_file=implementation.module.source_file,
            source_origin=origin.read_source_origin(function, project_root),
            signature=signatures.Signature.from_callable(function),
            docstring=inspect.getdoc(function),
        )
