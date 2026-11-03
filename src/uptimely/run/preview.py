"""Bounded Polars previews with explicit, browser-safe JSON value encoding."""

import base64
import datetime
import decimal
import math

import polars as pl
import pydantic

from . import models

MAX_SAFE_JSON_INTEGER = 2**53 - 1


def _json_value(value: object) -> pydantic.JsonValue:
    """Encode rich dataframe cells without lossy implicit JSON conversions."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return str(value) if abs(value) > MAX_SAFE_JSON_INTEGER else value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Preview struct keys must be strings")
        return {key: _json_value(item) for key, item in value.items()}
    raise TypeError(f"Unsupported preview cell type: {type(value).__name__}")


def collect_preview(
    profile_id: str, frame: object, rows: int
) -> tuple[models.ProfilePreview, pl.DataFrame]:
    """Limit before collecting; propagate errors for the recorder to report.

    Args:
        profile_id: Profile owning the final frame.
        frame: Eager or lazy Polars frame.
        rows: Positive maximum sample size.

    Returns:
        The serializable preview and its collected dataframe for console display.

    Raises:
        TypeError: The frame or a cell value cannot be serialized.
        polars.exceptions.PolarsError: The bounded query cannot be collected.
    """
    if not isinstance(frame, (pl.DataFrame, pl.LazyFrame)):
        raise TypeError(f"Unsupported preview frame type: {type(frame).__name__}")
    sample = frame.head(rows)
    if isinstance(sample, pl.LazyFrame):
        sample = sample.collect()
    artifact = models.ProfilePreview(
        profile_id=profile_id,
        status="succeeded",
        requested_rows=rows,
        columns=[
            models.PreviewColumn(name=name, dtype=str(dtype))
            for name, dtype in sample.schema.items()
        ],
        rows=[[_json_value(value) for value in row] for row in sample.iter_rows()],
    )
    return artifact, sample
