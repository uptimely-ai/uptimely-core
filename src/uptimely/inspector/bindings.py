"""Inspect callable implementations bound to a Spec."""

from __future__ import annotations

import collections.abc
import graphlib
import inspect
import logging
import types
import typing

from uptimely.codebase.python import codebase, entrypoint
from uptimely.spec import arg_types
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)

_KNOWN_ANNOTATION_NAMES = frozenset(
    {
        "DataFrame",
        "LazyFrame",
        "None",
        "bool",
        "bytes",
        "dict",
        "float",
        "int",
        "list",
        "set",
        "str",
        "tuple",
    }
)


class BindingInspection:
    """Compare one Spec binding with its inspected Python implementation."""

    INSPECTION_DEPENDENCIES: dict[str, tuple[str, ...]] = {
        "inspect_declared_arguments": (),
        "inspect_keyword_arguments": ("inspect_declared_arguments",),
        "inspect_argument_annotations": ("inspect_keyword_arguments",),
        "inspect_required_parameters": ("inspect_argument_annotations",),
        "inspect_dataframe_contract": ("inspect_required_parameters",),
        "inspect_return_annotation": ("inspect_dataframe_contract",),
    }

    def __init__(
        self,
        function: spec_model.FunctionTemplate,
        signature: entrypoint.Signature,
    ) -> None:
        """Initialize binding inspection with its complete semantic inputs.

        Args:
            function: The declared function contract.
            signature: The inspected implementation signature.
        """
        self.function = function
        self.signature = signature

    @classmethod
    def inspect_spec(
        cls,
        spec_definition: spec_model.Spec
        | collections.abc.Mapping[str, spec_model.FunctionTemplate],
        entrypoints: collections.abc.Mapping[str, entrypoint.Entrypoint] | None = None,
    ) -> dict[str, entrypoint.Signature]:
        """Inspect every enabled function bound by the Spec."""
        if isinstance(spec_definition, collections.abc.Mapping):
            selected_functions = dict(spec_definition)
        else:
            selected_functions = {}
            for operator in spec_definition.operators:
                for binding in operator.bindings.values():
                    function = spec_definition.functions.get(binding.function)
                    if function is not None:
                        selected_functions.setdefault(function.id, function)

        if entrypoints is None:
            locations = dict.fromkeys(
                function.entrypoint
                for function in selected_functions.values()
                if function.entrypoint
            )
            logger.debug("Parse %d unique entrypoints", len(locations))
            python_codebase = codebase.Codebase.from_locations(
                locations, entrypoint_type=entrypoint.Entrypoint
            )
            entrypoints = python_codebase.entrypoints_index

        enabled_count = sum(function.validate_signature for function in selected_functions.values())
        disabled_count = sum(
            not function.validate_signature for function in selected_functions.values()
        )
        logger.debug(
            "Inspect callable signatures for %d functions; skip %d disabled functions",
            enabled_count,
            disabled_count,
        )

        signatures: dict[str, entrypoint.Signature] = {}
        inspected: dict[str, entrypoint.Signature] = {}
        for function_id, function in selected_functions.items():
            if not function.validate_signature or not function.entrypoint:
                continue
            signature = inspected.get(function.entrypoint)
            if signature is None:
                signature = entrypoints[function.entrypoint].read_signature()
                inspected[function.entrypoint] = signature
            cls(function, signature).inspect()
            signatures[function_id] = signature
        return signatures

    def inspect(self) -> None:
        """Run all binding inspections in prerequisite order.

        Raises:
            ValueError: The implementation violates the binding contract.
            graphlib.CycleError: Inspection dependencies contain a cycle.
        """
        ordered = tuple(graphlib.TopologicalSorter(self.INSPECTION_DEPENDENCIES).static_order())
        for inspection in ordered:
            getattr(self, inspection)()

    def inspect_declared_arguments(self) -> None:
        """Require each declared argument to be accepted by the implementation."""
        for argument_name in self.function.args:
            if not argument_name or not argument_name.isidentifier():
                raise errors.SpecError(
                    f"Invalid argument name: {argument_name!r}",
                    code="invalid_implementation_signature",
                    path=("functions", self.function.id, "args"),
                )
            if argument_name not in self.signature.parameters and not self.signature.accepts_kwargs:
                raise errors.SpecError(
                    f"Implementation for function {self.function.id} does not accept declared "
                    f"argument {argument_name!r} as a keyword",
                    code="invalid_implementation_signature",
                    path=("functions", self.function.id, "args", argument_name),
                )

    def inspect_keyword_arguments(self) -> None:
        """Require declared arguments to be passable as keywords."""
        for argument_name in self.function.args:
            parameter = self.signature.parameters.get(argument_name)
            if parameter is not None and (
                parameter.kind is inspect.Parameter.POSITIONAL_ONLY
                or (
                    parameter.kind is inspect.Parameter.VAR_POSITIONAL
                    and not self.signature.accepts_kwargs
                )
            ):
                raise errors.SpecError(
                    f"Implementation parameter {argument_name!r} is positional-only and "
                    "cannot be passed as a keyword",
                    code="invalid_implementation_signature",
                    path=("functions", self.function.id, "args", argument_name),
                )

    def inspect_argument_annotations(self) -> None:
        """Require annotated parameters to accept their declared argument types."""
        for argument_name, argument in self.function.args.items():
            parameter = self.signature.parameters.get(argument_name)
            if parameter is None:
                continue
            if parameter.annotation is inspect.Parameter.empty:
                continue
            if not _supports_argument_type(parameter.annotation, argument.type):
                raise errors.SpecError(
                    f"Implementation parameter {argument_name!r} is annotated as "
                    f"{entrypoint.TypeAnnotation.name(parameter.annotation)}, but the function "
                    f"declares argument type {argument.type}",
                    code="invalid_implementation_signature",
                    path=("functions", self.function.id, "args", argument_name),
                )

    def inspect_required_parameters(self) -> None:
        """Reject required implementation parameters absent from the declaration."""
        for parameter_name in self.signature.required_parameters:
            if parameter_name not in self.function.args:
                raise errors.SpecError(
                    f"Implementation for function {self.function.id} requires undeclared "
                    f"parameter {parameter_name!r}",
                    code="invalid_implementation_signature",
                    path=("functions", self.function.id, "args"),
                )

    def inspect_dataframe_contract(self) -> None:
        """Reject declarations with too many dataframe arguments."""
        dataframe_inputs = sum(
            arg_types.is_dataframe(argument.type) for argument in self.function.args.values()
        )
        if dataframe_inputs > 2:
            raise errors.SpecError(
                "Callable contracts support at most two dataframe argument slots",
                code="invalid_implementation_signature",
                path=("functions", self.function.id, "args"),
            )

    def inspect_return_annotation(self) -> None:
        """Reject known Python return annotations that contradict the function contract."""
        function = self.function
        annotation = self.signature.return_annotation
        returns = function.returns
        if returns == "any":
            return
        if annotation is inspect.Signature.empty:
            return

        members = _annotation_names(annotation)
        contradictory = (
            members & (_KNOWN_ANNOTATION_NAMES - {"None"})
            if returns == "none"
            else members & (_KNOWN_ANNOTATION_NAMES - {"DataFrame", "LazyFrame"})
        )
        if contradictory:
            expected = "None" if returns == "none" else "DataFrame or LazyFrame"
            raise errors.SpecError(
                f"Function {function.id} declares returns={returns}, but its Python "
                f"return annotation is {entrypoint.TypeAnnotation.name(annotation)}; "
                f"expected {expected}",
                code="invalid_implementation_signature",
                path=("functions", function.id, "returns"),
            )


