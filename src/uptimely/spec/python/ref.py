"""Python-friendly structural references and reference factories."""

from __future__ import annotations

import dataclasses
import inspect
import re
from collections import abc

from uptimely import entrypoint as entrypoint_module

from .. import arg_types, functions, selectors
from . import functions as function_semantics

__all__ = [
    "Reference",
    "OutputReference",
    "DatasetDimensionsReference",
    "FunctionReference",
    "function",
    "current_dataset",
    "dataset",
    "source",
    "sink",
    "feature",
    "dimension",
    "dataframe",
    "column",
    "output",
    "parameter",
]

_PARAMETER_NAME = re.compile(r"^[A-Za-z_]\w*$")


@dataclasses.dataclass(frozen=True)
class FunctionReference:
    """A function location normalized without importing or executing its module."""

    module: str
    name: str
    kind: functions.FunctionKindId | None = None
    validate_signature: bool = True
    description: str | None = None

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
        validate_signature: Whether compilation and documentation should inspect
            the Python signature and validate implementation contracts.
        description: Optional explicit function description. Defaults to the
            docstring summary line when a callable is given.

    Returns:
        A reference containing the module location, function name, and
        description.

    Raises:
        TypeError: If the argument is neither callable nor a string, or
            validate_signature is not a boolean.
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
        if description is None:
            description = _docstring_summary(function)
    return FunctionReference(
        module=module,
        name=name,
        kind=kind,
        validate_signature=validate_signature,
        description=description,
    )


@dataclasses.dataclass(frozen=True)
class Reference:
    """A Python declaration reference resolved to a structural binding value."""

    type: str
    value: str

    def to_model(self) -> str:
        """Convert this reference to the spec document's reference string format."""
        return self.value

    @property
    def id(self) -> Reference:
        """Pass the referenced resource's identifier as a string argument."""
        return Reference(type=arg_types.STRING, value=f"{self.value}{selectors.ID_SELECTOR}")

    @property
    def dataframe(self) -> Reference:
        """Pass a dataset's materialized dataframe as an argument."""
        if self.type != "dataset":
            raise ValueError("Only dataset references have a dataframe selector")
        return Reference(type="dataset", value=f"{self.value}{selectors.DATAFRAME_SELECTOR}")

    @property
    def dimensions(self) -> DatasetDimensionsReference:
        """Select dimension metadata from a dataset reference."""
        if self.type != "dataset":
            raise ValueError("Only dataset references have dimension selectors")
        return DatasetDimensionsReference(value=f"{self.value}.dimensions")


@dataclasses.dataclass(frozen=True)
class DatasetDimensionsReference:
    """Dimension selectors available on a dataset reference."""

    value: str

    @property
    def ids(self) -> Reference:
        """Pass the dataset's dimension identifiers as an array of strings."""
        return Reference(
            type=arg_types.array_of(arg_types.STRING),
            value=f"{self.value}.ids",
        )


@dataclasses.dataclass(frozen=True)
class OutputReference(Reference):
    """An output identifier that must belong to the containing action."""

    name: str


def dataframe(name: str | None = None) -> Reference:
    """Reference a dataframe without loading or constructing it.

    Args:
        name: Dataset identifier, or None for the current dataset.

    Returns:
        A deferred reference to the dataset's materialized dataframe.
    """
    return (current_dataset() if name is None else dataset(name)).dataframe


def column(name: str) -> Reference:
    """Reference an input feature column, declaring a data dependency."""
    return feature(name)


def output(name: str) -> OutputReference:
    """Reference a declared output's name without adding an input dependency.

    Args:
        name: Feature name declared in the containing action's outputs.

    Returns:
        A deferred string reference to the output identifier.
    """
    identifier = feature(name).id
    return OutputReference(type=identifier.type, value=identifier.value, name=name)


def current_dataset() -> Reference:
    """Reference the dataset currently being evaluated."""
    return Reference(type="dataset", value=f"{selectors.DATASET_PREFIX}{selectors.CURRENT_ID}")


def dataset(name: str) -> Reference:
    """Reference a dataset by name."""
    return Reference(type="dataset", value=f"{selectors.DATASET_PREFIX}{name}")


def source(name: str, attribute: str = "path") -> str:
    """Reference a source path configured as a global project parameter."""
    if attribute != "path":
        raise ValueError("Source references support only the 'path' attribute")
    return parameter(name)


def sink(name: str, attribute: str = "path") -> str:
    """Reference a sink path configured as a global project parameter."""
    if attribute != "path":
        raise ValueError("Sink references support only the 'path' attribute")
    return parameter(name)


def parameter(name: str) -> str:
    """Reference a required scalar value from ``config/config.json``.

    Args:
        name: A nonempty Python identifier used as the parameter key.

    Returns:
        The spec reference string ``$params.<name>``.

    Raises:
        ValueError: If the name is not a valid parameter identifier.
    """
    if not isinstance(name, str) or not _PARAMETER_NAME.fullmatch(name):
        raise ValueError("Parameter names must be nonempty Python identifiers")
    return f"{selectors.PARAMS_PREFIX}{name}"


def feature(name: str) -> Reference:
    """Reference a source or calculated feature by name."""
    return Reference(type="feature", value=f"{selectors.FEATURE_PREFIX}{name}")


def dimension(name: str) -> Reference:
    """Reference a dataset dimension by name."""
    return Reference(type="dimension", value=f"{selectors.DIMENSION_PREFIX}{name}")
