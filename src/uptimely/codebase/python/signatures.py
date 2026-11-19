"""Inspect and format annotated Python callable signatures."""

from __future__ import annotations

import dataclasses
import inspect
import types
import typing

if typing.TYPE_CHECKING:
    from . import address


class TypeAnnotation:
    """Format Python type annotations for display."""

    @staticmethod
    def name(annotation: object) -> str:
        """Return a readable name for a type annotation."""
        if annotation is None or annotation is type(None):
            return "None"

        origin = typing.get_origin(annotation)
        if origin in (typing.Union, types.UnionType):
            return " | ".join(TypeAnnotation.name(arg) for arg in typing.get_args(annotation))

        if origin is not None:
            arguments = ", ".join(TypeAnnotation.name(arg) for arg in typing.get_args(annotation))
            return (
                f"{TypeAnnotation.name(origin)}[{arguments}]"
                if arguments
                else TypeAnnotation.name(origin)
            )

        return getattr(annotation, "__name__", str(annotation))


@dataclasses.dataclass
class DisplaySignature:
    """Formatted input and output annotations for presentation."""

    args: dict[str, str] = dataclasses.field(default_factory=dict)
    returns: str | None = None

    @classmethod
    def from_signature(cls, signature: inspect.Signature) -> DisplaySignature:
        """Create display metadata from an inspected Python signature."""
        return cls(
            args={
                name: TypeAnnotation.name(parameter.annotation)
                for name, parameter in signature.parameters.items()
                if parameter.annotation is not inspect.Parameter.empty
            },
            returns=(
                TypeAnnotation.name(signature.return_annotation)
                if signature.return_annotation is not inspect.Signature.empty
                else None
            ),
        )


@dataclasses.dataclass
class Signature:
    """Raw reflection data required to validate a Python function signature."""

    parameters: dict[str, inspect.Parameter] = dataclasses.field(default_factory=dict)
    return_annotation: object = dataclasses.field(default=inspect.Signature.empty, repr=False)

    @property
    def accepts_kwargs(self) -> bool:
        """Return whether the callable accepts arbitrary keyword arguments."""
        return any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in self.parameters.values()
        )

    @property
    def required_parameters(self) -> dict[str, inspect.Parameter]:
        """Return non-variadic parameters without defaults, in signature order."""
        return {
            name: parameter
            for name, parameter in self.parameters.items()
            if parameter.default is inspect.Parameter.empty
            and parameter.kind
            not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
        }

    @property
    def display(self) -> DisplaySignature:
        """Return presentation-oriented annotation metadata."""
        return DisplaySignature(
            args={
                name: TypeAnnotation.name(parameter.annotation)
                for name, parameter in self.parameters.items()
                if parameter.annotation is not inspect.Parameter.empty
            },
            returns=(
                TypeAnnotation.name(self.return_annotation)
                if self.return_annotation is not inspect.Signature.empty
                else None
            ),
        )

    @classmethod
    def read(cls, function: address.Function) -> Signature:
        """Read the annotated argument and return types of a function."""
        return cls.from_callable(function.load())

    @classmethod
    def from_callable(cls, function: typing.Callable[..., typing.Any]) -> Signature:
        """Read the annotated argument and return types of a loaded callable."""
        signature = inspect.signature(function, follow_wrapped=True, eval_str=True)
        return cls.from_signature(signature)

    @classmethod
    def from_signature(cls, signature: inspect.Signature) -> Signature:
        """Create validation metadata from an inspected Python signature."""
        return cls(
            parameters=dict(signature.parameters),
            return_annotation=signature.return_annotation,
        )
