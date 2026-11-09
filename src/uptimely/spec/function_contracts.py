"""Reusable callable contracts independent of operator behavior."""

from __future__ import annotations

import ast
import inspect
import types
import typing

type ReturnRole = typing.Literal["dataframe", "none", "any"]
RETURN_ROLES: typing.Final = frozenset({"dataframe", "none", "any"})
_FRAME_NAMES = frozenset({"DataFrame", "LazyFrame"})
_OPAQUE_NAMES = frozenset({"Any", "object"})
_KNOWN_NAMES = _FRAME_NAMES | frozenset(
    {
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


def _names(node: ast.expr) -> set[str] | None:
    """Resolve annotation leaves without evaluating annotations or importing code."""
    if isinstance(node, ast.Constant):
        if node.value is None:
            return {"None"}
        if isinstance(node.value, str):
            return annotation_names(node.value)
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Attribute):
        return {node.attr}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left, right = _names(node.left), _names(node.right)
        return left | right if left is not None and right is not None else None
    if isinstance(node, ast.Subscript):
        name = _names(node.value)
        if name == {"Annotated"}:
            first = node.slice.elts[0] if isinstance(node.slice, ast.Tuple) else node.slice
            return _names(first)
        if name in ({"Union"}, {"Optional"}):
            nodes = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            members = [_names(member) for member in nodes]
            if any(member is None for member in members):
                return None
            result = set().union(*(member for member in members if member is not None))
            return result | {"None"} if name == {"Optional"} else result
        return name
    return None


def annotation_names(annotation: object) -> set[str] | None:
    """Return syntactic annotation leaves, or None for an unsupported expression."""
    if annotation is inspect.Signature.empty:
        return None
    if annotation is None or annotation is type(None):
        return {"None"}
    if isinstance(annotation, typing.ForwardRef):
        annotation = annotation.__forward_arg__
    if not isinstance(annotation, str):
        origin = typing.get_origin(annotation)
        if origin is typing.Annotated:
            return annotation_names(typing.get_args(annotation)[0])
        if origin in (typing.Union, types.UnionType):
            members = [annotation_names(member) for member in typing.get_args(annotation)]
            if any(member is None for member in members):
                return None
            return set().union(*(member for member in members if member is not None))
        return {getattr(origin or annotation, "__name__", str(origin or annotation))}
    try:
        return _names(ast.parse(annotation, mode="eval").body)
    except SyntaxError:
        return None


def return_role(annotation: object) -> ReturnRole | None:
    """Infer a dataframe or no-result role only from an unambiguous annotation."""
    names = annotation_names(annotation)
    if names and names <= _FRAME_NAMES:
        return "dataframe"
    if names == {"None"}:
        return "none"
    return None


def check_return_annotation(role: ReturnRole, annotation: object) -> None:
    """Reject annotations that exclude or contradict the declared return role.

    An explicit ``any`` contract ignores the result. Opaque annotations may
    describe either result role and therefore need explicit metadata.
    """
    names = annotation_names(annotation)
    if role == "any" or names is None:
        return
    allowed = _FRAME_NAMES if role == "dataframe" else frozenset({"None"})
    if (names & _KNOWN_NAMES) - allowed - _OPAQUE_NAMES:
        raise ValueError(f"Declared returns={role} contradicts return annotation {annotation}")


def validate_metadata(returns: ReturnRole | None, args: dict[str, str] | None) -> None:
    """Validate explicit return and argument metadata at the authoring boundary."""
    if returns is not None and returns not in RETURN_ROLES:
        raise ValueError(f"Unsupported return contract: {returns}")
    if args is not None and (
        not isinstance(args, dict)
        or any(not isinstance(name, str) or not name.isidentifier() for name in args)
        or any(not isinstance(value, str) or not value for value in args.values())
    ):
        raise TypeError("Function args must map argument names to nonempty type strings")
