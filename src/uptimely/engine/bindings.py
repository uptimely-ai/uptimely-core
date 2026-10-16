"""Resolve portable plan values against execution resources and runtime state."""

import typing
from collections import abc

from uptimely.compiler import plan as plan_module

from . import state as state_module


class RuntimeBindings:
    """Resolve typed callable arguments, runtime placeholders, and dataframe IDs."""

    def __init__(
        self,
        resources: abc.Mapping[str, typing.Any],
        state: state_module.RuntimeState,
        bind: abc.Mapping[str, abc.Mapping[str, abc.Mapping[str, typing.Any]]],
    ) -> None:
        """Create a resolver for one execution's resources, bindings, and runtime state."""
        self.resources = resources
        self.state = state
        self.bind = bind

    def resolve_args(self, callable: plan_module.Callable) -> dict[str, object]:
        """Bind compiled argument values to runtime values using declared argument types."""
        function = self.resources["functions"][callable.function_id]
        if function["operation"] != callable.operation:
            raise ValueError(
                f"Callable {callable.id} operation {callable.operation} does not match "
                f"function {callable.function_id} operation {function['operation']}"
            )
        arguments = function.get("args", {})
        return {
            name: self.resolve_value(value, arguments.get(name, {}).get("type"))
            for name, value in callable.arguments.items()
        }

    def resolve_value(self, value: object, argument_type: str | None = None) -> object:
        """Recursively resolve one typed plan binding value."""
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if argument_type == "dataframe" and isinstance(value, str):
            frame = self.state.dataframe_by_id(value)
            if frame is None:
                raise ValueError(f"Dataset dataframe is unavailable: {value}")
            return frame
        if isinstance(value, str) and value.startswith("?"):
            return self.resolve_runtime_reference(value)
        if isinstance(value, list):
            element_type = (
                argument_type[6:-1]
                if argument_type is not None and argument_type.startswith("array[")
                else None
            )
            return [self.resolve_value(item, element_type) for item in value]
        if isinstance(value, dict):
            value_type = (
                argument_type[12:-1]
                if argument_type is not None and argument_type.startswith("object{str: ")
                else None
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
