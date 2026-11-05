"""Declarative analytical work and its data and execution requirements."""

from __future__ import annotations

import dataclasses
import inspect
import typing
from collections import abc

from uptimely import row_context as row_context_values
from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model

from . import bind, binding_conversion, ref, validation
from . import feature as feature_module
from . import functions as function_semantics
from . import row_context as row_context_module

__all__ = ["Operator", "Interface", "Binding"]

_Function = abc.Callable[..., object] | str | ref.FunctionReference


@dataclasses.dataclass(frozen=True, kw_only=True)
class Interface:
    """Declare the feature dependencies and outputs of an operator."""

    inputs: list[feature_module.Feature | ref.Reference | str] | None = None
    outputs: list[feature_module.Feature] = dataclasses.field(default_factory=list)

    def __post_init__(self) -> None:
        """Copy interface collections into mutable lists."""
        if self.inputs is not None:
            object.__setattr__(self, "inputs", list(self.inputs))
        object.__setattr__(self, "outputs", list(self.outputs))


@dataclasses.dataclass(frozen=True, kw_only=True)
class Binding:
    """Bind an implementation to its named arguments."""

    function: _Function
    arguments: dict[str, typing.Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, kw_only=True, init=False)
class Operator:
    """Declare operator identity, logical interface, and computation.

    Args:
        id: Non-empty operator identifier, unique within its profile.
        interface: Feature dependencies and outputs. Inputs are inferred from
            compute arguments when omitted.
        compute: Computation function and named arguments.
        function_id: Optional function catalog ID, defaulting to the function name.
        row_context: Operator-specific observation requirements, merged with
            argument annotations.
    """

    id: str
    compute: Binding
    interface: Interface
    function_id: str | None = None
    row_context: (
        row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
    ) = None

    def __init__(
        self,
        *,
        id: str,
        compute: Binding | None = None,
        interface: Interface | None = None,
        function: _Function | None = None,
        arguments: dict[str, typing.Any] | None = None,
        outputs: abc.Sequence[feature_module.Feature] | None = None,
        inputs: abc.Sequence[feature_module.Feature | ref.Reference | str] | None = None,
        function_id: str | None = None,
        row_context: (
            row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
        ) = None,
    ) -> None:
        """Validate the declaration and merge argument-level row-context annotations."""
        if compute is None:
            if function is None:
                raise TypeError("Operator requires 'function' or 'compute'")
            if arguments is None:
                raise TypeError("Operator requires 'arguments'")
            if outputs is None:
                raise TypeError("Operator requires 'outputs'")
            compute = Binding(function=function, arguments=arguments)
        elif function is not None or arguments is not None:
            compute = Binding(
                function=compute.function if function is None else function,
                arguments=compute.arguments if arguments is None else arguments,
            )
        if interface is None:
            interface = Interface(
                inputs=None if inputs is None else list(inputs),
                outputs=[] if outputs is None else list(outputs),
            )
        elif outputs is not None or inputs is not None:
            interface = Interface(
                inputs=interface.inputs if inputs is None else list(inputs),
                outputs=interface.outputs if outputs is None else list(outputs),
            )
        if not isinstance(compute, Binding):
            raise TypeError("Operator compute must be a Binding")
        if not isinstance(interface, Interface):
            raise TypeError("Operator interface must be an Interface")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "compute", compute)
        object.__setattr__(self, "interface", interface)
        object.__setattr__(self, "function_id", function_id)
        object.__setattr__(self, "row_context", row_context)
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Operator requires a non-empty id")
        _ = self.kind
        output_ids = [output.id for output in self.interface.outputs]
        if len(output_ids) != len(set(output_ids)):
            raise ValueError("Operator output feature IDs must not repeat")
        validation.validate_action_output_references(
            self.id,
            self._references(self.arguments),
            (output.id for output in self.outputs),
        )
        object.__setattr__(
            self, "row_context", row_context_module._context(self.arguments, self.row_context)
        )

    @property
    def function(self) -> _Function:
        """Return the bound implementation."""
        return self.compute.function

    @property
    def arguments(self) -> dict[str, typing.Any]:
        """Return the computation's named arguments."""
        return self.compute.arguments

    @property
    def outputs(self) -> list[feature_module.Feature]:
        """Return the action's declared output features."""
        return self.interface.outputs

    @property
    def inputs(self) -> list[feature_module.Feature | ref.Reference | str] | None:
        """Return declared input features, or None when they are inferred."""
        return self.interface.inputs

    @property
    def kind(self) -> functions.FunctionKindId:
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
        return typing.cast(functions.FunctionKindId, value)

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
        validation.validate_action_output_references(
            self.id, self._references(self.arguments), (output.id for output in self.outputs)
        )
        if callable(self.function):
            inspect.signature(self.function).bind(**self.arguments)
        return self.arguments.copy()

    def to_model(self) -> spec_model.Action:
        """Convert this declaration to its canonical document model."""
        arguments = self.bound_arguments()
        inputs = self._input_ids()
        return spec_model.Action(
            id=self.id,
            binding=spec_model.Binding(
                function=self.catalog_id,
                args={
                    name: binding_conversion.to_value(value) for name, value in arguments.items()
                },
            ),
            features=self._action_features(inputs, self.outputs),
            row_context=self.row_context,
        )

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Build the reusable function contract declared by this operator."""
        function_arguments = {
            name: spec_model.Argument(id=name, **binding_conversion.argument_definition(value))
            for name, value in self.bound_arguments().items()
        }
        reference = self.reference
        return spec_model.FunctionCatalog(
            root={
                self.catalog_id: spec_model.FunctionTemplate(
                    id=self.catalog_id,
                    kind=self.kind,
                    returns=functions.FUNCTION_KINDS[self.kind].returns,
                    entrypoint=reference.entrypoint,
                    validate_signature=reference.validate_signature,
                    args=function_arguments,
                    description=reference.description,
                )
            }
        )

    @staticmethod
    def _feature_id(value: feature_module.Feature | ref.Reference | str) -> str:
        """Return a feature identifier or reject a reference to another resource."""
        if isinstance(value, feature_module.Feature):
            return value.id
        if isinstance(value, ref.Reference):
            prefix, _, identifier = value.value.rpartition(".")
            if prefix != selectors.FEATURE_PREFIX.removesuffix("."):
                raise ValueError(f"Operator input must reference a feature, got {value.value!r}")
            return identifier
        return value.removeprefix(selectors.FEATURE_PREFIX)

    def _input_ids(self) -> list[str]:
        """Return declared input IDs or infer them from feature bindings."""
        if self.inputs is None:
            return self._inputs(self.arguments)
        return [self._feature_id(value) for value in self.inputs]

    @staticmethod
    def _action_features(
        inputs: abc.Iterable[str],
        outputs: abc.Iterable[feature_module.Feature],
    ) -> spec_model.ActionFeatures:
        """Build canonical input and output feature selectors."""
        return spec_model.ActionFeatures(
            inputs=[f"{selectors.FEATURE_PREFIX}{name}" for name in inputs],
            outputs=[f"{selectors.FEATURE_PREFIX}{feature.id}" for feature in outputs],
        )

    @staticmethod
    def _inputs(value: object) -> list[str]:
        """Collect unique feature-valued arguments in declaration order."""
        return list(
            dict.fromkeys(
                reference.value.removeprefix(selectors.FEATURE_PREFIX)
                for reference in Operator._references(value)
                if reference.type == "feature"
            )
        )

    @staticmethod
    def _references(value: object) -> typing.Iterator[ref.Reference]:
        """Yield references nested in argument bindings."""
        if isinstance(value, row_context_module.RowContextBinding):
            yield from Operator._references(value.value)
        elif isinstance(value, ref.Reference):
            yield value
        elif isinstance(value, bind.Bind):
            yield from Operator._references(value.args)
        elif isinstance(value, abc.Mapping):
            for child in value.values():
                yield from Operator._references(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                yield from Operator._references(child)
