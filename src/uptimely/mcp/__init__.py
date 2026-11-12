"""MCP server exposing saved-build introspection and execution as agent tools."""

import importlib
import typing

from . import state

ServerState = state.ServerState

__all__ = ["ServerState", "create_server", "main"]


def __getattr__(name: str) -> typing.Any:
    """Load server entrypoints lazily to keep ``python -m`` startup clean.

    Args:
        name: Requested package attribute.

    Returns:
        The requested server entrypoint.

    Raises:
        AttributeError: If the package does not expose the requested attribute.
    """
    if name in {"create_server", "main"}:
        return getattr(importlib.import_module(".server", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
