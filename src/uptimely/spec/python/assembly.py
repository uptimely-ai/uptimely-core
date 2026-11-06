"""Declarative analytical work and its data and execution requirements."""

from __future__ import annotations

import dataclasses
import inspect
import typing
from collections import abc

from uptimely import row_context as row_context_values
from uptimely.spec import arg_types, functions, selectors
from uptimely.spec import catalog as function_catalog
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
    """Declare an implementation and its named arguments."""

    function: _Function
    arguments: dict[str, typing.Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, kw_only=True, init=False)
class Operator:
    """Declare operator identity, logical interface, computation, and optional merge.

    Args:
        id: Non-empty operator identifier, unique within its profile.
        interface: Feature dependencies and outputs. Inputs are inferred from
            compute and merge arguments when omitted.
        compute: Computation function and named arguments.
        merge: Optional merge function and named arguments.
        row_context: Operator-specific observation requirements, merged with
            argument annotations.
    """

    id: str
    interface: Interface
    compute: Binding
    merge: Binding | None = None
    row_context: (
        row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
    ) = None

    def __init__(
        self,
        *,
        id: str,
        interface: Interface,
        compute: Binding,
        merge: Binding | None = None,
        row_context: (
            row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
        ) = None,
    ) -> None:
        """Validate the declaration and merge argument-level row-context annotations."""
        if not isinstance(compute, Binding):
            raise TypeError("Operator compute must be a Binding")
        if not isinstance(interface, Interface):
            raise TypeError("Operator interface must be an Interface")
        if merge is not None and not isinstance(merge, Binding):
            raise TypeError("Operator merge must be a Binding or None")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "interface", interface)
        object.__setattr__(self, "compute", compute)
        object.__setattr__(self, "merge", merge)
        object.__setattr__(self, "row_context", row_context)
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Operator requires a non-empty id")
        _ = self.kind
        if self.kind == functions.MERGE:
            raise ValueError("Merge functions must be declared in Operator.merge")
        if self.merge is not None:
            if self.kind == functions.VECTORIZE:
                raise ValueError("Vectorize operators cannot declare a merge binding")
            if not functions.FUNCTION_KINDS[self.kind].produces_fragment:
                raise ValueError(
                    f"{self.kind.capitalize()} operators cannot declare a merge binding"
                )
        if self.merge is not None and self._function_kind(self.merge.function) != functions.MERGE:
            raise ValueError("Operator merge binding must reference a function of kind 'merge'")
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
        value = self._function_kind(self.compute.function)
        if value not in functions.FUNCTION_KINDS:
            raise ValueError(
                "Function kind is required: use @function(kind=...) or "
                "ref.function(..., kind=...) for an undecorated implementation"
            )
        return typing.cast(functions.FunctionKindId, value)

    @staticmethod
    def _function_kind(function: _Function) -> functions.FunctionKindId | None:
        """Return the kind declared on a function or its reference."""
        if isinstance(function, ref.FunctionReference):
            value = function.kind
        elif callable(function):
            value = function_semantics.declared_kind(function)
        else:
            value = None
        return typing.cast(functions.FunctionKindId | None, value)

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

    def to_model(self) -> spec_model.Operator:
        """Convert this declaration to its canonical document model."""
        inputs = self._input_ids()
        return spec_model.Operator(
            id=self.id,
            compute=self._binding_model(self.compute),
            merge=self._binding_model(self.merge) if self.merge is not None else None,
            interface=self._model_interface(inputs, self.interface.outputs),
            row_context=self.row_context,
        )

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Build the reusable function contract declared by this operator."""
        catalogs = [self._function_template(self.compute)]
        if self.merge is not None:
            catalogs.append(self._function_template(self.merge))
        return spec_model.FunctionCatalog(root=function_catalog.merge_function_catalogs(catalogs))

    def _function_template(self, binding: Binding) -> spec_model.FunctionCatalog:
        """Build the reusable function contract for one binding."""
        argument_definitions = {
            name: binding_conversion.argument_definition(value)
            for name, value in self._bound_arguments(binding).items()
        }
        if binding is self.merge and "target" in argument_definitions:
            argument_definitions["target"]["type"] = arg_types.OPTIONAL_DATAFRAME
        function_arguments = {
            name: spec_model.Argument(id=name, **definition)
            for name, definition in argument_definitions.items()
        }
        reference = self._binding_reference(binding)
        kind = self._function_kind(binding.function)
        if kind is None or kind not in functions.FUNCTION_KINDS:
            raise ValueError(
                "Function kind is required: use @function(kind=...) or "
                "ref.function(..., kind=...) for an undecorated implementation"
            )
        return spec_model.FunctionCatalog(
            root={
                reference.name: spec_model.FunctionTemplate(
                    id=reference.name,
                    kind=kind,
                    returns=functions.FUNCTION_KINDS[kind].returns,
                    entrypoint=reference.entrypoint,
                    validate_signature=reference.validate_signature,
                    args=function_arguments,
                    description=reference.description,
                )
            }
        )

    def _binding_reference(self, binding: Binding) -> ref.FunctionReference:
        """Return the normalized function reference for one binding."""
        if isinstance(binding.function, ref.FunctionReference):
            return binding.function
        return ref.function(binding.function)

    def _binding_model(self, binding: Binding) -> spec_model.Binding:
        """Convert one Python binding to the canonical document model."""
        arguments = self._bound_arguments(binding)
        reference = self._binding_reference(binding)
        return spec_model.Binding(
            function=reference.name,
            args={name: binding_conversion.to_value(value) for name, value in arguments.items()},
        )

    @staticmethod
    def _bound_arguments(binding: Binding) -> dict[str, typing.Any]:
        """Return supplied arguments, validating in-process callable signatures."""
        if callable(binding.function):
            inspect.signature(binding.function).bind(**binding.arguments)
        return binding.arguments.copy()

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
            inputs = self._inputs(self.compute.arguments)
            if self.merge is not None:
                inputs.extend(self._inputs(self.merge.arguments))
            return [name for name in dict.fromkeys(inputs) if name not in outputs]
        return [self._feature_id(value) for value in self.interface.inputs]

    @staticmethod
    def _model_interface(
        inputs: abc.Iterable[str],
        outputs: abc.Iterable[feature_module.Feature],
    ) -> spec_model.Interface:
        """Build canonical input and output feature selectors."""
        return spec_model.Interface(
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
