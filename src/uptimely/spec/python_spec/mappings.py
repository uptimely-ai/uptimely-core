"""Python-friendly dataset mapping declarations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from uptimely.spec.json_spec import json_model

from .aggregation import Aggregation, aggregation
from .bind import Bind, _binding_args, _operation_id
from .feature import Feature as _Feature
from .ref import Reference
from .row_context import RowContext, RowContextBinding, _context

__all__ = [
    "Aggregation",
    "aggregation",
    "Vectorize",
    "Read",
    "Conform",
    "Expand",
    "Collapse",
    "Write",
]


@dataclass(frozen=True)
class _Mapping:
    """A function binding that produces one or more declared dataset features."""

    bind: Bind
    id: str | None = None
    features: list[_Feature | Reference | str] = field(default_factory=list)
    description: str | None = None
    aggregations: dict[str, Any] = field(default_factory=dict)

    def to_model(self) -> json_model.FeatureMapping:
        """Convert this mapping declaration to its canonical model."""
        identifier = _operation_id(self.bind, self.id)
        arguments = _binding_args(self.bind)
        aggregations = self.aggregations
        if isinstance(self, Collapse) and not aggregations:
            aggregations = arguments.pop("aggregations", {})
        return json_model.FeatureMapping(
            id=identifier,
            binding=json_model.Binding(
                function=_operation_id(self.bind, None),
                args=arguments,
            ),
            features=[_feature_id(feature) for feature in self.features],
            aggregations={
                feature_id: _aggregation_binding(aggregation)
                for feature_id, aggregation in aggregations.items()
            },
        )


@dataclass(frozen=True)
class Vectorize(_Mapping):
    """A mapping that calculates feature values while preserving dataset rows."""

    row_context: RowContext | RowContextBinding[Any] | None = None

    def __post_init__(self) -> None:
        """Consolidate context annotations from bound arguments and metadata."""
        object.__setattr__(self, "row_context", _context(self.bind.args, self.row_context))


@dataclass(frozen=True)
class Read(_Mapping):
    """A mapping that reads features from an external source."""


@dataclass(frozen=True)
class Conform(_Mapping):
    """A mapping that conforms input data to the target dataset's row scope."""


@dataclass(frozen=True)
class Expand(_Mapping):
    """A mapping that expands input data to the target dimensional coverage."""


@dataclass(frozen=True)
class Collapse(_Mapping):
    """A mapping that groups input data and applies per-feature aggregations."""


@dataclass(frozen=True)
class Write(_Mapping):
    """The callable that persists a dataset."""

    def to_model(self) -> json_model.Sink:
        """Convert this write declaration to its JSON model."""
        identifier = _operation_id(self.bind, self.id)
        return json_model.Sink(
            id=identifier,
            binding=json_model.Binding(
                function=_operation_id(self.bind, None),
                args=_binding_args(self.bind),
            ),
        )


def _feature_id(feature: _Feature | Reference | str) -> str:
    """Return a mapping output's feature identifier."""
    if isinstance(feature, Reference):
        prefix, _, identifier = feature.value.rpartition(".")
        if prefix != "$features":
            raise ValueError(f"Mapping output must reference a feature, got {feature.value!r}")
        return identifier
    if not isinstance(feature, str):
        return feature.id
    if feature.startswith("$features."):
        return feature.removeprefix("$features.")
    return feature


def _aggregation_binding(value: Aggregation | dict[str, Any]) -> json_model.Binding:
    """Convert a Python or canonical aggregation binding to its model."""
    if isinstance(value, Aggregation):
        return json_model.Binding(
            function=value.id,
            args=_binding_args(
                Bind(
                    function=value.function,
                    args=value.args,
                    function_id=value.function_id,
                )
            ),
        )
    return json_model.Binding.model_validate(
        {
            "function": value["function"],
            "args": value.get("args", {}),
        }
    )
