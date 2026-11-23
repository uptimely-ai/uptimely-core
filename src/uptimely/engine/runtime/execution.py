"""Execute explicit plan calls and store their named returns."""

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
        self.state = state
        self.bindings = bindings.RuntimeBindings(state, parameters, paths, project_root)

    def execute(self, invocation: plan.Invocation) -> None:
        """Call an entrypoint and store its result if it has a return name."""
        arguments = self.bindings.resolve_args(invocation)
        result = self.entrypoints[invocation.entrypoint].load()(**arguments)
        if invocation.returns is not None:
            self.state.store(invocation.returns, result)
