"""Inspect implementation entrypoints and validate compile-time contracts."""

from __future__ import annotations

import collections.abc
import inspect
import types
import typing

from uptimely import entrypoint, spec
from uptimely.spec import arg_types, functions
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

from . import graph as invocation_graph

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


def read_entrypoints(
    spec_definition: spec.Spec,
    graph: invocation_graph.InvocationGraph,
) -> dict[str, entrypoint.Entrypoint]:
    """Parse each distinct implementation location once."""
    entrypoints: dict[str, entrypoint.Entrypoint] = {}
    for node in graph.invocations:
        function = spec_definition.functions[node.function_id]
        if function.entrypoint in entrypoints:
            continue
        try:
            entrypoints[function.entrypoint] = entrypoint.Entrypoint(function.entrypoint)
        except ValueError as error:
            raise ValueError(
                f"Invalid entrypoint for function {function.id} "
                f"used by action {node.mapping_id}: {error}"
            ) from error
    return entrypoints


def read_packages(
    entrypoints: dict[str, entrypoint.Entrypoint],
) -> dict[str, entrypoint.PackageProvenance]:
    """Read package provenance independently of signature validation."""
    packages: dict[str, entrypoint.PackageProvenance] = {}
    for location, implementation in entrypoints.items():
        try:
            packages[location] = implementation.module.package
        except (ImportError, ValueError) as error:
            raise ValueError(
                f"Could not read package provenance for entrypoint {location}: {error}"
            ) from error
    return packages


def read_signatures(
    spec_definition: spec.Spec,
    graph: invocation_graph.InvocationGraph,
    entrypoints: dict[str, entrypoint.Entrypoint],
) -> dict[str, entrypoint.Signature]:
    """Inspect enabled function declarations and validate implementation contracts."""
    signatures: dict[str, entrypoint.Signature] = {}
    signatures_by_function: dict[str, entrypoint.Signature] = {}
    for node in graph.invocations:
        function = spec_definition.functions.get(node.function_id)
        if function is None or not function.validate_signature:
            continue

        signature = signatures_by_function.get(function.id)
        if signature is None:
            implementation = entrypoints[function.entrypoint]
            try:
                signature = implementation.function.signature
                validate_callable_signature(function, signature)
            except errors.SpecError:
                raise
            except (ImportError, AttributeError, ValueError, TypeError, NameError) as error:
                raise ValueError(
                    f"Could not read signature of function {function.id} "
                    f"used by action {node.mapping_id} from entrypoint "
                    f"{function.entrypoint}; available build package: "
                    f"{implementation.module.package}: {error}"
                ) from error
            signatures_by_function[function.id] = signature
        signatures[node.node_id] = signature
    return signatures


def validate_return_annotation(function: spec_model.FunctionTemplate, annotation: object) -> None:
    """Reject known Python return annotations that contradict the function contract."""
    returns = functions.FUNCTION_KINDS[function.kind].returns
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


def validate_callable_signature(
    function: spec_model.FunctionTemplate, signature: entrypoint.Signature
) -> None:
    """Validate keyword-call shape and supported annotations against a declaration."""
    parameters = signature.parameters
    accepts_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )
    for argument_name, argument in function.args.items():
        parameter = parameters.get(argument_name)
        if parameter is None:
            if accepts_kwargs:
                continue
            raise errors.SpecError(
                f"Implementation for function {function.id} does not accept declared "
                f"argument {argument_name!r} as a keyword",
                code="invalid_implementation_signature",
                path=("functions", function.id, "args", argument_name),
            )
        if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
            raise errors.SpecError(
                f"Implementation parameter {argument_name!r} is positional-only and "
                "cannot be passed as a keyword",
                code="invalid_implementation_signature",
                path=("functions", function.id, "args", argument_name),
            )
        if parameter.annotation is not inspect.Parameter.empty and not _supports_argument_type(
            parameter.annotation, argument.type
        ):
            raise errors.SpecError(
                f"Implementation parameter {argument_name!r} is annotated as "
                f"{entrypoint.TypeAnnotation.name(parameter.annotation)}, but the function "
                f"declares argument type {argument.type}",
                code="invalid_implementation_signature",
                path=("functions", function.id, "args", argument_name),
            )

    for parameter_name, parameter in parameters.items():
        if parameter.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            continue
        if parameter.default is inspect.Parameter.empty and parameter_name not in function.args:
            raise errors.SpecError(
                f"Implementation for function {function.id} requires undeclared "
                f"parameter {parameter_name!r}",
                code="invalid_implementation_signature",
                path=("functions", function.id, "args"),
            )

    validate_return_annotation(function, signature.return_annotation)


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
