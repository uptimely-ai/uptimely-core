"""Function locations and callable metadata without eager module loading."""

from __future__ import annotations

import dataclasses
import inspect
from collections import abc

from uptimely import entrypoint as entrypoint_module
from uptimely.spec import function_kinds as functions

from . import functions as function_semantics

__all__ = ["FunctionReference", "function"]


@dataclasses.dataclass(frozen=True)
class FunctionReference:
    """A function location normalized without importing or executing its module."""

    module: str
    name: str
    kind: functions.FunctionKindId | None = None
    validate_signature: bool = True
    description: str | None = None
    category: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.module, str):
            raise TypeError("Function reference module must be a string")
        if not entrypoint_module.Module.is_valid_location(self.module):
            raise ValueError("Function reference module must be an importable dotted module name")
        if not isinstance(self.name, str):
            raise TypeError("Function reference name must be a string")
        if not all(part.isidentifier() for part in self.name.split(".")):
            raise ValueError("Function reference name must be a Python qualified name")
        if self.kind is not None and self.kind not in functions.FUNCTION_KINDS:
            raise ValueError(f"Unsupported function kind: {self.kind}")
        if self.category is not None and not isinstance(self.category, str):
            raise TypeError("Function reference category must be a string")
        if not isinstance(self.validate_signature, bool):
            raise TypeError("validate_signature must be a boolean")
        if self.description is not None and not isinstance(self.description, str):
            raise TypeError("Function reference description must be a string")

    @property
    def entrypoint(self) -> str:
        """Return the entrypoint in ``module.path:qualname`` format."""
        return entrypoint_module.Entrypoint.format(self.module, self.name)


def _docstring_summary(function: abc.Callable[..., object]) -> str | None:
    """Return the docstring summary line of a callable, or None without one."""
    docstring = inspect.getdoc(function)
    if not docstring:
        return None
    summary = docstring.split("\n\n", 1)[0]
    return " ".join(summary.split())


def function(
    function: abc.Callable[..., object] | str,
    *,
    kind: functions.FunctionKindId | None = None,
    category: str | None = None,
    validate_signature: bool = True,
    description: str | None = None,
) -> FunctionReference:
    """Reference a callable or a ``module.path:qualname`` entrypoint string.

    Args:
        function: A named Python callable such as ``module.calculate``, or an
            importable module and qualified name separated by a colon. Creating
            a reference does not load code; compilation and execution do.
        kind: Optional function contract for undecorated implementations. Must
            agree with decorated semantics when supplied for a decorated callable.
        category: Optional free-form grouping label stored in the Spec.
        validate_signature: Whether compilation and documentation should inspect
            the Python signature and validate implementation contracts.
        description: Optional explicit function description. Defaults to the
            docstring summary line when a callable is given.

    Returns:
        A reference containing the module location, function name, and
        description.

    Raises:
        TypeError: If the argument is neither callable nor a string,
            category is not a string, or validate_signature is not a boolean.
        ValueError: If the entrypoint is invalid or the callable has no valid
            module and function name, or if kind is unsupported.
    """
    if isinstance(function, str):
        module, separator, name = function.rpartition(":")
        if not separator:
            raise ValueError("Function entrypoint must use 'module.path:qualname'")
    else:
        if not callable(function):
            raise TypeError("function must be a Python callable or a string")
        callable_function = entrypoint_module.Function.from_callable(function)
        module = callable_function.module.location
        name = callable_function.name
        declared = function_semantics.declared_kind(function)
        if declared is not None:
            if kind is not None and kind != declared:
                raise ValueError(
                    f"Function kind '{kind}' conflicts with decorated kind '{declared}'"
                )
            kind = declared
        declared_category = function_semantics.declared_category(function)
        if declared_category is not None:
            if category is not None and category != declared_category:
                raise ValueError(
                    f"Function category '{category}' conflicts with decorated category "
                    f"'{declared_category}'"
                )
            category = declared_category
        if description is None:
            description = _docstring_summary(function)
    return FunctionReference(
        module=module,
        name=name,
        kind=kind,
        category=category,
        validate_signature=validate_signature,
        description=description,
    )
