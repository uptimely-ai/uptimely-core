"""Declarative function bindings and their produced features."""

from __future__ import annotations

import dataclasses
import inspect
import typing
from collections import abc

from uptimely.spec import catalog, operations, selectors
from uptimely.spec import model as spec_model

from . import bind, binding_conversion, ref
from . import feature as feature_module
from . import row_context as row_context_module

__all__ = ["FunctionMapping", "kind"]

_KIND_ATTRIBUTE = "__uptimely_kind__"
_Parameters = typing.ParamSpec("_Parameters")
_Result = typing.TypeVar("_Result")
_Function = abc.Callable[..., object] | str | ref.FunctionReference


def kind(
    value: operations.FunctionKind,
) -> abc.Callable[
    [abc.Callable[_Parameters, _Result]],
    abc.Callable[_Parameters, _Result],
]:
    """Mark a callable with the kind used by its mapping."""
    if value not in operations.FUNCTION_KINDS:
        raise ValueError(f"Unsupported function kind: {value}")

    def decorate(
        function: abc.Callable[_Parameters, _Result],
    ) -> abc.Callable[_Parameters, _Result]:
        setattr(function, _KIND_ATTRIBUTE, value)
        return function

    return decorate


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

    function: _Function
    arguments: dict[str, typing.Any]
    outputs: list[feature_module.Feature]
    function_id: str | None = None
    inputs: list[ref.Reference | str] | None = None
    row_context: (
        row_context_module.RowContext | row_context_module.RowContextBinding[typing.Any] | None
    ) = None

    def __post_init__(self) -> None:
        """Validate the declaration and merge argument-level row-context annotations."""
        _ = self.kind
        output_names = [output.name for output in self.outputs]
        if len(output_names) != len(set(output_names)):
            raise ValueError("Function-call output feature names must not repeat")
        object.__setattr__(
            self, "row_context", row_context_module._context(self.arguments, self.row_context)
        )

    @property
    def kind(self) -> operations.FunctionKind:
        """Return the kind declared on the function or its reference."""
        value = (
            self.function.kind
            if isinstance(self.function, ref.FunctionReference)
            else getattr(self.function, _KIND_ATTRIBUTE, None)
        )
        if value not in operations.FUNCTION_KINDS:
            raise ValueError(
                "Function must be annotated with @kind(...) or supplied as a "
                "FunctionReference with kind metadata"
            )
        return typing.cast(operations.FunctionKind, value)

    @property
    def reference(self) -> ref.FunctionReference:
        """Return the normalized entrypoint without importing string references."""
        if isinstance(self.function, ref.FunctionReference):
            return self.function
        return ref.function(self.function, kind=self.kind)

    @property
    def catalog_id(self) -> str:
        """Return the explicit or function-derived catalog identifier."""
        return self.function_id or self.reference.name

    def bound_arguments(self) -> dict[str, typing.Any]:
        """Return a copy of arguments, validating names for in-process callables.

        Entrypoint strings are not imported during authoring; signature validation
        for those functions is deferred until compilation.
        """
        if callable(self.function):
            inspect.signature(self.function).bind(**self.arguments)
        return self.arguments.copy()

    def to_model(self, identifier: str) -> spec_model.Mapping:
        """Convert this declaration to its canonical document model."""
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
                args={
                    name: binding_conversion.to_value(value) for name, value in arguments.items()
                },
            ),
            features=_mapping_features(inputs, self.outputs),
            row_context=self.row_context,
        )

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Build the reusable function contract declared by this mapping."""
        function_arguments = {
            name: spec_model.Argument(id=name, **binding_conversion.argument_definition(value))
            for name, value in self.bound_arguments().items()
        }
        reference = self.reference
        return spec_model.FunctionCatalog(
            root={
                self.catalog_id: catalog.function_template(
                    function_id=self.catalog_id,
                    kind=self.kind,
                    entrypoint=reference.entrypoint,
                    args=function_arguments,
                    validate_signature=reference.validate_signature,
                )
            }
        )


def _feature_id(value: ref.Reference | str) -> str:
    """Return a feature identifier or reject a reference to another resource."""
    if isinstance(value, ref.Reference):
        prefix, _, identifier = value.value.rpartition(".")
        if prefix != selectors.FEATURE_PREFIX.removesuffix("."):
            raise ValueError(f"Mapping input must reference a feature, got {value.value!r}")
        return identifier
    return value.removeprefix(selectors.FEATURE_PREFIX)


def _mapping_features(
    inputs: abc.Iterable[str],
    outputs: abc.Iterable[feature_module.Feature],
) -> spec_model.MappingFeatures:
    """Build canonical input and output feature selectors."""
    return spec_model.MappingFeatures(
        inputs=[f"{selectors.FEATURE_PREFIX}{name}" for name in inputs],
        outputs=[f"{selectors.FEATURE_PREFIX}{feature.name}" for feature in outputs],
    )


def _inputs(value: object) -> list[str]:
    """Collect unique feature-valued arguments in declaration order."""
    return list(dict.fromkeys(_feature_references(value)))


def _feature_references(value: object) -> typing.Iterator[str]:
    """Yield feature references nested in a binding value."""
    if isinstance(value, row_context_module.RowContextBinding):
        yield from _feature_references(value.value)
    elif isinstance(value, ref.Reference):
        if value.type == "feature":
            yield value.value.removeprefix(selectors.FEATURE_PREFIX)
    elif isinstance(value, bind.Bind):
        yield from _feature_references(value.args)
    elif isinstance(value, abc.Mapping):
        for child in value.values():
            yield from _feature_references(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _feature_references(child)
