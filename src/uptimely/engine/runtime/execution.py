"""Resolve and execute explicit plan calls."""

import pathlib
from collections import abc

from uptimely import plan
from uptimely.codebase.python import entrypoint as entrypoint_module

from . import bindings
from . import state as state_module


class InvocationExecutor:
    """Resolve and execute one invocation without analytical dispatch."""

    def __init__(
        self,
        entrypoints: abc.Mapping[str, entrypoint_module.Entrypoint],
        parameters: abc.Mapping[str, object],
        state: state_module.RuntimeState,
        *,
        paths: abc.Mapping[str, str] | None = None,
        project_root: pathlib.Path | None = None,
    ) -> None:
        """Create an executor for one plan execution."""
        self.entrypoints = entrypoints
        self.bindings = bindings.RuntimeBindings(state, parameters, paths, project_root)

    def resolve_arguments(self, invocation: plan.Invocation) -> dict[str, object]:
        """Resolve the arguments for one invocation."""
        return self.bindings.resolve_args(invocation)

    def execute(self, invocation: plan.Invocation, arguments: abc.Mapping[str, object]) -> object:
        """Call the entrypoint with the resolved arguments."""
        return self.entrypoints[invocation.entrypoint].load()(**arguments)
