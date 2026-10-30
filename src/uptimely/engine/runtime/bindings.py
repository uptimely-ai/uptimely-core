"""Resolve portable plan values against execution resources and runtime state."""

import typing
from collections import abc

from uptimely import execution_plan
from uptimely.spec import arg_types, selectors
from uptimely.spec import model as spec_model

from . import state as state_module


class RuntimeBindings:
    """Resolve typed invocation arguments, global parameters, and dataframe IDs."""

    def __init__(
        self,
        spec_definition: spec_model.Spec,
        state: state_module.RuntimeState,
        parameters: abc.Mapping[str, typing.Any],
    ) -> None:
        """Create a resolver for one execution's parameters and runtime state."""
        self.spec_definition = spec_definition
        self.state = state
        self.parameters = parameters

    def resolve_args(self, invocation: execution_plan.Invocation) -> dict[str, object]:
        """Bind compiled argument values to runtime values using declared argument types."""
        function = self.spec_definition.functions.get(invocation.function_id)
        if function is None:
            raise ValueError(f"Unknown function: {invocation.function_id}")
        if function.kind != invocation.function_kind:
            raise ValueError(
                f"Invocation {invocation.id} for action {invocation.mapping_id} "
                f"function kind {invocation.function_kind} does not match function "
                f"{invocation.function_id} kind {function.kind}"
            )
        return {
            name: self.resolve_value(
                value, function.args[name].type if name in function.args else None
            )
            for name, value in invocation.arguments.items()
        }

    def resolve_value(self, value: object, argument_type: str | None = None) -> object:
        """Recursively resolve one typed plan binding value."""
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if argument_type == arg_types.DATAFRAME and isinstance(value, str):
            frame = self.state.dataframe_by_id(value)
            if frame is None:
                raise ValueError(f"Dataset dataframe is unavailable: {value}")
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
            return [self.resolve_value(item, element_type) for item in value]
        if isinstance(value, dict):
            value_type = (
                arg_types.object_value_type(argument_type) if argument_type is not None else None
            )
            return {name: self.resolve_value(item, value_type) for name, item in value.items()}
        return value

    def resolve_parameter_reference(self, value: str) -> object:
        """Resolve a required ``$params.<name>`` project parameter."""
        name = value.removeprefix(selectors.PARAMS_PREFIX)
        if not name or "." in name or not name.isidentifier():
            raise ValueError(f"Malformed parameter reference: {value}")
        if name not in self.parameters:
            raise ValueError(f"Unresolved parameter: {name}")
        return self.parameters[name]
