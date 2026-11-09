"""Declarative analytical work and its data and execution requirements."""

from __future__ import annotations

import dataclasses
import inspect
import typing
from collections import abc

from uptimely.spec import (
    arg_types,
    function_contracts,
    selectors,
)
from uptimely.spec import model as spec_model
from uptimely.spec import (
    row_context as row_context_values,
)

from . import binding_conversion, ref
from . import feature as feature_module
from . import functions as function_metadata
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
        if (
            callable(self.function)
            and function_metadata.declared_metadata(self.function).validate_signature
        ):
            inspect.signature(self.function).bind(**self.arguments)
        reference = self.reference
        if reference.signature is not None:
            reference.signature.bind(**self.arguments)
        if reference.args is not None and set(reference.args) != set(self.arguments):
            raise ValueError("Binding arguments must match the explicit function args contract")
        return self.arguments.copy()

    def to_model(self) -> spec_model.Binding:
        """Convert this binding to the canonical document model."""
        arguments = self.bound_arguments()
        return spec_model.Binding(
            function=self.reference.name,
            args={name: binding_conversion.to_value(value) for name, value in arguments.items()},
        )

    def to_function_template(
        self, *, row_context: row_context_values.RowContext | None = None
    ) -> spec_model.FunctionTemplate:
        """Build a reusable contract without operator-specific classifications."""
        argument_definitions = {
            name: binding_conversion.argument_definition(value, row_context=row_context)
            for name, value in self.bound_arguments().items()
        }
        reference = self.reference
        if reference.returns is None:
            raise ValueError(
                "Explicit returns metadata is required for absent or ambiguous return annotations"
            )
        if reference.args is not None:
            argument_definitions = {name: {"type": value} for name, value in reference.args.items()}
        elif reference.signature is not None:
            for name, definition in argument_definitions.items():
                parameter = reference.signature.parameters.get(name)
                if parameter is not None and definition["type"] == arg_types.DATAFRAME:
                    names = function_contracts.annotation_names(parameter.annotation)
                    if names is not None and "None" in names:
                        definition["type"] = arg_types.OPTIONAL_DATAFRAME
        return spec_model.FunctionTemplate(
            id=reference.name,
            category=reference.category,
            returns=reference.returns,
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
        row_context: Operator-specific observation requirements, merged with
            argument annotations.
        compute: Computation function and named arguments.
        merge: Optional merge function and named arguments.
    """

    id: str
    interface: Interface
    row_context: (
        row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
    ) = None
    compute: Binding
    merge: Binding | None = None

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
        object.__setattr__(
            self,
            "row_context",
            row_context_module._context(self.compute.arguments, self.row_context),
        )

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
        bindings = [("compute", self.compute)]
        if self.merge is not None:
            bindings.append(("merge", self.merge))
        catalogs = []
        for role, binding in bindings:
            template = binding.to_function_template(row_context=self.row_context)
            dataframe_count = sum(
                arg_types.is_dataframe(argument.type) for argument in template.args.values()
            )
            if (role == "compute" and dataframe_count > 1) or (
                role == "merge" and dataframe_count != 2
            ):
                raise ValueError(
                    f"Operator {self.id} {role} binding has invalid dataframe arity: "
                    f"{dataframe_count}"
                )
            if role == "merge" and template.returns != "dataframe":
                raise ValueError("Merge binding must return a dataframe")
            if role == "compute" and self.merge is not None and template.returns != "dataframe":
                raise ValueError("A merge requires a dataframe-producing compute binding")
            catalogs.append(spec_model.FunctionCatalog(root={template.id: template}))
        return spec_model.FunctionCatalog.merge(catalogs)
