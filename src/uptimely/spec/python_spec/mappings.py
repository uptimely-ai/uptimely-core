"""Python-friendly dataset mapping declarations."""

from __future__ import annotations

import dataclasses
import typing

from uptimely.spec import json_spec

from . import bind as bind_module
from . import feature as feature_module
from . import ref
from . import row_context as row_context_module

__all__ = [
    "Vectorize",
    "Read",
    "Conform",
    "Expand",
    "Collapse",
    "Write",
]


@dataclasses.dataclass(frozen=True)
class _Mapping:
    """A function binding that produces one or more declared dataset features."""

    bind: bind_module.Bind
    id: str | None = None
    inputs: list[ref.Reference | str] = dataclasses.field(default_factory=list)
    outputs: list[feature_module.Feature | ref.Reference | str] = dataclasses.field(
        default_factory=list
    )
    description: str | None = None
    row_context: (
        row_context_module.RowContext | row_context_module.RowContextBinding[typing.Any] | None
    ) = None

    def __post_init__(self) -> None:
        """Consolidate directional maxima from annotated arguments and metadata."""
        object.__setattr__(
            self, "row_context", row_context_module._context(self.bind.args, self.row_context)
        )

    def to_model(self) -> json_spec.json_model.Mapping:
        """Convert this mapping declaration to its canonical model."""
        identifier = bind_module._operation_id(self.bind, self.id)
        arguments = bind_module._binding_args(self.bind)
        return json_spec.json_model.Mapping(
            id=identifier,
            binding=json_spec.json_model.Binding(
                function=bind_module._operation_id(self.bind, None),
                args=arguments,
            ),
            features={
                "inputs": [f"$features.{_feature_id(feature)}" for feature in self.inputs],
                "outputs": [f"$features.{_feature_id(feature)}" for feature in self.outputs],
            },
            row_context=self.row_context,
        )


@dataclasses.dataclass(frozen=True)
class Vectorize(_Mapping):
    """Calculate a dimension-keyed dataframe fragment at the dataset's grain."""


@dataclasses.dataclass(frozen=True)
class Read(_Mapping):
    """A mapping that reads features from an external source."""


@dataclasses.dataclass(frozen=True)
class Conform(_Mapping):
    """A mapping that conforms input data to the target dataset's row scope."""


@dataclasses.dataclass(frozen=True)
class Expand(_Mapping):
    """A mapping that expands input data to the target dimensional coverage."""


@dataclasses.dataclass(frozen=True)
class Collapse(_Mapping):
    """Bind a dataframe-producing function at a coarser observation grain.

    Args:
        bind: The dataframe-producing callable and its analytical arguments.
        id: Optional mapping identifier.
        inputs: Required source features.
        outputs: Declared output features. Dimension keys are required implicitly.
    """


@dataclasses.dataclass(frozen=True)
class Write(_Mapping):
    """The output-free mapping that persists or evaluates a dataset."""


def _feature_id(feature: feature_module.Feature | ref.Reference | str) -> str:
    """Return a mapping output's feature identifier."""
    if isinstance(feature, ref.Reference):
        prefix, _, identifier = feature.value.rpartition(".")
        if prefix != "$features":
            raise ValueError(f"Mapping output must reference a feature, got {feature.value!r}")
        return identifier
    if not isinstance(feature, str):
        return feature.id
    if feature.startswith("$features."):
        return feature.removeprefix("$features.")
    return feature
