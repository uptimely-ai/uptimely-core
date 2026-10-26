import polars as pl
from examples.simple_analytics.data.data import DATA

from uptimely.spec.python import operation


@operation("read")
def read_data() -> pl.DataFrame:
    """Load the raw dataset."""
    return pl.DataFrame(DATA)


def extract_col(df: pl.DataFrame, column: str) -> pl.Series:
    return df[column]


@operation("vectorize")
def sum_features(
    dataset: pl.LazyFrame,
    left_feature: str,
    right_feature: str,
    output: str,
) -> pl.LazyFrame:
    """Add two feature columns and store the result in a named output column."""
    return dataset.with_columns((pl.col(left_feature) + pl.col(right_feature)).alias(output))


@operation("expand")
def expand_data(source: pl.DataFrame) -> pl.DataFrame:
    """Return foreign values for reconciliation against the target dataset."""
    return source.select("id", pl.col("input_1").alias("expanded"))


def filter_data(df: pl.DataFrame, filter: str) -> pl.DataFrame:
    return df.filter(pl.col(filter))


@operation("vectorize")
def tag_first_item(dataset: pl.LazyFrame, id_column: str, output: str) -> pl.LazyFrame:
    """Mark the first row for each identifier dimension."""
    return dataset.with_columns((pl.col(id_column).cum_count().over(id_column) == 1).alias(output))


@operation("write")
def write_data(df: pl.DataFrame | pl.LazyFrame, cols: list[str]) -> None:
    """Print the selected feature columns as JSON."""
    selected = df.select(cols)
    if isinstance(selected, pl.LazyFrame):
        selected = selected.collect()
    print(selected.write_json())
