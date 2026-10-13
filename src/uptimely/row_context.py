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

    Empty directions mean current-row-only input. An absent RowContext means
    unknown requirements, not zero context. Unbounded directions require all
    observations in that direction; two unbounded directions need no ordering.
    """

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    dimension: str | None = pydantic.Field(default=None, pattern=r"^\$dimensions\.[^.]+$")
    before: ContextExtent | typing.Literal["unbounded"] = pydantic.Field(
        default_factory=ContextExtent
    )
    after: ContextExtent | typing.Literal["unbounded"] = pydantic.Field(
        default_factory=ContextExtent
    )

    @pydantic.model_validator(mode="after")
    def validate_extent(self) -> RowContext:
        """Require one measurement across both directional requirements."""
        measurements = {
            key
            for direction in (self.before, self.after)
            if isinstance(direction, ContextExtent)
            for key in direction.model_dump(exclude_none=True)
        }
        if len(measurements) > 1:
            raise ValueError("Row context must use one measurement: time, steps, or rows")
        if measurements & {"time", "steps"} and self.dimension is None:
            raise ValueError("Time and steps context require a declared dimension")
        if "rows" in measurements and self.dimension is not None:
            raise ValueError("Row-count context uses dataset order, not a dimension")
        return self

    @pydantic.model_serializer
    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible metadata without unspecified measurements."""
        result: dict[str, object] = {
            "before": (
                self.before.model_dump(exclude_none=True)
                if isinstance(self.before, ContextExtent)
                else self.before
            ),
            "after": (
                self.after.model_dump(exclude_none=True)
                if isinstance(self.after, ContextExtent)
                else self.after
            ),
        }
        if self.dimension is not None:
            result["dimension"] = self.dimension
        return result

    def merge(self, other: RowContext) -> RowContext:
        """Combine requirements for the same input scope without adding lags."""
        if (
            self.dimension is not None
            and other.dimension is not None
            and self.dimension != other.dimension
        ):
            raise ValueError("Row context must use one dimension")
        if self.before == self.after == UNBOUNDED:
            return self
        if other.before == other.after == UNBOUNDED:
            return other
        return RowContext(
            dimension=self.dimension or other.dimension,
            before=(
                UNBOUNDED
                if self.before == UNBOUNDED or other.before == UNBOUNDED
                else self.before.merge(other.before)
            ),
            after=(
                UNBOUNDED
                if self.after == UNBOUNDED or other.after == UNBOUNDED
                else self.after.merge(other.after)
            ),
        )

    @property
    def requires_order(self) -> bool:
        """Return whether the context distinguishes preceding from following rows."""

        def amount(direction: ContextExtent | typing.Literal["unbounded"]) -> int | str:
            if direction == UNBOUNDED:
                return UNBOUNDED
            values = direction.model_dump(exclude_none=True)
            if not values:
                return 0
            measure, value = next(iter(values.items()))
            if value == UNBOUNDED:
                return UNBOUNDED
            return duration_nanoseconds(value) if measure == "time" else value

        before, after = amount(self.before), amount(self.after)
        return not (before == after == UNBOUNDED) and (before != 0 or after != 0)
