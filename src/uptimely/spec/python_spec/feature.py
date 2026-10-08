"""Python-friendly dataset feature declarations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from uptimely.spec.json_spec.json_model import (
    Binding,
)
from uptimely.spec.json_spec.json_model import (
    Calculation as CalculationModel,
)
from uptimely.spec.json_spec.json_model import (
    Input as InputModel,
)

from .bind import Bind, _binding_args, _operation_id

__all__ = [
    "Raw",
    "Vectorize",
    "Aggregation",
    "aggregation",
]


@dataclass(frozen=True)
class Aggregation:
    """An aggregate function binding evaluated within a collapse operation."""

    function: Callable[..., object]
    args: dict[str, Any]
    function_id: str | None = None

    @property
    def id(self) -> str:
        """Return the explicit or callable-derived function identifier."""
        return self.function_id or self.function.__name__


def aggregation(
    function: Callable[..., object], /, function_id: str | None = None, **args: Any
) -> Aggregation:
    """Bind an aggregate function for evaluation within a collapse operation."""
    return Aggregation(function=function, args=args, function_id=function_id)


@dataclass(frozen=True)
class Raw:
    """A source-provided dataset feature."""

    id: str
    description: str | None = None
    type: str = "object"
    unit: str | None = None

    def to_model(self) -> InputModel:
        """Convert this input declaration to its JSON model."""
        return InputModel(
            id=self.id,
            description=self.description,
            type=self.type,
            unit=self.unit,
        )


@dataclass(frozen=True)
class Vectorize:
    """A vectorized dataset feature."""

    id: str
    bind: Bind
    description: str | None = None
    unit: str | None = None

    def to_model(self) -> CalculationModel:
        """Convert this vectorized feature declaration to its JSON model."""
        return CalculationModel(
            id=self.id,
            description=self.description,
            unit=self.unit,
            binding=Binding(
                function=_operation_id(self.bind, None),
                args=_binding_args(self.bind),
            ),
        )


def _feature_models(features: list[Raw]) -> dict[str, InputModel]:
    """Convert feature declarations to canonical models keyed by identifier."""
    return {feature.id: feature.to_model() for feature in features}
