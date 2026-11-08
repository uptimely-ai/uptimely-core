"""Base contract and display naming for document models."""

import re

import pydantic


class StrictModel(pydantic.BaseModel):
    """Base model that rejects fields outside the spec contract."""

    model_config = pydantic.ConfigDict(extra="forbid")


def humanize_identifier(identifier: str) -> str:
    """Return a display name for a snake- or kebab-case identifier."""
    return identifier.replace("_", " ").replace("-", " ").title()


def snake_case_identifier(value: str) -> str:
    """Convert a display or class name to a snake-case identifier."""
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated)
    return re.sub(r"[^A-Za-z0-9]+", "_", separated).strip("_").lower()
