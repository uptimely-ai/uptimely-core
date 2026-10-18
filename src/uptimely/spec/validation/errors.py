"""Validation error types."""

from __future__ import annotations


class SpecError(ValueError):
    """A semantic spec error with a stable code and resource path."""

    def __init__(self, message: str, *, code: str, path: tuple[str | int, ...]):
        self.code = code
        self.path = path
        location = ".".join(str(part) for part in path)
        super().__init__(f"{location}: {message}" if location else message)
