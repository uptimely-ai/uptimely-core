"""Declarative analytical work and its data and execution requirements."""

from __future__ import annotations

import dataclasses
import hashlib
import typing
from collections import abc

from uptimely.spec import arg_types, function_contracts, operator_bindings, selectors
from uptimely.spec import model as spec_model
from uptimely.spec import (
    row_context as row_context_values,
)

from . import binding_conversion, feature, ref
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

        Entrypoint strings and references are not imported during authoring.
        Implementation signature validation is deferred to binding inspection.
        """
        reference = self.reference
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
    """Declare an operator with a compute binding and an optional merge.

    Args:
        id: Optional non-empty identifier, unique within its profile. When omitted,
            the ID is generated from the primary function and outputs. An operator
            referenced as a profile's seed must have an explicitly supplied ID.
        inputs: Feature dependencies. Inputs are inferred from binding arguments
            when omitted.
        outputs: Explicit feature declarations produced by the operator. When
            omitted, output references in the compute and merge bindings are used.
        row_context: Operator-specific observation requirements, merged with
            argument annotations.
        compute: Function accepting zero or one dataframe. A dataframe result
            is the complete target without a merge, or a fragment with a merge.
            Non-dataframe results are not added to the target.
        merge: Function combining the compute fragment with the target.
    """

    id: str
    inputs: list[feature.Feature | ref.Reference | str] | None
    outputs: list[feature.Feature] | None
    row_context: (
        row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
    ) = None
    compute: Bind
    merge: Bind | None = None
    _id_explicit: bool = dataclasses.field(init=False, repr=False, compare=False)

    def __init__(
        self,
        *,
        compute: Bind,
        id: str | None = None,
        inputs: abc.Sequence[feature.Feature | ref.Reference | str] | None = None,
        outputs: abc.Sequence[feature.Feature] | None = None,
        row_context: (
            row_context_values.RowContext | row_context_module.RowContextBinding[typing.Any] | None
        ) = None,
        merge: Bind | None = None,
    ) -> None:
        """Create an operator, deriving its identifier when one is not supplied."""
        if not isinstance(compute, Bind):
            raise TypeError("Operator compute must be a Bind")
        if merge is not None and not isinstance(merge, Bind):
            raise TypeError("Operator merge must be a Bind or None")
        if inputs is not None and (
            not isinstance(inputs, abc.Sequence) or isinstance(inputs, (str, bytes))
        ):
            raise TypeError("Operator inputs must be a sequence of feature references")
        if outputs is not None and (
            not isinstance(outputs, abc.Sequence) or isinstance(outputs, (str, bytes))
        ):
            raise TypeError("Operator outputs must be a sequence of Features")
        id_explicit = id is not None
        if id is None:
            resolved_output_ids = (
                type(self)._output_ids(outputs)
                if outputs is not None
                else type(self)._inferred_output_ids(compute, merge)
            )
            id = type(self)._generate_id(
                resolved_output_ids,
                compute.reference.name,
            )
        if not isinstance(id, str) or not id.strip():
            raise ValueError("Operator requires a non-empty id")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "inputs", list(inputs) if inputs is not None else None)
        object.__setattr__(self, "outputs", list(outputs) if outputs is not None else None)
        object.__setattr__(self, "row_context", row_context)
        object.__setattr__(self, "compute", compute)
        object.__setattr__(self, "merge", merge)
        object.__setattr__(self, "_id_explicit", id_explicit)
        self._input_ids()
        _ = self.output_ids
        self.__post_init__()

    @classmethod
    def _generate_id(
        cls,
        output_ids: abc.Sequence[str],
        function_id: str,
    ) -> str:
        """Create an ID from its function, resolved output IDs, and short hash."""
        output_id = output_ids[0] if len(output_ids) == 1 else f"features{len(output_ids)}"
        prefix = f"op-{function_id}-{output_id}-"
        digest = hashlib.sha256(prefix.encode("utf-8")).hexdigest()[:8]
        return f"{prefix}{digest}"

    @property
    def output_ids(self) -> list[str]:
        """Return explicit or inferred output feature IDs in order."""
        if self.outputs is None:
            return self._inferred_output_ids(self.compute, self.merge)
        return self._output_ids(self.outputs)

    @property
    def input_ids(self) -> list[str]:
        """Return explicit or inferred input feature IDs in order."""
        if self.inputs is None:
            return self._inferred_input_ids(
                self.compute,
                self.merge,
                output_ids=self.output_ids,
            )
        return self._input_ids()

    @classmethod
    def _inferred_output_ids(cls, compute: Bind, merge: Bind | None) -> list[str]:
        """Infer output feature IDs from output references in bindings."""
        compute_model = compute.to_model()
        identifiers = list(compute_model.inferred_feature_outputs)
        if merge is not None:
            identifiers.extend(merge.to_model().inferred_feature_outputs)
        return list(dict.fromkeys(identifiers))

    @classmethod
    def _inferred_input_ids(
        cls,
        compute: Bind,
        merge: Bind | None,
        output_ids: abc.Sequence[str] = (),
    ) -> list[str]:
        """Infer input feature IDs from input references in bindings."""
        compute_model = compute.to_model()
        identifiers = list(compute_model.inferred_feature_inputs)
        if merge is not None:
            identifiers.extend(merge.to_model().inferred_feature_inputs)
        excluded = set(output_ids)
        return [
            identifier for identifier in dict.fromkeys(identifiers) if identifier not in excluded
        ]

    @classmethod
    def _output_ids(cls, outputs: abc.Sequence[feature.Feature]) -> list[str]:
        """Validate and normalize output feature IDs."""
        identifiers = []
        for output in outputs:
            if not isinstance(output, feature.Feature):
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
    def _feature_id(cls, value: feature.Feature | ref.Reference | str) -> str:
        """Normalize and validate a feature identifier or reference."""
        if isinstance(value, feature.Feature):
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
            is_workflow=(
                self.reference.returns in {"none", "any"}
                and not compute.profile_dataframe_references
                and not any(
                    arg_types.is_dataframe(value) for value in (self.reference.args or {}).values()
                )
            ),
            merge=merge,
            interface=spec_model.Interface(
                inputs=[f"{selectors.FEATURE_PREFIX}{name}" for name in self.input_ids],
                outputs=[f"{selectors.FEATURE_PREFIX}{name}" for name in self.output_ids],
            ),
            row_context=self.row_context,
        )

    def function_catalog(self) -> spec_model.FunctionCatalog:
        """Build the reusable function contract declared by this operator."""
        bindings: list[tuple[operator_bindings.BindingKind, Bind]] = [
            (operator_bindings.COMPUTE, self.compute)
        ]
        if self.merge is not None:
            bindings.append((operator_bindings.MERGE, self.merge))
        catalogs = []
        for role, binding in bindings:
            template = binding.to_function_template(row_context=self.row_context)
            dataframe_count = template.dataframe_argument_count
            if dataframe_count not in operator_bindings.OPERATOR_BINDINGS[role].dataframe_inputs:
                raise ValueError(
                    f"Operator {self.id} {role} binding has invalid dataframe arity: "
                    f"{dataframe_count}"
                )
            if (
                role == operator_bindings.MERGE or self.merge is not None
            ) and template.returns != arg_types.DATAFRAME:
                raise ValueError(
                    f"Operator {self.id} {role} binding must return a dataframe when merging"
                )
            catalogs.append(spec_model.FunctionCatalog(root={template.id: template}))
        return spec_model.FunctionCatalog.merge(catalogs)
