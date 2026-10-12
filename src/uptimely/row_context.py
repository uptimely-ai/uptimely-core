"""Portable observation-context requirements shared by specifications and plans."""

from __future__ import annotations

import decimal
import re
import typing

import pydantic

UNBOUNDED: typing.Literal["unbounded"] = "unbounded"
CountExtent = typing.Annotated[int, pydantic.Field(strict=True, ge=0)] | typing.Literal["unbounded"]
TimeExtent = str

_UNITS = {
    "w": 604_800_000_000_000,
    "d": 86_400_000_000_000,
    "h": 3_600_000_000_000,
    "m": 60_000_000_000,
    "s": 1_000_000_000,
    "ms": 1_000_000,
    "us": 1_000,
    "ns": 1,
}
_DURATION_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)(ms|us|ns|w|d|h|m|s)")


def duration_nanoseconds(value: str) -> int:
    """Parse a fixed duration such as ``1h30m`` without floating-point rounding.

    Args:
        value: Nonnegative duration using distinct lowercase unit suffixes.
            Days and weeks mean exactly 24 hours and seven days.

    Returns:
        The exact duration in nanoseconds.

    Raises:
        ValueError: If syntax is invalid or precision is finer than a nanosecond.
    """
    position = 0
    total = 0
    seen: set[str] = set()
    for match in _DURATION_PART.finditer(value):
        amount, unit = match.groups()
        if match.start() != position or unit in seen:
            raise ValueError(f"Invalid fixed duration: {value!r}")
        # Integer arithmetic avoids Decimal context rounding on large durations.
        numerator, denominator = decimal.Decimal(amount).as_integer_ratio()
        nanoseconds, remainder = divmod(numerator * _UNITS[unit], denominator)
        if remainder:
            raise ValueError(f"Duration has sub-nanosecond precision: {value!r}")
        total += nanoseconds
        seen.add(unit)
        position = match.end()
    if position != len(value) or not seen:
        raise ValueError(f"Invalid fixed duration: {value!r}")
    return total


class ContextExtent(pydantic.BaseModel):
    """Context in one direction, expressed using a single measurement."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    time: TimeExtent | None = None
    steps: CountExtent | None = None
    rows: CountExtent | None = None

    @pydantic.field_validator("time")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        """Require a fixed duration or the explicit unbounded marker."""
        if value is not None and value != UNBOUNDED:
            duration_nanoseconds(value)
        return value

    @pydantic.model_validator(mode="before")
    @classmethod
    def reject_null_extents(cls, value: object) -> object:
        """Distinguish omitted measurements from invalid explicit nulls."""
        if isinstance(value, dict) and any(item is None for item in value.values()):
            raise ValueError("Context measurements cannot be null; omit them instead")
        return value

    @pydantic.model_validator(mode="after")
    def validate_measurement(self) -> ContextExtent:
        """Require at most one measurement within a directional extent."""
        if len(self.model_dump(exclude_none=True)) > 1:
            raise ValueError("Row context must use one measurement: time, steps, or rows")
        return self

    def merge(self, other: ContextExtent) -> ContextExtent:
        """Take the maximum extent, requiring compatible measurements."""
        values: dict[str, int | str] = {}
        for measure in ("time", "steps", "rows"):
            left = getattr(self, measure)
            right = getattr(other, measure)
            if left is None and right is None:
                continue
            if left == UNBOUNDED or right == UNBOUNDED:
                values[measure] = UNBOUNDED
            elif left is None:
                values[measure] = right
            elif right is None:
                values[measure] = left
            elif measure == "time":
                values[measure] = (
                    left if duration_nanoseconds(left) >= duration_nanoseconds(right) else right
                )
            else:
                values[measure] = max(left, right)
        return ContextExtent.model_validate(values)


class RowContext(pydantic.BaseModel):
    """Required input observations, interpreted using the dataset's logical order.

    An empty bounded context explicitly means current-row-only input. An absent
    RowContext means unknown requirements, not zero context. Partition and
    dataset extents require their entire respective input scopes.
    """

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    extent: typing.Literal["bounded", "partition", "dataset"] = "bounded"
    before: ContextExtent = pydantic.Field(default_factory=ContextExtent)
    after: ContextExtent = pydantic.Field(default_factory=ContextExtent)

    @pydantic.model_validator(mode="after")
    def validate_extent(self) -> RowContext:
        """Require one measurement across both directions of bounded context."""
        measurements = (
            self.before.model_dump(exclude_none=True).keys()
            | self.after.model_dump(exclude_none=True).keys()
        )
        if len(measurements) > 1:
            raise ValueError("Row context must use one measurement: time, steps, or rows")
        if self.extent != "bounded" and (
            self.before.model_dump(exclude_none=True) or self.after.model_dump(exclude_none=True)
        ):
            raise ValueError("Partition/dataset context cannot also declare before or after")
        return self

    @pydantic.model_serializer
    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible metadata without unspecified measurements."""
        return {
            "extent": self.extent,
            "before": self.before.model_dump(exclude_none=True),
            "after": self.after.model_dump(exclude_none=True),
        }

    def merge(self, other: RowContext) -> RowContext:
        """Combine requirements for the same input scope without adding lags."""
        if self.extent == "dataset" or other.extent == "dataset":
            return RowContext(extent="dataset")
        if self.extent == "partition" or other.extent == "partition":
            return RowContext(extent="partition")
        return RowContext(
            before=self.before.merge(other.before),
            after=self.after.merge(other.after),
        )
