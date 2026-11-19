"""Compatibility façade for Python entrypoint APIs."""

from __future__ import annotations

from .address import Entrypoint, Function, Module
from .origin import PackageOrigin, SourceOrigin
from .signatures import DisplaySignature, Signature, TypeAnnotation

__all__ = [
    "DisplaySignature",
    "Entrypoint",
    "Function",
    "Module",
    "PackageOrigin",
    "Signature",
    "SourceOrigin",
    "TypeAnnotation",
]
