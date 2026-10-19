"""An uncontrolled workflow that performs its I/O internally."""

import pathlib

import polars as pl

EXAMPLE_ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_PATH = EXAMPLE_ROOT / "data" / "source.csv"
OUTPUT_PATH = EXAMPLE_ROOT / "_generated" / "workflow_results.csv"


def read_declared_inputs() -> pl.DataFrame:
    """Load the declared dataframe inputs for the example mapping."""
    return pl.read_csv(SOURCE_PATH)


def run() -> None:
    """Read observations, calculate ratios, and write the result internally."""
    observations = pl.read_csv(SOURCE_PATH)
    result = observations.with_columns(
        (pl.col("measurement") / pl.col("reference_value")).alias("ratio")
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.select("asset_id", "ratio").write_csv(OUTPUT_PATH)
