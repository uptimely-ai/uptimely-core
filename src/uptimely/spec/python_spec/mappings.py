"""Python-friendly dataset mapping declarations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from uptimely.spec.json_spec import json_model

from .bind import Bind, _binding_args, _operation_id
from .feature import Feature as _Feature
from .ref import Reference
from .row_context import RowContext, RowContextBinding, _context

__all__ = [
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

    def to_model(self) -> json_model.FeatureMapping:
        """Convert this mapping declaration to its canonical model."""
        identifier = _operation_id(self.bind, self.id)
        arguments = _binding_args(self.bind)
        return json_model.FeatureMapping(
            id=identifier,
            binding=json_model.Binding(
                function=_operation_id(self.bind, None),
                args=arguments,
            ),
            features=[_feature_id(feature) for feature in self.features],
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
    """Bind a collapse function with input data inferred from bound features.

    Args:
        bind: The reducer callable and its analytical arguments.
        id: Optional mapping identifier.
        features: Declared outputs, including the target entity's grouping dimensions.
    """


@dataclass(frozen=True)
class Write(_Mapping):
    """The output-free mapping that persists or evaluates a dataset."""

    def to_model(self) -> json_model.FeatureMapping:
        """Convert this write declaration to an output-free mapping model."""
        identifier = _operation_id(self.bind, self.id)
        return json_model.FeatureMapping(
            id=identifier,
            binding=json_model.Binding(
                function=_operation_id(self.bind, None),
                args=_binding_args(self.bind),
            ),
            features=[],
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
