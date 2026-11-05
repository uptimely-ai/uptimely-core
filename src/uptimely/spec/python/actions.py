"""Declarative analytical work and its data and execution requirements."""

from __future__ import annotations

import dataclasses
import inspect
import typing
from collections import abc

from uptimely import row_context as row_context_values
from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model

from . import bind, binding_conversion, ref
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
        row_context: Operator-specific observation requirements, merged with
            argument annotations.
    """

    id: str
    interface: Interface
    compute: Binding
    row_context: (
        row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
    ) = None

    def __init__(
        self,
        *,
        id: str,
        interface: Interface,
        compute: Binding,
        row_context: (
            row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
        ) = None,
    ) -> None:
        """Validate the declaration and merge argument-level row-context annotations."""
        if not isinstance(compute, Binding):
            raise TypeError("Operator compute must be a Binding")
        if not isinstance(interface, Interface):
            raise TypeError("Operator interface must be an Interface")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "interface", interface)
        object.__setattr__(self, "compute", compute)
        object.__setattr__(self, "row_context", row_context)
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Operator requires a non-empty id")
        _ = self.kind
        output_ids = [output.id for output in self.interface.outputs]
        if len(output_ids) != len(set(output_ids)):
            raise ValueError("Operator output feature IDs must not repeat")
        object.__setattr__(
            self,
            "row_context",
            row_context_module._context(self.compute.arguments, self.row_context),
        )

    @property
    def kind(self) -> functions.FunctionKindId:
        """Return the kind declared on the function or its reference."""
        if isinstance(self.compute.function, ref.FunctionReference):
            value = self.compute.function.kind
        elif callable(self.compute.function):
            value = function_semantics.declared_kind(self.compute.function)
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
        if isinstance(self.compute.function, ref.FunctionReference):
            return self.compute.function
        return ref.function(self.compute.function)

    @property
    def catalog_id(self) -> str:
        """Return the function-derived catalog identifier."""
        return self.reference.name

    def bound_arguments(self) -> dict[str, typing.Any]:
        """Return a copy of arguments, validating names for in-process callables.

        Entrypoint strings are not imported during authoring; signature validation
        for those functions is deferred until compilation.
        """
        if callable(self.compute.function):
            inspect.signature(self.compute.function).bind(**self.compute.arguments)
        return self.compute.arguments.copy()

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
            features=self._action_features(inputs, self.interface.outputs),
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
        if self.interface.inputs is None:
            outputs = {output.id for output in self.interface.outputs}
            return [name for name in self._inputs(self.compute.arguments) if name not in outputs]
        return [self._feature_id(value) for value in self.interface.inputs]

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
                if reference.kind == "feature"
            )
        )

    @staticmethod
    def _references(value: object) -> typing.Iterator[ref.Reference]:
        """Yield references nested in argument bindings."""
        if isinstance(value, row_context_module.RowContextBinding):
            yield from Operator._references(value.value)
        elif isinstance(reference := binding_conversion.resource_reference(value), ref.Reference):
            yield reference
        elif isinstance(value, bind.Bind):
            yield from Operator._references(value.args)
        elif isinstance(value, abc.Mapping):
            for child in value.values():
                yield from Operator._references(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                yield from Operator._references(child)
