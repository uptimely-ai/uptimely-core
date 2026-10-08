"""Sink functions for writing calculated example data."""

import polars as pl


def write_pump_telemetry(dataset: pl.LazyFrame, features: list[str]) -> None:
    """Write calculated telemetry features as JSON to standard output."""
    print(dataset.select(features).collect().write_json())
