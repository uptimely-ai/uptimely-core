"""Base contract and display naming for document models."""

import pydantic


class StrictModel(pydantic.BaseModel):
    """Base model that rejects fields outside the spec contract."""

    model_config = pydantic.ConfigDict(extra="forbid")


def humanize_identifier(identifier: str) -> str:
    """Return a display name for a snake- or kebab-case identifier."""
    return identifier.replace("_", " ").replace("-", " ").title()
