"""Python-friendly dataset mapping declarations."""

from __future__ import annotations

import dataclasses
import typing

from uptimely import contracts
from uptimely.analytics import model as analytics_model

from . import bind as bind_module
from . import feature as feature_module
from . import ref
from . import row_context as row_context_module

__all__ = ["Mapping"]


@dataclasses.dataclass(frozen=True)
class Mapping:
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
        """Require function operation metadata and consolidate row context."""
        if self.bind.function.operation is None:
            raise ValueError(
                "Mapping requires operation metadata on ref.function(..., operation=...)"
            )
        object.__setattr__(
            self, "row_context", row_context_module._context(self.bind.args, self.row_context)
        )

    @property
    def operation(self) -> contracts.FunctionOperation:
        """Return the operation declared by this mapping's function reference."""
        operation = self.bind.function.operation
        if operation is None:
            raise ValueError(
                "Mapping requires operation metadata on ref.function(..., operation=...)"
            )
        return operation

    def to_model(self) -> analytics_model.Mapping:
        """Convert this mapping declaration to its document model."""
        identifier = bind_module._mapping_id(self.bind, self.id)
        arguments = bind_module._binding_args(self.bind)
        return analytics_model.Mapping(
            id=identifier,
            binding=analytics_model.Binding(
                function=bind_module._function_id(self.bind),
                args=arguments,
            ),
            features={
                "inputs": [
                    f"{contracts.FEATURE_PREFIX}{_feature_id(feature)}" for feature in self.inputs
                ],
                "outputs": [
                    f"{contracts.FEATURE_PREFIX}{_feature_id(feature)}" for feature in self.outputs
                ],
            },
            row_context=self.row_context,
        )


def _feature_id(feature: feature_module.Feature | ref.Reference | str) -> str:
    """Return a mapping output's feature identifier."""
    if isinstance(feature, ref.Reference):
        prefix, _, identifier = feature.value.rpartition(".")
        if prefix != contracts.FEATURE_PREFIX.removesuffix("."):
            raise ValueError(f"Mapping output must reference a feature, got {feature.value!r}")
        return identifier
    if not isinstance(feature, str):
        return feature.id
    if feature.startswith(contracts.FEATURE_PREFIX):
        return feature.removeprefix(contracts.FEATURE_PREFIX)
    return feature