def _annotation_names(annotation: object) -> set[str]:
    """Return supported leaf names for a resolved or string annotation."""
    if isinstance(annotation, str):
        return {part.strip().rsplit(".", 1)[-1] for part in annotation.split("|")}
    origin = typing.get_origin(annotation)
    if origin is typing.Annotated:
        return _annotation_names(typing.get_args(annotation)[0])
    if origin in (typing.Union, types.UnionType):
        return set().union(*(_annotation_names(member) for member in typing.get_args(annotation)))
    if origin is typing.Literal:
        return {type(value).__name__ for value in typing.get_args(annotation)}
    if annotation is None or annotation is type(None):
        return {"None"}
    if annotation is typing.Any or annotation is object:
        return {entrypoint.TypeAnnotation.name(annotation)}
    if origin is not None:
        return {entrypoint.TypeAnnotation.name(origin).rsplit(".", 1)[-1]}
    return {entrypoint.TypeAnnotation.name(annotation).rsplit(".", 1)[-1]}


def _supports_argument_type(annotation: object, declared_type: str) -> bool:
    """Return whether a supported annotation accepts the declared argument type."""
    if annotation in (typing.Any, object):
        return True
    if declared_type in {arg_types.DATAFRAME, arg_types.OPTIONAL_DATAFRAME}:
        names = _annotation_names(annotation)
        dataframe_names = {"DataFrame", "LazyFrame"}
        accepts_dataframe = bool(names & dataframe_names) or not names & _KNOWN_ANNOTATION_NAMES
        accepts_none = bool(names & {"None", "NoneType"})
        return accepts_dataframe and (declared_type == arg_types.DATAFRAME or accepts_none)
    origin = typing.get_origin(annotation)
    if origin is typing.Annotated:
        return _supports_argument_type(typing.get_args(annotation)[0], declared_type)
    if origin in (typing.Union, types.UnionType):
        return all(
            _supports_argument_type(member, declared_type) for member in typing.get_args(annotation)
        )
    if origin is typing.Literal:
        return all(
            _supports_argument_type(type(type_member), declared_type)
            for type_member in typing.get_args(annotation)
        )

    if declared_type == arg_types.DATAFRAME:
        return entrypoint.TypeAnnotation.name(annotation).rsplit(".", 1)[-1] in {
            "DataFrame",
            "LazyFrame",
        } or entrypoint.TypeAnnotation.name(annotation).rsplit(".", 1)[-1] not in (
            _KNOWN_ANNOTATION_NAMES
        )

    atomic_types: dict[str, type[object]] = {
        arg_types.STRING: str,
        arg_types.INTEGER: int,
        arg_types.FLOAT: float,
        arg_types.BOOLEAN: bool,
    }
    expected = atomic_types.get(declared_type)
    if expected is not None:
        if annotation is expected:
            return True
        return (
            entrypoint.TypeAnnotation.name(annotation).rsplit(".", 1)[-1]
            not in _KNOWN_ANNOTATION_NAMES
        )

    array_item = arg_types.array_item_type(declared_type)
    if array_item is not None:
        array_origins = {list, tuple, collections.abc.Sequence}
        if origin is None:
            name = entrypoint.TypeAnnotation.name(annotation).rsplit(".", 1)[-1]
            return annotation in array_origins or name not in _KNOWN_ANNOTATION_NAMES
        if origin not in array_origins:
            name = entrypoint.TypeAnnotation.name(origin).rsplit(".", 1)[-1]
            return name not in _KNOWN_ANNOTATION_NAMES
        arguments = typing.get_args(annotation)
        members = [member for member in arguments if member is not Ellipsis]
        return not members or all(_supports_argument_type(member, array_item) for member in members)

    object_value = arg_types.object_value_type(declared_type)
    if object_value is not None:
        mapping_origins = {dict, collections.abc.Mapping}
        if origin is None:
            name = entrypoint.TypeAnnotation.name(annotation).rsplit(".", 1)[-1]
            return annotation in mapping_origins or name not in _KNOWN_ANNOTATION_NAMES
        if origin not in mapping_origins:
            name = entrypoint.TypeAnnotation.name(origin).rsplit(".", 1)[-1]
            return name not in _KNOWN_ANNOTATION_NAMES
        arguments = typing.get_args(annotation)
        return (
            len(arguments) == 2
            and arguments[0] is str
            and _supports_argument_type(arguments[1], object_value)
        )

    return True
