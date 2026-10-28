"""Uncontrolled workflow that reads and writes its data internally."""

import pathlib

import polars as pl

from uptimely.spec.python import function

EXAMPLE_ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_PATH = EXAMPLE_ROOT / "data" / "pump_external_workflow.csv"
OUTPUT_PATH = EXAMPLE_ROOT / "_generated" / "pump_external_workflow_results.csv"


@function(kind="read")
def read_pump_external_inputs() -> pl.DataFrame:
    """Load the dataframe inputs declared by the external workflow action."""
    return pl.read_csv(SOURCE_PATH)


@function(kind="escape")
def process_pump_external_workflow() -> None:
    """Read pump inputs, calculate ratios, and write results internally."""
    observations = pl.read_csv(SOURCE_PATH)
    result = observations.with_columns(
        (pl.col("measurement") / pl.col("reference_value")).alias("ratio")
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.select("plant", "production_line", "pump", "ratio").write_csv(OUTPUT_PATH)
