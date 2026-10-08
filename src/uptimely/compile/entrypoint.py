"""Load Python function entrypoints and read their annotated signatures."""

import dataclasses
import importlib
import inspect
import sys
import types
import typing
from pathlib import Path


@dataclasses.dataclass
class FunctionSignature:
    """Annotated input and output types of a Python function."""

    args: dict[str, str] = dataclasses.field(default_factory=dict)
    returns: str | None = None


def load_callable(entrypoint: str, root: Path | None = None) -> typing.Callable:
    """Import the callable addressed by an entrypoint.

    Args:
        entrypoint: ``'module.path:function'`` or ``'path/to/module.py:function'``.
        root: Directory added to ``sys.path`` so the module becomes importable.

    Returns:
        The imported callable.

    Raises:
        ValueError: If the entrypoint does not contain a function name.
        ImportError: If the module cannot be imported.
        AttributeError: If the module has no such function.
    """
    if ":" not in entrypoint:
        raise ValueError(
            f"Invalid entrypoint: {entrypoint}. "
            "Expected 'module.path:function' or 'path/to/module.py:function'"
        )

    if root is not None and str(root) not in sys.path:
        sys.path.insert(0, str(root))

    module_path, function_name = entrypoint.rsplit(":", 1)
    if module_path.endswith(".py"):
        module_path = module_path[:-3]
    module_path = module_path.replace("/", ".")

    module = importlib.import_module(module_path)
    if not hasattr(module, function_name):
        raise AttributeError(f"Function {function_name} not found in module {module_path}")

    return getattr(module, function_name)


def read_signature(entrypoint: str, root: Path | None = None) -> FunctionSignature:
    """Read the annotated argument and return types of an entrypoint.

    Args:
        entrypoint: ``'module.path:function'`` or ``'path/to/module.py:function'``.
        root: Directory added to ``sys.path`` so the module becomes importable.

    Returns:
        The annotated signature; unannotated parameters are omitted.
    """
    func = load_callable(entrypoint, root)
    hints = typing.get_type_hints(func)
    parameters = inspect.signature(func).parameters

    return FunctionSignature(
        args={name: type_name(hints[name]) for name in parameters if name in hints},
        returns=type_name(hints["return"]) if "return" in hints else None,
    )


def type_name(annotation: object) -> str:
    """Return a readable name for a type annotation."""
    if annotation is None or annotation is type(None):
        return "None"

    if isinstance(annotation, (types.UnionType, type(int | str))):
        return " | ".join(type_name(arg) for arg in typing.get_args(annotation))

    origin = typing.get_origin(annotation)
    if origin is not None:
        arguments = ", ".join(type_name(arg) for arg in typing.get_args(annotation))
        return f"{type_name(origin)}[{arguments}]" if arguments else type_name(origin)

    return getattr(annotation, "__name__", str(annotation))
