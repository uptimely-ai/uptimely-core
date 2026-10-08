"""Python-friendly dataset fragment declarations."""

from __future__ import annotations

from dataclasses import dataclass, field

from uptimely.spec.json_spec.json_model import (
    Binding,
)
from uptimely.spec.json_spec.json_model import (
    Sink as SinkModel,
)
from uptimely.spec.json_spec.json_model import (
    Source as SourceModel,
)
from uptimely.spec.json_spec.json_model import (
    Transform as TransformModel,
)

from .bind import Bind, _binding_args, _operation_id
from .feature import Raw, _feature_models

__all__ = [
    "Read",
    "Conform",
    "Expand",
    "Collapse",
    "Write",
]


@dataclass(frozen=True)
class Read:
    """The callable that loads a dataset from an external source into an immutable fragment."""

    bind: Bind
    id: str | None = None
    features: list[Raw] = field(default_factory=list)

    def to_model(self) -> SourceModel:
        """Convert this source declaration to its JSON model."""
        identifier = _operation_id(self.bind, self.id)
        return SourceModel(
            id=identifier,
            binding=Binding(
                function=_operation_id(self.bind, None),
                args=_binding_args(self.bind),
            ),
            features=_feature_models(self.features),
        )


@dataclass(frozen=True)
class _Operation:
    """Shared declaration fields for non-source dataset operations."""

    bind: Bind
    id: str | None = None
    description: str | None = None
    features: list[Raw] = field(default_factory=list)

    def to_model(self) -> TransformModel:
        """Convert this operation declaration to its JSON model."""
        identifier = _operation_id(self.bind, self.id)
        return TransformModel(
            id=identifier,
            binding=Binding(
                function=_operation_id(self.bind, None),
                args=_binding_args(self.bind),
            ),
            features=_feature_models(self.features),
        )


@dataclass(frozen=True)
class Conform(_Operation):
    """A dataset operation that reconciles or narrows a fragment to the target row scope."""


@dataclass(frozen=True)
class Expand(_Operation):
    """A dataset expansion operation."""


@dataclass(frozen=True)
class Collapse(_Operation):
    """A dataset collapse operation."""


@dataclass(frozen=True)
class Write:
    """The callable that persists a dataset."""

    bind: Bind
    id: str | None = None

    def to_model(self) -> SinkModel:
        """Convert this write declaration to its JSON model."""
        identifier = _operation_id(self.bind, self.id)
        return SinkModel(
            id=identifier,
            binding=Binding(
                function=_operation_id(self.bind, None),
                args=_binding_args(self.bind),
            ),
        )
