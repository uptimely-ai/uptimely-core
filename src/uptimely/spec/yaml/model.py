"""Build Spec bindings and operators from compact YAML declarations."""

from __future__ import annotations

import typing

import pydantic

from uptimely.codebase.python import entrypoint
from uptimely.spec import arg_types, function_contracts
from uptimely.spec import model as spec_model
from uptimely.spec import row_context as row_context_module
from uptimely.spec.python import assembly, feature, merge, ref

_INPUT_PREFIX = "$input."
_OUTPUT_PREFIX = "$output."
_OPERATOR_FIELDS = frozenset(
    {"function", "input", "inputs", "outputs", "args", "merge", "row_context"}
)
_MERGE_FIELDS = frozenset({"function", "args"})


class _BindingDeclaration(pydantic.BaseModel):
    """Validated function and arguments fields shared by compact bindings."""

    model_config = pydantic.ConfigDict(extra="forbid", strict=True)

    function: str
    args: dict[str, typing.Any] = pydantic.Field(default_factory=dict)

    @pydantic.model_validator(mode="before")
    @classmethod
    def validate_declaration(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        if not isinstance(value.get("function"), str) or not value["function"]:
            raise ValueError("function must be an entrypoint or declared function ID")
        if "args" in value and not isinstance(value["args"], dict):
            raise ValueError("args must be a mapping")
        return value


class _MergeDeclaration(_BindingDeclaration):
    """Validated function binding used for an explicit merge."""

    @pydantic.model_validator(mode="before")
    @classmethod
    def validate_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            unknown = value.keys() - _MERGE_FIELDS
            if unknown:
                raise ValueError(f"Unknown merge fields: {', '.join(sorted(unknown))}")
        return value


class _CompactOperator(_BindingDeclaration):
    """Validated compact operator fields before Spec model construction."""

    input: str | None = None
    inputs: list[str] | None = None
    outputs: list[str] | None = None
    merge: typing.Literal["default"] | _MergeDeclaration | None = None
    row_context: row_context_module.RowContext | None = None

    @pydantic.model_validator(mode="before")
    @classmethod
    def validate_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            unknown = value.keys() - _OPERATOR_FIELDS
            if unknown:
                raise ValueError(f"Unknown operator fields: {', '.join(sorted(unknown))}")
        return value

    @pydantic.field_validator("input", mode="before")
    @classmethod
    def validate_input(cls, value: object) -> object:
        if not isinstance(value, str) or not value or "." in value:
            raise ValueError("input must be a profile ID or '@' for the current profile")
        return value

    @pydantic.field_validator("inputs", "outputs", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info: pydantic.ValidationInfo) -> object:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{info.field_name} must be a list of feature IDs")
        return value

    @pydantic.field_validator("merge", mode="before")
    @classmethod
    def validate_merge(cls, value: object) -> object:
        if value is None or value == "default" or isinstance(value, dict):
            return value
        raise ValueError("merge must be 'default' or a function binding")


class _Argument:
    """Translate YAML reference syntax into binding arguments."""

    def translate(self, value: typing.Any, dependencies: list[str]) -> typing.Any:
        """Convert nested argument values and track referenced input features."""
        if isinstance(value, dict):
            return self._mapping(value, dependencies)
        if isinstance(value, list):
            return [self.translate(item, dependencies) for item in value]
        if isinstance(value, str):
            return self._string(value, dependencies)
        return value

    def _mapping(
        self, value: dict[str, typing.Any], dependencies: list[str]
    ) -> dict[str, typing.Any]:
        result = {}
        for key, item in value.items():
            if key.startswith(_OUTPUT_PREFIX):
                raise ValueError(f"Output references cannot be mapping keys: {key!r}")
            if key.startswith(_INPUT_PREFIX):
                identifier = key.removeprefix(_INPUT_PREFIX)
                self._validate_feature_identifier(identifier, key)
                dependencies.append(identifier)
                key = identifier
            if key in result:
                raise ValueError(f"Duplicate argument key after resolving input reference: {key!r}")
            result[key] = self.translate(item, dependencies)
        return result

    def _string(self, value: str, dependencies: list[str]) -> typing.Any:
        for prefix, constructor in ((_INPUT_PREFIX, ref.input), (_OUTPUT_PREFIX, ref.output)):
            if value.startswith(prefix):
                identifier = value.removeprefix(prefix)
                self._validate_feature_identifier(identifier, value)
                if prefix == _INPUT_PREFIX:
                    dependencies.append(identifier)
                return constructor(identifier)
        if value.startswith("$operators.@.row_context."):
            attribute = value.removeprefix("$operators.@.row_context.")
            if attribute not in {"before", "after", "dimension"}:
                raise ValueError(f"Invalid row context reference {value!r}")
            return ref.row_context(attribute)
        argument = spec_model.BindingArgument(value)
        dependencies.extend(argument.inferred_feature_inputs)
        value_type = argument.selector_value_type
        if value_type in {arg_types.DATAFRAME, arg_types.array_of(arg_types.STRING)}:
            return ref.Reference(kind=value_type, value=value)
        return value

    @staticmethod
    def _validate_feature_identifier(identifier: str, reference: str) -> None:
        if not identifier or "." in identifier or identifier == "@":
            raise ValueError(f"Invalid feature reference {reference!r}")


class _FunctionBinding:
    """Resolve function declarations and bind explicit or inferred datasets."""

    def __init__(self, functions: spec_model.FunctionCatalog) -> None:
        self.functions = functions
        self.arguments = _Argument()

    def bind(
        self,
        declaration: _BindingDeclaration,
        dependencies: list[str],
        *,
        infer_dataframe: bool = False,
    ) -> tuple[assembly.Bind, str | None]:
        """Build a binding and optionally infer its dataframe argument."""
        reference = self._function(declaration.function)
        arguments = self.arguments.translate(declaration.args, dependencies)
        inferred_argument = None
        if isinstance(declaration, _CompactOperator) and declaration.input is not None:
            profile = declaration.input
            argument = self._dataframe_argument(reference)
            if argument in arguments:
                raise ValueError(f"input and args.{argument} both bind the dataframe")
            arguments = {argument: ref.dataset(None if profile == "@" else profile), **arguments}
        elif infer_dataframe:
            candidates = self._dataframe_arguments(reference)
            missing = [name for name in candidates if name not in arguments]
            if missing:
                argument = self._dataframe_argument(reference)
                arguments = {argument: ref.dataset(), **arguments}
                inferred_argument = argument
        return assembly.Bind(reference, **arguments), inferred_argument

    def _function(self, name: str) -> ref.FunctionReference:
        declared = self.functions.get(name)
        if declared is not None:
            return ref.function(
                declared.entrypoint,
                returns=declared.returns,
                args={key: argument.type for key, argument in declared.args.items()},
                category=declared.category,
                validate_signature=declared.validate_signature,
                description=declared.description,
            )
        return ref.function(entrypoint.Entrypoint(name).load())

    @staticmethod
    def _dataframe_arguments(reference: ref.FunctionReference) -> list[str]:
        if reference.args is not None:
            return [name for name, kind in reference.args.items() if arg_types.is_dataframe(kind)]
        if reference.signature is not None:
            candidates = []
            for name, parameter in reference.signature.parameters.items():
                names = function_contracts.annotation_names(parameter.annotation)
                if names and names <= {"DataFrame", "LazyFrame", "None"} and names != {"None"}:
                    candidates.append(name)
            return candidates
        return []

    @classmethod
    def _dataframe_argument(cls, reference: ref.FunctionReference) -> str:
        candidates = cls._dataframe_arguments(reference)
        if len(candidates) != 1:
            raise ValueError(
                f"Cannot determine the single dataframe argument for {reference.entrypoint!r}. "
                "Bind the dataframe explicitly in args."
            )
        return candidates[0]


class _OperatorBuilder:
    """Build operators and register their inferred function contracts."""

    def __init__(self, explicit_functions: spec_model.FunctionCatalog) -> None:
        self.explicit_functions = explicit_functions
        self.functions = explicit_functions
        self.bindings = _FunctionBinding(explicit_functions)

    def author(
        self, identifier: str, declaration: dict[str, typing.Any]
    ) -> tuple[assembly.Operator, spec_model.Operator, str | None]:
        """Build an operator and add its inferred function contracts.

        Args:
            identifier: Operator identifier within its profile.
            declaration: Compact YAML operator declaration.

        Returns:
            The declared operator, its document model, and any inferred dataframe argument name.

        Raises:
            ValueError: A declaration or function contract is invalid.
        """
        declaration = _CompactOperator.model_validate(declaration)
        operator, inferred_argument = self._operator(identifier, declaration)
        operator_model = operator.to_model()
        catalog = operator.function_catalog()
        resolved = self._function_templates(operator, declaration, operator_model, catalog)
        self.functions = spec_model.FunctionCatalog.merge(
            [self.functions, spec_model.FunctionCatalog(root=resolved)]
        )
        return operator, operator_model, inferred_argument

    def _function_templates(
        self,
        operator: assembly.Operator,
        declaration: _CompactOperator,
        operator_model: spec_model.Operator,
        catalog: spec_model.FunctionCatalog,
    ) -> dict[str, spec_model.FunctionTemplate]:
        resolved = {}
        function_bindings = [(operator.compute, declaration.function, operator_model.compute)]
        if operator.merge is not None and isinstance(declaration.merge, _MergeDeclaration):
            function_bindings.append(
                (operator.merge, declaration.merge.function, operator_model.merge)
            )
        for binding, authored_id, binding_model in function_bindings:
            function_id = self._function_id(authored_id, binding.reference.name)
            resolved[function_id] = self._template(function_id, binding.reference.name, catalog)
            if binding_model is not None:
                binding_model.function = function_id
        if operator.merge is not None and declaration.merge == "default":
            reference_name = operator.merge.reference.name
            template = catalog.root[reference_name]
            resolved[template.id] = self._template(template.id, reference_name, catalog)
        return resolved

    def _function_id(self, authored_id: str, reference_name: str) -> str:
        return authored_id if authored_id in self.explicit_functions else reference_name

    def _template(
        self, function_id: str, reference_name: str, catalog: spec_model.FunctionCatalog
    ) -> spec_model.FunctionTemplate:
        template = catalog.root[reference_name]
        existing = self.explicit_functions.get(function_id)
        if existing is not None and existing.entrypoint != template.entrypoint:
            raise ValueError(f"Conflicting function definition for '{function_id}'")
        return existing if existing is not None else template

    def _operator(
        self, identifier: str, declaration: _CompactOperator
    ) -> tuple[assembly.Operator, str | None]:
        merge_binding = self._merge(declaration.merge)
        dependencies: list[str] = []
        compute, inferred_argument = self.bindings.bind(
            declaration, dependencies, infer_dataframe=True
        )
        outputs = (
            [feature.Feature(id=value) for value in declaration.outputs]
            if declaration.outputs is not None
            else None
        )
        inputs = declaration.inputs
        operator = assembly.Operator(
            id=identifier,
            compute=compute,
            inputs=inputs,
            outputs=outputs,
            merge=merge_binding,
            row_context=declaration.row_context,
        )
        if inputs is None and dependencies:
            inferred_inputs = self._inferred_inputs(dependencies, operator.output_ids)
            operator = assembly.Operator(
                id=identifier,
                compute=compute,
                inputs=inferred_inputs,
                outputs=outputs,
                merge=merge_binding,
                row_context=declaration.row_context,
            )
        return operator, inferred_argument

    @staticmethod
    def _inferred_inputs(dependencies: list[str], output_ids: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in dependencies if value not in output_ids))

    def _merge(
        self, declaration: typing.Literal["default"] | _MergeDeclaration | None
    ) -> assembly.Bind | None:
        if declaration == "default":
            return merge.default()
        if declaration is None:
            return None
        binding, _ = self.bindings.bind(declaration, [])
        return binding
