"""Resolve portable plan values against execution resources and runtime state."""

import typing
from collections import abc

from uptimely import plan as plan_module
from uptimely.spec import arg_types, selectors

from . import state as state_module


class RuntimeBindings:
    """Resolve typed invocation arguments, global parameters, and dataframe IDs."""

    def __init__(
        self,
        state: state_module.RuntimeState,
        parameters: abc.Mapping[str, typing.Any],
    ) -> None:
        """Create a resolver for one execution's parameters and runtime state."""
        self.state = state
        self.parameters = parameters

    def resolve_args(
        self,
        invocation: plan_module.Invocation,
        *,
        staged_fragment: object | None = None,
    ) -> dict[str, object]:
        """Bind compiled argument values to runtime values using declared argument types."""
        return {
            name: self.resolve_value(
                value,
                invocation.argument_types.get(name),
                staged_fragment=staged_fragment,
            )
            for name, value in invocation.arguments.items()
        }

    def resolve_value(
        self,
        value: object,
        argument_type: str | None = None,
        *,
        staged_fragment: object | None = None,
    ) -> object:
        """Recursively resolve one typed plan binding value."""
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if value == f"{selectors.OPERATOR_PREFIX}{selectors.CURRENT_ID}.fragment":
            if argument_type != arg_types.DATAFRAME:
                raise ValueError("Merge fragment argument must have dataframe type")
            if staged_fragment is None:
                raise ValueError("Staged fragment is unavailable")
            return staged_fragment
        if arg_types.is_dataframe(argument_type or "") and isinstance(value, str):
            frame = self.state.resolve_dataset_or_fragment_dataframe(value)
            if frame is None:
                if argument_type == arg_types.OPTIONAL_DATAFRAME:
                    return None
                raise ValueError(f"Profile dataframe is unavailable: {value}")
            return frame
        if isinstance(value, str) and value.startswith(selectors.PARAMS_PREFIX):
            return self.resolve_parameter_reference(value)
        if isinstance(value, str) and value == "$params":
            raise ValueError(f"Malformed parameter reference: {value}")
        if isinstance(value, str) and value.startswith("?"):
            raise ValueError(
                f"Legacy runtime reference {value!r} is unsupported; use a $params.<name> reference"
            )
        if isinstance(value, list):
            element_type = (
                arg_types.array_item_type(argument_type) if argument_type is not None else None
            )
            return [
                self.resolve_value(item, element_type, staged_fragment=staged_fragment)
                for item in value
            ]
        if isinstance(value, dict):
            value_type = (
                arg_types.object_value_type(argument_type) if argument_type is not None else None
            )
            return {
                name: self.resolve_value(item, value_type, staged_fragment=staged_fragment)
                for name, item in value.items()
            }
        return value

    def resolve_parameter_reference(self, value: str) -> object:
        """Resolve a required ``$params.<name>`` project parameter."""
        name = value.removeprefix(selectors.PARAMS_PREFIX)
        if not name or "." in name or not name.isidentifier():
            raise ValueError(f"Malformed parameter reference: {value}")
        if name not in self.parameters:
            raise ValueError(f"Unresolved parameter: {name}")
        return self.parameters[name]
