"""Python-friendly structural references and reference factories."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Reference",
    "current_dataset",
    "dataset",
    "fragment",
    "source",
    "sink",
    "feature",
    "dimension",
]


@dataclass(frozen=True)
class Reference:
    """A Python declaration reference resolved to a structural binding value."""

    type: str
    value: str

    def to_model(self) -> str:
        """Convert this reference to its canonical structural reference string."""
        return self.value


def current_dataset() -> Reference:
    """Reference the dataset currently being evaluated."""
    return Reference(type="dataset", value="$datasets.@")


def dataset(name: str) -> Reference:
    """Reference a dataset by name."""
    return Reference(type="dataset", value=f"$datasets.{name}")


def fragment(name: str) -> Reference:
    """Reference a dataframe fragment by name."""
    return Reference(type="fragment", value=f"$fragments.{name}")


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
