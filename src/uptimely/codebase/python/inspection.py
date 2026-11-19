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
    raw_signature: inspect.Signature
    display_signature: signatures.DisplaySignature
    docstring: str | None

    @classmethod
    def read(
        cls,
        implementation: address.Entrypoint,
        project_root: pathlib.Path | None,
    ) -> CallableInspection:
        """Inspect an entrypoint's source, origin, signature, and documentation."""
        function = implementation.function.load()
        raw_signature = inspect.signature(function, follow_wrapped=True, eval_str=True)
        return cls(
            source_file=implementation.module.source_file,
            source_origin=origin.OriginReader.read_source(function, project_root),
            raw_signature=raw_signature,
            display_signature=signatures.DisplaySignature.from_signature(raw_signature),
            docstring=inspect.getdoc(function),
        )
