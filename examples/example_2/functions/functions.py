from collections.abc import Callable

import polars as pl
from examples.example_2.data.data import DATA


def read_data() -> pl.DataFrame:
    """Load the raw dataset."""
    return pl.DataFrame(DATA)


def extract_col(df: pl.DataFrame, column: str) -> pl.Series:
    return df[column]


def sum_features(
    left_feature: str,
    right_feature: str,
    output: str,
) -> pl.Expr:
    """Add two feature columns and store the result in a named output column."""
    return (pl.col(left_feature) + pl.col(right_feature)).alias(output)


def expand_data(df1: pl.DataFrame, df2: pl.DataFrame) -> pl.DataFrame:

    # Start with the first dataset as the base
    return df1.join(df2, on="id", how="inner")


def agg(
    df: pl.DataFrame,
    dimension: str,
    features: list[str],
    aggregation: Callable[[pl.Expr], pl.Expr] | None = None,
) -> pl.DataFrame:
    """Aggregate feature columns by a dimension.

    ``aggregation`` receives each feature expression and must return the
    expression to use for that feature. It defaults to ``implode``.
    """
    aggregate = aggregation or pl.Expr.implode
    return df.group_by(dimension).agg([aggregate(pl.col(feature)) for feature in features])


def filter_data(df: pl.DataFrame, filter: str) -> pl.DataFrame:
    return df.filter(pl.col(filter))


def tag_first_item(id_column: str, output: str) -> pl.Expr:
    """Mark the first row for each identifier dimension."""
    return (pl.col(id_column).cum_count().over(id_column) == 1).alias(output)


def write_data(new_data: object) -> bool:
    """Write the dataset as JSON to stdout-style sink; returns True on success."""
    print(new_data.data.write_json())
    return True
