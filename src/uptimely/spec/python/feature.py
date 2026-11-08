"""Python-friendly profile feature declarations."""

from __future__ import annotations

import dataclasses

from uptimely.spec import feature_types
from uptimely.spec import model as spec_model
from uptimely.spec.model import base as model_base

__all__ = ["Feature", "FeatureSet"]


@dataclasses.dataclass(frozen=True)
class Feature:
    """A named output feature with a stable identifier and display name."""

    id: str | None = None
    name: str | None = None
    type: feature_types.FeatureType | None = None
    unit: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        """Generate a display name from the ID when one is not supplied."""
        if self.name is None and self.id is not None:
            object.__setattr__(self, "name", model_base.humanize_identifier(self.id))

    def to_model(self) -> spec_model.Feature:
        """Convert this feature declaration to its JSON model."""
        if self.id is None:
            raise ValueError("Feature requires an id outside a FeatureSet declaration")
        return spec_model.Feature(
            id=self.id,
            name=self.name,
            description=self.description,
            type=self.type,
            unit=self.unit,
        )


class FeatureSet:
    """Namespace for a profile's feature declarations.

    Subclasses declare :class:`Feature` instances as class attributes and
    reference those attributes from ``Operator.interface.outputs``. A feature
    without an explicit ID uses its attribute name.
    """

    def __init_subclass__(cls) -> None:
        """Set missing feature IDs from their attribute names."""
        super().__init_subclass__()
        for name, value in vars(cls).items():
            if isinstance(value, Feature) and value.id is None:
                setattr(cls, name, dataclasses.replace(value, id=name))
