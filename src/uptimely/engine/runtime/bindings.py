"""Resolve portable plan arguments against execution resources."""

import pathlib
from collections import abc

from uptimely import plan
from uptimely.spec import selectors

from . import state as state_module


class RuntimeBindings:
    """Resolve named returns, parameters, and paths in JSON arguments."""

    def __init__(
        self,
        state: state_module.RuntimeState,
        parameters: abc.Mapping[str, object],
        paths: abc.Mapping[str, str] | None = None,
        project_root: pathlib.Path | None = None,
    ) -> None:
        """Create a resolver for one execution's values and project context."""
        self.state = state
        self.parameters = parameters
        self.paths = {} if paths is None else paths
        self.project_root = project_root

    def resolve_args(self, invocation: plan.Invocation) -> dict[str, object]:
        """Resolve all argument values for an invocation."""
        return {name: self.resolve_value(value) for name, value in invocation.arguments.items()}

    def resolve_value(self, value: object) -> object:
        """Recursively resolve reserved references in a plan argument.

        Raises:
            ValueError: A referenced return, parameter, or path is unavailable.
        """
        if isinstance(value, str):
            if value.startswith(plan.Variable.PREFIXES):
                return self.state.resolve(value)
            if value.startswith(selectors.PARAMS_PREFIX):
                name = value.removeprefix(selectors.PARAMS_PREFIX)
                if name not in self.parameters:
                    raise ValueError(f"Unresolved parameter: {name}")
                return self.parameters[name]
            if value.startswith(selectors.PATHS_PREFIX):
                name = value.removeprefix(selectors.PATHS_PREFIX)
                if name not in self.paths:
                    raise ValueError(f"Unresolved path: {name}")
                path = pathlib.Path(self.paths[name])
                if path.is_absolute():
                    return str(path)
                if self.project_root is None:
                    raise ValueError(
                        f"Cannot resolve project-relative path without a project root: {name}"
                    )
                return str(self.project_root / path)
        if isinstance(value, list):
            return [self.resolve_value(item) for item in value]
        if isinstance(value, dict):
            return {name: self.resolve_value(item) for name, item in value.items()}
        return value
