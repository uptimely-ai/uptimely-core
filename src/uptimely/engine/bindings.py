"""Resolve portable plan values against execution resources and runtime state."""

import typing
from collections import abc

from uptimely import execution_plan
from uptimely.spec import arg_types
from uptimely.spec import model as spec_model

from . import state as state_module


class RuntimeBindings:
    """Resolve typed invocation arguments, runtime placeholders, and dataframe IDs."""

    def __init__(
        self,
        spec_definition: spec_model.Spec,
        state: state_module.RuntimeState,
        bind: abc.Mapping[str, abc.Mapping[str, abc.Mapping[str, typing.Any]]],
    ) -> None:
        """Create a resolver for one execution's resources, bindings, and runtime state."""
        self.spec_definition = spec_definition
        self.state = state
        self.bind = bind

    def resolve_args(self, invocation: execution_plan.Invocation) -> dict[str, object]:
        """Bind compiled argument values to runtime values using declared argument types."""
        function = self.spec_definition.functions.get(invocation.function_id)
        if function is None:
            raise ValueError(f"Unknown function: {invocation.function_id}")
        if function.kind != invocation.operation:
            raise ValueError(
                f"Invocation {invocation.id} for mapping {invocation.mapping_id} "
                f"operation {invocation.operation} does not match function "
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
        if isinstance(value, str) and value.startswith("?"):
            return self.resolve_runtime_reference(value)
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

    def resolve_runtime_reference(self, value: str) -> object:
        """Resolve a `?<namespace>.<object>.<attribute>` runtime placeholder."""
        parts = value.removeprefix("?").split(".")
        if len(parts) != 3:
            raise ValueError(f"Malformed runtime reference: {value}")
        namespace, object_id, attribute = parts
        namespace_bindings = self.bind.get(namespace)
        if namespace_bindings is None:
            raise ValueError(f"Unknown runtime namespace: {namespace}")
        object_bindings = namespace_bindings.get(object_id)
        if object_bindings is None:
            raise ValueError(f"Unknown {namespace} object: {object_id}")
        if attribute not in object_bindings:
            raise ValueError(f"{namespace} object {object_id} has no attribute: {attribute}")
        return object_bindings[attribute]
