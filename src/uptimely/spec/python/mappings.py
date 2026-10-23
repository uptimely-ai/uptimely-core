"""Declarative function bindings and their produced features."""

from __future__ import annotations

import dataclasses
import inspect
import typing
from collections import abc

from uptimely.spec import catalog, operations, selectors
from uptimely.spec import model as spec_model

from . import bind, ref
from . import feature as feature_module
from . import row_context as row_context_module

__all__ = ["FunctionMapping", "operation"]

_OPERATION_ATTRIBUTE = "__uptimely_operation__"
_Parameters = typing.ParamSpec("_Parameters")
_Result = typing.TypeVar("_Result")


def operation(
    value: operations.FunctionOperation,
) -> abc.Callable[
    [abc.Callable[_Parameters, _Result]],
    abc.Callable[_Parameters, _Result],
]:
    """Annotate an analytical function with its spec operation."""
    if value not in operations.FUNCTION_OPERATIONS:
        raise ValueError(f"Unsupported function operation: {value}")

    def annotate(
        function: abc.Callable[_Parameters, _Result],
    ) -> abc.Callable[_Parameters, _Result]:
        setattr(function, _OPERATION_ATTRIBUTE, value)
        return function

    return annotate


@dataclasses.dataclass(frozen=True, kw_only=True)
class FunctionMapping:
    """Declare an analytical function call without executing it.

    Args:
        function: Real callable, entrypoint string, or explicit function reference.
        arguments: Named implementation arguments, including structural references.
        outputs: Named output features in declaration order; empty for writes.
        function_id: Optional function catalog ID, defaulting to the function name.
        inputs: Explicit dependency override for opaque dataframe access. Otherwise
            dependencies are collected from feature-valued arguments. Identifier
            selectors do not imply data dependencies.
        row_context: Function-call-specific observation requirements, merged with
            argument annotations.
    """

    function: abc.Callable[..., object] | str | ref.FunctionReference
    arguments: dict[str, typing.Any]
    outputs: list[feature_module.Feature]
    function_id: str | None = None
    inputs: list[ref.Reference | str] | None = None
    row_context: (
        row_context_module.RowContext | row_context_module.RowContextBinding[typing.Any] | None
    ) = None

    def __post_init__(self) -> None:
        """Validate operation metadata and consolidate observation requirements."""
        _ = self.operation
        names = [output.name for output in self.outputs]
        if len(names) != len(set(names)):
            raise ValueError("Function-call output feature names must not repeat")
        object.__setattr__(
            self, "row_context", row_context_module._context(self.arguments, self.row_context)
        )

    @property
    def operation(self) -> operations.FunctionOperation:
        """Return the operation declared on the callable or function reference."""
        if isinstance(self.function, ref.FunctionReference):
            value = self.function.operation
        elif callable(self.function):
            value = getattr(self.function, _OPERATION_ATTRIBUTE, None)
        else:
            value = None
        if value not in operations.FUNCTION_OPERATIONS:
            raise ValueError(
                "Function must be annotated with @operation(...) or supplied as a "
                "FunctionReference with operation metadata"
            )
        return typing.cast(operations.FunctionOperation, value)

    @property
    def reference(self) -> ref.FunctionReference:
        """Return the function location without importing entrypoint strings."""
        if isinstance(self.function, ref.FunctionReference):
            return self.function
        return ref.function(self.function, operation=self.operation)

    @property
    def catalog_id(self) -> str:
        """Return the explicit or function-derived catalog identifier."""
        return self.function_id or self.reference.name

    def bound_arguments(self) -> dict[str, typing.Any]:
        """Return declared arguments and validate real callable argument names.

        Entrypoint strings remain import-free during authoring; their signature
        validation happens during compilation unless explicitly disabled.
        """
        arguments = self.arguments.copy()
        if callable(self.function):
            inspect.signature(self.function).bind(**arguments)
        return arguments

    def to_model(self, identifier: str) -> spec_model.Mapping:
        """Convert a named declaration to a canonical mapping."""
        arguments = self.bound_arguments()
        inputs = (
            [_feature_id(value) for value in self.inputs]
            if self.inputs is not None
            else _inputs(self.arguments)
        )
        return spec_model.Mapping(
            id=identifier,
            binding=spec_model.Binding(
                function=self.catalog_id,
                args={name: bind._binding_value(value) for name, value in arguments.items()},
            ),
            features={
                "inputs": [f"{selectors.FEATURE_PREFIX}{name}" for name in inputs],
                "outputs": [f"{selectors.FEATURE_PREFIX}{output.name}" for output in self.outputs],
            },
            row_context=self.row_context,
        )

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Build the reusable function contract for this binding."""
        arguments = {
            name: spec_model.Argument(id=name, **bind._argument_definition(value))
            for name, value in self.bound_arguments().items()
        }
        return spec_model.FunctionCatalog(
            root={
                self.catalog_id: catalog.function_template(
                    function_id=self.catalog_id,
                    operation=self.operation,
                    entrypoint=self.reference.entrypoint,
                    args=arguments,
                    validate_signature=self.reference.validate_signature,
                )
            }
        )


def _feature_id(value: ref.Reference | str) -> str:
    """Normalize an explicit dependency, rejecting non-feature references."""
    if isinstance(value, ref.Reference):
        prefix, _, identifier = value.value.rpartition(".")
        if prefix != selectors.FEATURE_PREFIX.removesuffix("."):
            raise ValueError(f"Mapping input must reference a feature, got {value.value!r}")
        return identifier
    return value.removeprefix(selectors.FEATURE_PREFIX)


def _inputs(value: object) -> list[str]:
    """Collect feature dependencies recursively without treating IDs as data."""
    if isinstance(value, row_context_module.RowContextBinding):
        return _inputs(value.value)
    if isinstance(value, ref.Reference):
        if value.type == "feature":
            return [value.value.removeprefix(selectors.FEATURE_PREFIX)]
        return []
    if isinstance(value, bind.Bind):
        return _inputs(value.args)
    if isinstance(value, abc.Mapping):
        children = value.values()
    elif isinstance(value, (list, tuple)):
        children = value
    else:
        return []
    result: list[str] = []
    for child in children:
        for name in _inputs(child):
            if name not in result:
                result.append(name)
    return result
