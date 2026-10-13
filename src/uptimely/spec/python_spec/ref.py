"""Python-friendly structural references and reference factories."""

from __future__ import annotations

import dataclasses

__all__ = [
    "Reference",
    "current_dataset",
    "dataset",
    "source",
    "sink",
    "feature",
    "dimension",
]


@dataclasses.dataclass(frozen=True)
class Reference:
    """A Python declaration reference resolved to a structural binding value."""

    type: str
    value: str

    def to_model(self) -> str:
        """Convert this reference to its canonical structural reference string."""
        return self.value

    @property
    def id(self) -> Reference:
        """Pass the referenced resource's identifier as a string argument."""
        return Reference(type="string", value=f"{self.value}.id")

    @property
    def dataframe(self) -> Reference:
        """Pass a dataset's materialized dataframe as an argument."""
        if self.type != "dataset":
            raise ValueError("Only dataset references have a dataframe selector")
        return Reference(type="dataset", value=f"{self.value}.dataframe")


def current_dataset() -> Reference:
    """Reference the dataset currently being evaluated."""
    return Reference(type="dataset", value="$datasets.@")


def dataset(name: str) -> Reference:
    """Reference a dataset by name."""
    return Reference(type="dataset", value=f"$datasets.{name}")


def source(name: str, attribute: str = "path") -> str:
    """Reference a runtime-configured source attribute by name."""
    return f"?storage.{name}.{attribute}"


def sink(name: str, attribute: str = "path") -> str:
    """Reference a runtime-configured sink attribute by name."""
    return f"?storage.{name}.{attribute}"


def feature(name: str) -> Reference:
    """Reference a source or calculated feature by name."""
    return Reference(type="feature", value=f"$features.{name}")


def dimension(name: str) -> Reference:
    """Reference a dataset dimension by name."""
    return Reference(type="dimension", value=f"$dimensions.{name}")
