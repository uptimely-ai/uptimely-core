"""Python-friendly structural references and reference factories."""

from __future__ import annotations

import dataclasses
from collections import abc

__all__ = [
    "Reference",
    "FunctionReference",
    "function",
    "current_dataset",
    "dataset",
    "source",
    "sink",
    "feature",
    "dimension",
]


@dataclasses.dataclass(frozen=True)
class FunctionReference:
    """A function location normalized without importing or executing its module."""

    module: str
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.module, str):
            raise TypeError("Function reference module must be a string")
        if not self.module.strip():
            raise ValueError("Function reference module must not be empty")
        if not isinstance(self.name, str):
            raise TypeError("Function reference name must be a string")
        if not self.name.isidentifier():
            raise ValueError("Function reference name must be a Python identifier")

    @property
    def entrypoint(self) -> str:
        """Return the canonical module-and-function entrypoint."""
        return f"{self.module}:{self.name}"


def function(
    function: abc.Callable[..., object] | str,
) -> FunctionReference:
    """Reference a callable or a ``module:function`` entrypoint string.

    Args:
        function: A named Python callable such as ``module.calculate``, or an
            entrypoint string such as ``path/to/module.py:calculate``,
            ``https://example.org/module.py:calculate``, or
            ``s3://bucket/module.py:calculate``. Creating a reference does not
            load code; compilation and execution do.

    Returns:
        A reference containing the module location and function name.

    Raises:
        TypeError: If the argument is neither callable nor a string.
        ValueError: If the entrypoint is invalid or the callable has no valid
            module and function name.
    """
    if isinstance(function, str):
        module, separator, name = function.rpartition(":")
        if not separator:
            raise ValueError("Function entrypoint must use 'module:function' or 'path:function'")
    else:
        if not callable(function):
            raise TypeError("function must be a Python callable or a string")
        module = getattr(function, "__module__", None)
        name = getattr(function, "__name__", None)
        if not isinstance(module, str) or not isinstance(name, str):
            raise ValueError(
                "Callable must have a module and function name; pass an entrypoint string instead"
            )
    return FunctionReference(module=module, name=name)


@dataclasses.dataclass(frozen=True)
class Reference:
    """A Python declaration reference resolved to a structural binding value."""

    type: str
    value: str

    def to_model(self) -> str:
        """Convert this reference to its canonical structural reference string."""
        return self.value

    @property
    def id(self) -> Reference:
        """Pass the referenced resource's identifier as a string argument."""
        return Reference(type="string", value=f"{self.value}.id")

    @property
    def dataframe(self) -> Reference:
        """Pass a dataset's materialized dataframe as an argument."""
        if self.type != "dataset":
            raise ValueError("Only dataset references have a dataframe selector")
        return Reference(type="dataset", value=f"{self.value}.dataframe")


def current_dataset() -> Reference:
    """Reference the dataset currently being evaluated."""
    return Reference(type="dataset", value="$datasets.@")


def dataset(name: str) -> Reference:
    """Reference a dataset by name."""
    return Reference(type="dataset", value=f"$datasets.{name}")


def source(name: str, attribute: str = "path") -> str:
    """Reference a runtime-configured source attribute by name."""
    return f"?storage.{name}.{attribute}"


def sink(name: str, attribute: str = "path") -> str:
    """Reference a runtime-configured sink attribute by name."""
    return f"?storage.{name}.{attribute}"


def feature(name: str) -> Reference:
    """Reference a source or calculated feature by name."""
    return Reference(type="feature", value=f"$features.{name}")


def dimension(name: str) -> Reference:
    """Reference a dataset dimension by name."""
    return Reference(type="dimension", value=f"$dimensions.{name}")
