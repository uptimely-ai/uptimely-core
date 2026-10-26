"""The spec document model."""

from __future__ import annotations

import typing

import pydantic

from . import common, normalization
from . import dataset as dataset_module
from . import functions as functions_module

SPEC_VERSION = 2


class Spec(common.StrictModel):
    """The complete JSON spec document."""

    name: str | None = None
    spec_version: typing.Literal[2] = SPEC_VERSION
    source: common.SpecSource = pydantic.Field(
        default_factory=lambda: common.SpecSource(name="manual", generated=False)
    )
    dimensions: dict[str, common.Dimension] = pydantic.Field(default_factory=dict)
    functions: functions_module.FunctionCatalog = pydantic.Field(
        default_factory=functions_module.FunctionCatalog
    )
    entities: dict[str, dataset_module.Entity] = pydantic.Field(default_factory=dict)

    @property
    def dimension_ids_by_dataset(self) -> dict[str, list[str]]:
        """Return each dataset's owning entity dimension identifiers."""
        return {
            dataset.id: entity.dimension_ids
            for entity in self.entities.values()
            for dataset in entity.datasets.values()
        }

    @pydantic.field_validator("spec_version", mode="before")
    @classmethod
    def validate_spec_version_type(cls, value: object) -> object:
        """Reject booleans, which Python otherwise treats as integer literals."""
        if type(value) is not int:
            raise ValueError("spec_version must be an integer")
        return value

    @pydantic.model_validator(mode="before")
    @classmethod
    def normalize_document(cls, value: typing.Any) -> typing.Any:
        return normalization.normalize_spec_document(value)
