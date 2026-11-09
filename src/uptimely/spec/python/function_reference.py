"""Function locations and callable metadata without eager module loading."""

from __future__ import annotations

import dataclasses
import inspect
from collections import abc

from uptimely import entrypoint as entrypoint_module
from uptimely.spec import function_contracts

from . import functions as function_semantics

__all__ = ["FunctionReference", "function"]


@dataclasses.dataclass(frozen=True)
class FunctionReference:
    """A function location normalized without importing or executing its module."""

    module: str
    name: str
    returns: function_contracts.ReturnRole | None = None
    args: dict[str, str] | None = None
    validate_signature: bool = True
    description: str | None = None
    category: str | None = None
    signature: inspect.Signature | None = dataclasses.field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.module, str):
            raise TypeError("Function reference module must be a string")
        if not entrypoint_module.Module.is_valid_location(self.module):
            raise ValueError("Function reference module must be an importable dotted module name")
        if not isinstance(self.name, str):
            raise TypeError("Function reference name must be a string")
        if not all(part.isidentifier() for part in self.name.split(".")):
            raise ValueError("Function reference name must be a Python qualified name")
        function_contracts.validate_metadata(self.returns, self.args)
        if self.category is not None and not isinstance(self.category, str):
            raise TypeError("Function reference category must be a string")
        if not isinstance(self.validate_signature, bool):
            raise TypeError("validate_signature must be a boolean")
        if self.description is not None and not isinstance(self.description, str):
            raise TypeError("Function reference description must be a string")
        if not self.validate_signature and (self.returns is None or self.args is None):
            raise ValueError("Disabling signature inspection requires explicit args and returns")

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
    returns: function_contracts.ReturnRole | None = None,
    args: dict[str, str] | None = None,
    category: str | None = None,
    validate_signature: bool | None = None,
    description: str | None = None,
) -> FunctionReference:
    """Reference a callable or a ``module.path:qualname`` entrypoint string.

    Args:
        function: A named Python callable such as ``module.calculate``, or an
            importable module and qualified name separated by a colon. Creating
            a reference does not load code; compilation and execution do.
        returns: Explicit independent return role when annotations are ambiguous.
        args: Explicit reusable argument types.
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
            module and function name, or if contracts conflict or are missing.
    """
    signature = None
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
        declared = function_semantics.declared_metadata(function)
        if returns is not None and declared.returns is not None and returns != declared.returns:
            raise ValueError("Return contract conflicts with decorated metadata")
        if args is not None and declared.args is not None and args != declared.args:
            raise ValueError("Argument contract conflicts with decorated metadata")
        returns = returns if returns is not None else declared.returns
        args = args if args is not None else declared.args
        if validate_signature is None:
            validate_signature = declared.validate_signature
        if validate_signature:
            signature = inspect.signature(function)
            annotation = signature.return_annotation
            if returns is None:
                returns = function_contracts.return_role(annotation)
            if returns is not None:
                function_contracts.check_return_annotation(returns, annotation)
        declared_category = declared.category
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
        returns=returns,
        args=args.copy() if args is not None else None,
        category=category,
        validate_signature=True if validate_signature is None else validate_signature,
        description=description,
        signature=signature,
    )
