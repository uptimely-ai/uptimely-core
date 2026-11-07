"""Declarative analytical work and its data and execution requirements."""

from __future__ import annotations

import dataclasses
import inspect
import typing
from collections import abc

from uptimely.spec import (
    arg_types,
    selectors,
)
from uptimely.spec import (
    function_kinds as functions,
)
from uptimely.spec import model as spec_model
from uptimely.spec import (
    row_context as row_context_values,
)

from . import binding_conversion, ref
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
        """Copy and validate declarations at the authoring boundary."""
        if self.inputs is not None:
            if not isinstance(self.inputs, abc.Sequence) or isinstance(self.inputs, (str, bytes)):
                raise TypeError("Operator inputs must be a sequence of feature references")
            object.__setattr__(self, "inputs", list(self.inputs))
        if not isinstance(self.outputs, abc.Sequence) or isinstance(self.outputs, (str, bytes)):
            raise TypeError("Operator outputs must be a sequence of Features")
        object.__setattr__(self, "outputs", list(self.outputs))
        self._input_ids()
        _ = self.output_ids

    @property
    def output_ids(self) -> list[str]:
        """Return the declared output feature IDs in order."""
        identifiers = []
        for output in self.outputs:
            if not isinstance(output, feature_module.Feature):
                raise TypeError("Operator outputs must contain Features")
            identifiers.append(self._validate_feature_id(output.id))
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Operator output feature IDs must not repeat")
        return identifiers

    def to_model(
        self, *, compute: spec_model.Binding, merge: spec_model.Binding | None = None
    ) -> spec_model.Interface:
        """Convert explicit or inferred dependencies to canonical feature selectors.

        Args:
            compute: Canonical computation binding used to infer omitted inputs.
            merge: Optional canonical merge binding contributing inferred inputs.

        Returns:
            An interface with ordered inputs and declared outputs.
        """
        if self.inputs is None:
            outputs = set(self.output_ids)
            inferred = list(compute.inferred_feature_inputs)
            if merge is not None:
                inferred.extend(merge.inferred_feature_inputs)
            inputs = [name for name in dict.fromkeys(inferred) if name not in outputs]
        else:
            inputs = self._input_ids()
        return spec_model.Interface(
            inputs=[f"{selectors.FEATURE_PREFIX}{name}" for name in inputs],
            outputs=[f"{selectors.FEATURE_PREFIX}{name}" for name in self.output_ids],
        )

    def _input_ids(self) -> list[str]:
        """Normalize explicit inputs and require unique feature identifiers."""
        if self.inputs is None:
            return []
        identifiers = [self._feature_id(value) for value in self.inputs]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Operator input feature IDs must not repeat")
        return identifiers

    @classmethod
    def _feature_id(cls, value: feature_module.Feature | ref.Reference | str) -> str:
        """Normalize and validate a feature identifier or reference."""
        if isinstance(value, feature_module.Feature):
            identifier = value.id
        elif isinstance(value, ref.Reference):
            prefix, separator, identifier = value.value.partition(".")
            if prefix != selectors.FEATURE_PREFIX.removesuffix(".") or not separator:
                raise ValueError(f"Operator input must reference a feature, got {value.value!r}")
        elif isinstance(value, str):
            if value.startswith(selectors.FEATURE_PREFIX):
                identifier = value.removeprefix(selectors.FEATURE_PREFIX)
            elif value.startswith("$"):
                raise ValueError(f"Operator input must reference a feature, got {value!r}")
            else:
                identifier = value
        else:
            raise TypeError("Operator inputs must be Feature objects, references, or strings")
        return cls._validate_feature_id(identifier)

    @staticmethod
    def _validate_feature_id(identifier: str) -> str:
        """Reject empty, nested, or current-feature selectors as feature IDs."""
        if (
            not isinstance(identifier, str)
            or not identifier
            or "." in identifier
            or identifier == selectors.CURRENT_ID
        ):
            raise ValueError(f"Invalid operator feature ID: {identifier!r}")
        return identifier


