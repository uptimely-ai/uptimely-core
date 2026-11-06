"""Observation dimensions and their keyed resolutions."""

import typing

import pydantic

from . import base


class Resolution(base.StrictModel):
    """A keyed resolution of a dimension."""

    id: str = pydantic.Field(exclude=True)
    key: str
    type: str
    parent: str | None = None


class Dimension(base.StrictModel):
    """A globally defined observation dimension."""

    id: str = pydantic.Field(exclude=True)
    resolutions: dict[str, Resolution]
    description: str | None = None
    name: str | None = None

    @pydantic.model_validator(mode="after")
    def require_resolutions(self) -> typing.Self:
        """Require a dimension to expose at least one usable resolution."""
        if not self.resolutions:
            raise ValueError("A dimension must declare at least one resolution")
        return self

    @pydantic.model_validator(mode="after")
    def generate_name(self) -> typing.Self:
        """Generate a display name from the dimension ID when one is not supplied."""
        if self.name is None:
            self.name = base.humanize_identifier(self.id)
        return self
