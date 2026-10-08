"""Source functions for reading data from various sources."""

import polars as pl


def read_pump_telemetry(
    source: str,
    production_line: str | None = None,
    environment: str = "development",
) -> pl.LazyFrame:
    """Load telemetry for an optional production line from a mock environment."""
    if environment not in {"development", "qa", "production"}:
        raise ValueError(f"Unsupported environment: {environment}")

    data = pl.read_json(source).lazy()
    return data.filter(pl.col("production_line") == production_line) if production_line else data
