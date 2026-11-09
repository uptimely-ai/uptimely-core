"""Resolve pump capacities across the machine hierarchy."""

import polars as pl

from uptimely import function


@function(category="calculate")
def resolve_capacity(dataset: pl.LazyFrame, features: list[str], output: str) -> pl.LazyFrame:
    """Choose the first non-null capacity in most-to-least-specific order.

    Parameters
    ----------
    dataset
        Pump profile with capacities from each resolution.
    features
        Capacity columns ordered from most to least accurate resolution.
    output
        Name of the resolved capacity feature.

    Returns
    -------
    Pump profile with the resolved capacity, preserving all source columns.
    """
    return dataset.with_columns(pl.coalesce(features).alias(output))
