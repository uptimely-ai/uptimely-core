"""Declarative analytical work and its data and execution requirements."""

from __future__ import annotations

import dataclasses
import hashlib
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

__all__ = ["Operator", "Bind"]

_Function = abc.Callable[..., object] | str | ref.FunctionReference


@dataclasses.dataclass(frozen=True, init=False)
class Bind:
    """Declare an implementation and its named arguments."""

    function: _Function
    arguments: dict[str, typing.Any]

    def __init__(self, function: _Function, /, **arguments: typing.Any) -> None:
        """Create a bind from an implementation and its keyword arguments.

        Args:
            function: Callable, function reference, or importable function path.
            **arguments: Named values passed to the function.
        """
        object.__setattr__(self, "function", function)
        object.__setattr__(self, "arguments", arguments)

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
            raise ValueError("Bind arguments must match the explicit function args contract")
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


@dataclasses.dataclass(frozen=True, kw_only=True, init=False)
class Operator:
    """Declare an operator with a read, compute, write, or staged binding.

    Args:
        id: Optional non-empty identifier, unique within its profile. When omitted,
            the ID is generated from the primary function and outputs.
        inputs: Feature dependencies. Inputs are inferred from binding arguments
            when omitted.
        outputs: Feature declarations produced by the operator.
        row_context: Operator-specific observation requirements, merged with
            argument annotations.
        read: Function reading a dataframe without a dataframe input.
        compute: Function producing the complete target or a non-dataframe result.
        write: Function consuming one dataframe and returning no result.
        stage: Function producing a fragment for merging.
        merge: Function combining a staged fragment with the target.
    """

    id: str
    inputs: list[feature_module.Feature | ref.Reference | str] | None
    outputs: list[feature_module.Feature]
    row_context: (
        row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
    ) = None
    read: Bind | None = None
    compute: Bind | None = None
    write: Bind | None = None
    stage: Bind | None = None
    merge: Bind | None = None
    _primary_role: typing.Literal["read", "compute", "write", "stage"] = dataclasses.field(
        init=False,
        repr=False,
        compare=False,
    )
    _primary_binding: Bind = dataclasses.field(init=False, repr=False, compare=False)

    def __init__(
        self,
        *,
        id: str | None = None,
        inputs: abc.Sequence[feature_module.Feature | ref.Reference | str] | None = None,
        outputs: abc.Sequence[feature_module.Feature] = (),
        row_context: (
            row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
        ) = None,
        read: Bind | None = None,
        compute: Bind | None = None,
        write: Bind | None = None,
        stage: Bind | None = None,
        merge: Bind | None = None,
    ) -> None:
        """Create an operator, deriving its identifier when one is not supplied."""
        for role, binding in (
            ("read", read),
            ("compute", compute),
            ("write", write),
            ("stage", stage),
            ("merge", merge),
        ):
            if binding is not None and not isinstance(binding, Bind):
                raise TypeError(f"Operator {role} must be a Bind or None")
        if inputs is not None and (
            not isinstance(inputs, abc.Sequence) or isinstance(inputs, (str, bytes))
        ):
            raise TypeError("Operator inputs must be a sequence of feature references")
        if not isinstance(outputs, abc.Sequence) or isinstance(outputs, (str, bytes)):
            raise TypeError("Operator outputs must be a sequence of Features")
        primary_bindings: list[
            tuple[typing.Literal["read", "compute", "write", "stage"], Bind]
        ] = []
        if read is not None:
            primary_bindings.append(("read", read))
        if compute is not None:
            primary_bindings.append(("compute", compute))
        if write is not None:
            primary_bindings.append(("write", write))
        if stage is not None:
            primary_bindings.append(("stage", stage))
        if (
            len(primary_bindings) != 1
            or (stage is not None and merge is None)
            or (merge is not None and read is None and stage is None)
        ):
            raise ValueError(
                "Operator requires one primary binding; merge is allowed only with read or stage"
            )
        primary_role, primary = primary_bindings[0]
        if id is None:
            id = self._generate_id(outputs, primary.reference.name)
        if not isinstance(id, str) or not id.strip():
            raise ValueError("Operator requires a non-empty id")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "inputs", list(inputs) if inputs is not None else None)
        object.__setattr__(self, "outputs", list(outputs))
        object.__setattr__(self, "row_context", row_context)
        object.__setattr__(self, "read", read)
        object.__setattr__(self, "compute", compute)
        object.__setattr__(self, "write", write)
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "merge", merge)
        object.__setattr__(self, "_primary_role", primary_role)
        object.__setattr__(self, "_primary_binding", primary)
        self._input_ids()
        _ = self.output_ids
        self.__post_init__()

    @property
    def _primary(self) -> Bind:
        """Return the primary function binding."""
        return self._primary_binding

    @classmethod
    def _generate_id(cls, outputs: abc.Sequence[feature_module.Feature], function_id: str) -> str:
        """Create an ID from its function, outputs, and short hash."""
        output_ids = cls._output_ids(outputs)
        output_id = output_ids[0] if len(output_ids) == 1 else f"features{len(output_ids)}"
        prefix = f"op-{function_id}-{output_id}-"
        digest = hashlib.sha256(prefix.encode("utf-8")).hexdigest()[:8]
        return f"{prefix}{digest}"

    @property
    def output_ids(self) -> list[str]:
        """Return the declared output feature IDs in order."""
        return self._output_ids(self.outputs)

    @classmethod
    def _output_ids(cls, outputs: abc.Sequence[feature_module.Feature]) -> list[str]:
        """Validate and normalize output feature IDs."""
        identifiers = []
        for output in outputs:
            if not isinstance(output, feature_module.Feature):
                raise TypeError("Operator outputs must contain Features")
            identifiers.append(cls._validate_feature_id(output.id))
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Operator output feature IDs must not repeat")
        return identifiers

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
    def _validate_feature_id(identifier: str | None) -> str:
        """Reject empty, nested, or current-feature selectors as feature IDs."""
        if (
            not isinstance(identifier, str)
            or not identifier
            or "." in identifier
            or identifier == selectors.CURRENT_ID
        ):
            raise ValueError(f"Invalid operator feature ID: {identifier!r}")
        return identifier

    def __post_init__(self) -> None:
        """Validate the declaration and merge argument-level row-context annotations."""
        object.__setattr__(
            self,
            "row_context",
            row_context_module._context(self._primary.arguments, self.row_context),
        )

    @property
    def reference(self) -> ref.FunctionReference:
        """Return the normalized entrypoint without importing string references."""
        return self._primary.reference

    @property
    def catalog_id(self) -> str:
        """Return the function-derived catalog identifier."""
        return self.reference.name

    def bound_arguments(self) -> dict[str, typing.Any]:
        """Return a copy of arguments, validating names for in-process callables.

        Entrypoint strings are not imported during authoring; signature validation
        for those functions is deferred until compilation.
        """
        return self._primary.bound_arguments()

    def to_model(self) -> spec_model.Operator:
        """Convert this declaration to its canonical document model."""
        compute = self._primary.to_model()
        merge = self.merge.to_model() if self.merge is not None else None
        if self.inputs is None:
            output_ids = set(self.output_ids)
            inferred = list(compute.inferred_feature_inputs)
            if merge is not None:
                inferred.extend(merge.inferred_feature_inputs)
            input_ids = [name for name in dict.fromkeys(inferred) if name not in output_ids]
        else:
            input_ids = self._input_ids()
        return spec_model.Operator(
            id=self.id,
            compute=compute,
            merge=merge,
            interface=spec_model.Interface(
                inputs=[f"{selectors.FEATURE_PREFIX}{name}" for name in input_ids],
                outputs=[f"{selectors.FEATURE_PREFIX}{name}" for name in self.output_ids],
            ),
            row_context=self.row_context,
        )

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Build the reusable function contract declared by this operator."""
        bindings: list[tuple[str, Bind]] = [(self._primary_role, self._primary)]
        if self.merge is not None:
            bindings.append(("merge", self.merge))
        catalogs = []
        for role, binding in bindings:
            template = binding.to_function_template(row_context=self.row_context)
            dataframe_count = sum(
                arg_types.is_dataframe(argument.type) for argument in template.args.values()
            )
            if role == "read":
                if dataframe_count != 0:
                    raise ValueError("Read binding must not accept dataframe inputs")
                if template.returns != "dataframe":
                    raise ValueError("Read binding must return a dataframe")
            elif role == "write":
                if dataframe_count != 1:
                    raise ValueError("Write binding must accept exactly one dataframe input")
                if template.returns != "none":
                    raise ValueError("Write binding must return no result")
            if (role in {"compute", "stage"} and dataframe_count > 1) or (
                role == "merge" and dataframe_count != 2
            ):
                raise ValueError(
                    f"Operator {self.id} {role} binding has invalid dataframe arity: "
                    f"{dataframe_count}"
                )
            if role == "merge" and template.returns != "dataframe":
                raise ValueError("Merge binding must return a dataframe")
            if role == "stage" and template.returns != "dataframe":
                raise ValueError("A stage binding must return a dataframe")
            catalogs.append(spec_model.FunctionCatalog(root={template.id: template}))
        return spec_model.FunctionCatalog.merge(catalogs)
