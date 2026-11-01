"""Validate compiler inputs and callable signatures against spec contracts."""

from __future__ import annotations

import collections.abc
import graphlib
import inspect
import types
import typing

from uptimely import entrypoint
from uptimely.spec import arg_types, functions
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

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


class CallableValidationContext(typing.NamedTuple):
    """Function declaration and implementation signature being checked."""

    function: spec_model.FunctionTemplate
    signature: entrypoint.Signature


type Validator = collections.abc.Callable[[CallableValidationContext], None]


def validation_declared_arguments(context: CallableValidationContext) -> None:
    """Require each declared argument to be accepted by the implementation."""
    for argument_name in context.function.args:
        if (
            argument_name not in context.signature.parameters
            and not context.signature.accepts_kwargs
        ):
            raise errors.SpecError(
                f"Implementation for function {context.function.id} does not accept declared "
                f"argument {argument_name!r} as a keyword",
                code="invalid_implementation_signature",
                path=("functions", context.function.id, "args", argument_name),
            )


def validation_keyword_arguments(context: CallableValidationContext) -> None:
    """Require declared arguments to be passable as keywords."""
    for argument_name in context.function.args:
        parameter = context.signature.parameters.get(argument_name)
        if parameter is not None and parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
            raise errors.SpecError(
                f"Implementation parameter {argument_name!r} is positional-only and "
                "cannot be passed as a keyword",
                code="invalid_implementation_signature",
                path=("functions", context.function.id, "args", argument_name),
            )


def validation_argument_annotations(context: CallableValidationContext) -> None:
    """Require annotated parameters to accept their declared argument types."""
    for argument_name, argument in context.function.args.items():
        parameter = context.signature.parameters.get(argument_name)
        if (
            parameter is not None
            and parameter.annotation is not inspect.Parameter.empty
            and not _supports_argument_type(parameter.annotation, argument.type)
        ):
            raise errors.SpecError(
                f"Implementation parameter {argument_name!r} is annotated as "
                f"{entrypoint.TypeAnnotation.name(parameter.annotation)}, but the function "
                f"declares argument type {argument.type}",
                code="invalid_implementation_signature",
                path=("functions", context.function.id, "args", argument_name),
            )


def validation_required_parameters(context: CallableValidationContext) -> None:
    """Reject required implementation parameters absent from the declaration."""
    for parameter_name in context.signature.required_parameters:
        if parameter_name not in context.function.args:
            raise errors.SpecError(
                f"Implementation for function {context.function.id} requires undeclared "
                f"parameter {parameter_name!r}",
                code="invalid_implementation_signature",
                path=("functions", context.function.id, "args"),
            )


def validation_return_annotation(context: CallableValidationContext) -> None:
    """Reject known Python return annotations that contradict the function contract."""
    function = context.function
    annotation = context.signature.return_annotation
    returns = functions.FUNCTION_KINDS[function.kind].returns
    if returns == "any" or annotation is inspect.Signature.empty:
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


VALIDATION_DEPENDENCIES: dict[Validator, tuple[Validator, ...]] = {
    validation_declared_arguments: (),
    validation_keyword_arguments: (validation_declared_arguments,),
    validation_argument_annotations: (validation_keyword_arguments,),
    validation_required_parameters: (validation_argument_annotations,),
    validation_return_annotation: (validation_required_parameters,),
}


def validation_callable_signature(context: CallableValidationContext) -> None:
    """Run callable signature checks in prerequisite order.

    Args:
        context: The function declaration and implementation signature to check.

    Raises:
        ValueError: The implementation violates its declared function contract.
        graphlib.CycleError: Validator dependencies contain a configuration cycle.
    """
    ordered = tuple(graphlib.TopologicalSorter(VALIDATION_DEPENDENCIES).static_order())
    for validate in ordered:
        validate(context)


def validation_feature_selection(features: collections.abc.Collection[str] | None) -> None:
    """Reject strings where a collection of feature identifiers is expected."""
    if isinstance(features, str):
        raise ValueError("features must be a collection of feature identifiers")


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
    origin = typing.get_origin(annotation)
    if origin is typing.Annotated:
        return _supports_argument_type(typing.get_args(annotation)[0], declared_type)
    if origin in (typing.Union, types.UnionType):
        return all(
            _supports_argument_type(member, declared_type) for member in typing.get_args(annotation)
        )
    if origin is typing.Literal:
        return all(
            _supports_argument_type(type(value), declared_type)
            for value in typing.get_args(annotation)
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
