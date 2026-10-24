"""An implementation whose optional runtime dependency is not installed."""

import uptimely_missing_runtime_dependency


def read() -> object:
    """Require the optional dependency when invoked."""
    return uptimely_missing_runtime_dependency.read()
