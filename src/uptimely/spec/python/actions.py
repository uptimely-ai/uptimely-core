"""Declarative analytical work and its data and execution requirements."""

from __future__ import annotations

import dataclasses
import inspect
import typing
from collections import abc

from uptimely import row_context as row_context_values
from uptimely.spec import catalog, functions, selectors
from uptimely.spec import model as spec_model

from . import bind, binding_conversion, ref
from . import feature as feature_module
from . import functions as function_semantics
from . import row_context as row_context_module

__all__ = ["Action"]

_Function = abc.Callable[..., object] | str | ref.FunctionReference


@dataclasses.dataclass(frozen=True, kw_only=True)
class Action:
    """Declare analytical work without executing its implementation.

    Args:
        id: Non-empty action identifier, unique within its dataset.
        function: Real callable, entrypoint string, or explicit function reference.
        arguments: Named implementation arguments, including structural references.
        outputs: Named output features in declaration order; empty for writes.
        function_id: Optional function catalog ID, defaulting to the function name.
        inputs: Explicit dependency override for opaque dataframe access. Otherwise
            dependencies are collected from feature-valued arguments. Identifier
            selectors do not imply data dependencies.
        row_context: Action-specific observation requirements, merged with
            argument annotations.
    """

    id: str
    function: _Function
    arguments: dict[str, typing.Any]
    outputs: list[feature_module.Feature]
    function_id: str | None = None
    inputs: list[ref.Reference | str] | None = None
    row_context: (
        row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
    ) = None

    def __post_init__(self) -> None:
        """Validate the declaration and merge argument-level row-context annotations."""
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Action requires a non-empty id")
        _ = self.kind
        output_names = [output.name for output in self.outputs]
        if len(output_names) != len(set(output_names)):
            raise ValueError("Action output feature names must not repeat")
        self._validate_output_references()
        object.__setattr__(
            self, "row_context", row_context_module._context(self.arguments, self.row_context)
        )

    @property
    def kind(self) -> functions.FunctionKind:
        """Return the kind declared on the function or its reference."""
        if isinstance(self.function, ref.FunctionReference):
            value = self.function.kind
        elif callable(self.function):
            value = function_semantics.declared_kind(self.function)
        else:
            value = None
        if value not in functions.FUNCTION_KINDS:
            raise ValueError(
                "Function kind is required: use @function(kind=...) or "
                "ref.function(..., kind=...) for an undecorated implementation"
            )
        return typing.cast(functions.FunctionKind, value)

    @property
    def reference(self) -> ref.FunctionReference:
        """Return the normalized entrypoint without importing string references."""
        if isinstance(self.function, ref.FunctionReference):
            return self.function
        return ref.function(self.function)

    @property
    def catalog_id(self) -> str:
        """Return the explicit or function-derived catalog identifier."""
        return self.function_id or self.reference.name

    def bound_arguments(self) -> dict[str, typing.Any]:
        """Return a copy of arguments, validating names for in-process callables.

        Entrypoint strings are not imported during authoring; signature validation
        for those functions is deferred until compilation.
        """
        self._validate_output_references()
        if callable(self.function):
            inspect.signature(self.function).bind(**self.arguments)
        return self.arguments.copy()

    def _validate_output_references(self) -> None:
        output_names = {output.name for output in self.outputs}
        for reference in _references(self.arguments):
            if isinstance(reference, ref.OutputReference) and reference.name not in output_names:
                raise ValueError(
                    f"Action '{self.id}' references undeclared output '{reference.name}'"
                )

    def to_model(self) -> spec_model.Action:
        """Convert this declaration to its canonical document model."""
        arguments = self.bound_arguments()
        inputs = (
            [_feature_id(value) for value in self.inputs]
            if self.inputs is not None
            else _inputs(self.arguments)
        )
        return spec_model.Action(
            id=self.id,
            binding=spec_model.Binding(
                function=self.catalog_id,
                args={
                    name: binding_conversion.to_value(value) for name, value in arguments.items()
                },
            ),
            features=_action_features(inputs, self.outputs),
            row_context=self.row_context,
        )

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Build the reusable function contract declared by this action."""
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
                    description=reference.description,
                )
            }
        )


def _feature_id(value: ref.Reference | str) -> str:
    """Return a feature identifier or reject a reference to another resource."""
    if isinstance(value, ref.Reference):
        prefix, _, identifier = value.value.rpartition(".")
        if prefix != selectors.FEATURE_PREFIX.removesuffix("."):
            raise ValueError(f"Action input must reference a feature, got {value.value!r}")
        return identifier
    return value.removeprefix(selectors.FEATURE_PREFIX)


def _action_features(
    inputs: abc.Iterable[str],
    outputs: abc.Iterable[feature_module.Feature],
) -> spec_model.ActionFeatures:
    """Build canonical input and output feature selectors."""
    return spec_model.ActionFeatures(
        inputs=[f"{selectors.FEATURE_PREFIX}{name}" for name in inputs],
        outputs=[f"{selectors.FEATURE_PREFIX}{feature.name}" for feature in outputs],
    )


def _inputs(value: object) -> list[str]:
    """Collect unique feature-valued arguments in declaration order."""
    return list(dict.fromkeys(_feature_references(value)))


def _feature_references(value: object) -> typing.Iterator[str]:
    """Yield feature references nested in a binding value."""
    for reference in _references(value):
        if reference.type == "feature":
            yield reference.value.removeprefix(selectors.FEATURE_PREFIX)


def _references(value: object) -> typing.Iterator[ref.Reference]:
    """Yield references nested in argument bindings."""
    if isinstance(value, row_context_module.RowContextBinding):
        yield from _references(value.value)
    elif isinstance(value, ref.Reference):
        yield value
    elif isinstance(value, bind.Bind):
        yield from _references(value.args)
    elif isinstance(value, abc.Mapping):
        for child in value.values():
            yield from _references(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _references(child)
