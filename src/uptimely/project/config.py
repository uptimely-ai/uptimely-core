"""Shared project code configuration."""

import pydantic


class CodeSettings(pydantic.BaseModel):
    """Project code language, runtime definition location, and source directory."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    language: str = pydantic.Field(default="python", min_length=1)
    requirements: str | None = pydantic.Field(default=None, min_length=1)
    src: str | None = pydantic.Field(default=None, min_length=1)

    @pydantic.field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        """Require a nonblank code language."""
        if not value.strip():
            raise ValueError("Code language must be nonblank")
        return value
