"""Callable entrypoints used by test specifications."""

import polars as pl


def read_observation_totals() -> pl.DataFrame:
    """Load the small dataset used by the observation-totals spec fixture."""
    return pl.DataFrame(
        {
            "id": [1, 2],
            "input_1": [1, 3],
            "input_2": [2, 4],
        }
    )


def sum_observation_features(
    dataset: pl.LazyFrame,
    left_feature: str,
    right_feature: str,
    output: str,
) -> pl.LazyFrame:
    """Add two selected features for the observation-totals spec fixture."""
    return dataset.with_columns((pl.col(left_feature) + pl.col(right_feature)).alias(output))