@dataclasses.dataclass(frozen=True, kw_only=True)
class Binding:
    """Declare an implementation and its named arguments."""

    function: _Function
    arguments: dict[str, typing.Any] = dataclasses.field(default_factory=dict)

    @property
    def _declared_kind(self) -> functions.FunctionKindId | None:
        """Return function semantics without requiring a complete contract."""
        if isinstance(self.function, ref.FunctionReference):
            return self.function.kind
        if callable(self.function):
            return function_semantics.declared_kind(self.function)
        return None

    @property
    def kind(self) -> functions.FunctionKindId:
        """Return the required function kind.

        Raises:
            ValueError: If the implementation has no supported declared kind.
        """
        value = self._declared_kind
        if value is None or value not in functions.FUNCTION_KINDS:
            raise ValueError(
                "Function kind is required: use @function(kind=...) or "
                "ref.function(..., kind=...) for an undecorated implementation"
            )
        return value

    @property
    def reference(self) -> ref.FunctionReference:
        """Return the normalized entrypoint without importing string references."""
        if isinstance(self.function, ref.FunctionReference):
            return self.function
        return ref.function(self.function)

    def bound_arguments(self) -> dict[str, typing.Any]:
        """Copy arguments after validating signatures of in-process callables.

        Entrypoint strings and references are not imported during authoring;
        their signature validation is deferred until compilation.
        """
        if callable(self.function):
            inspect.signature(self.function).bind(**self.arguments)
        return self.arguments.copy()

    def to_model(self) -> spec_model.Binding:
        """Convert this binding to the canonical document model."""
        arguments = self.bound_arguments()
        return spec_model.Binding(
            function=self.reference.name,
            args={name: binding_conversion.to_value(value) for name, value in arguments.items()},
        )

    def to_function_template(self) -> spec_model.FunctionTemplate:
        """Build the reusable function contract, including merge-target optionality."""
        argument_definitions = {
            name: binding_conversion.argument_definition(value)
            for name, value in self.bound_arguments().items()
        }
        reference = self.reference
        kind = self.kind
        if kind == functions.MERGE and "target" in argument_definitions:
            argument_definitions["target"]["type"] = arg_types.OPTIONAL_DATAFRAME
        return spec_model.FunctionTemplate(
            id=reference.name,
            kind=kind,
            returns=functions.FUNCTION_KINDS[kind].returns,
            entrypoint=reference.entrypoint,
            validate_signature=reference.validate_signature,
            args={
                name: spec_model.Argument(id=name, **definition)
                for name, definition in argument_definitions.items()
            },
            description=reference.description,
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
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

    def __post_init__(self) -> None:
        """Validate the declaration and merge argument-level row-context annotations."""
        if not isinstance(self.compute, Binding):
            raise TypeError("Operator compute must be a Binding")
        if not isinstance(self.interface, Interface):
            raise TypeError("Operator interface must be an Interface")
        if self.merge is not None and not isinstance(self.merge, Binding):
            raise TypeError("Operator merge must be a Binding or None")
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Operator requires a non-empty id")
        kind = self.kind
        if kind == functions.MERGE:
            raise ValueError("Merge functions must be declared in Operator.merge")
        if self.merge is not None:
            if kind == functions.VECTORIZE:
                raise ValueError("Vectorize operators cannot declare a merge binding")
            if not functions.FUNCTION_KINDS[kind].produces_fragment:
                raise ValueError(f"{kind.capitalize()} operators cannot declare a merge binding")
            if self.merge._declared_kind != functions.MERGE:
                raise ValueError("Operator merge binding must reference a function of kind 'merge'")
        object.__setattr__(
            self,
            "row_context",
            row_context_module._context(self.compute.arguments, self.row_context),
        )

    @property
    def kind(self) -> functions.FunctionKindId:
        """Return the kind declared on the function or its reference."""
        return self.compute.kind

    @property
    def reference(self) -> ref.FunctionReference:
        """Return the normalized entrypoint without importing string references."""
        return self.compute.reference

    @property
    def catalog_id(self) -> str:
        """Return the function-derived catalog identifier."""
        return self.reference.name

    def bound_arguments(self) -> dict[str, typing.Any]:
        """Return a copy of arguments, validating names for in-process callables.

        Entrypoint strings are not imported during authoring; signature validation
        for those functions is deferred until compilation.
        """
        return self.compute.bound_arguments()

    def to_model(self) -> spec_model.Operator:
        """Convert this declaration to its canonical document model."""
        compute = self.compute.to_model()
        merge = self.merge.to_model() if self.merge is not None else None
        return spec_model.Operator(
            id=self.id,
            compute=compute,
            merge=merge,
            interface=self.interface.to_model(compute=compute, merge=merge),
            row_context=self.row_context,
        )

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Build the reusable function contract declared by this operator."""
        bindings = [self.compute]
        if self.merge is not None:
            bindings.append(self.merge)
        catalogs = []
        for binding in bindings:
            template = binding.to_function_template()
            catalogs.append(spec_model.FunctionCatalog(root={template.id: template}))
        return spec_model.FunctionCatalog.merge(catalogs)
