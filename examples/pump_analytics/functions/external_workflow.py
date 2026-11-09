"""Uncontrolled workflow that reads and writes its data internally."""

import pathlib

import polars as pl

from uptimely import function

EXAMPLE_ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_PATH = EXAMPLE_ROOT / "data" / "pump_external_workflow.csv"
OUTPUT_PATH = EXAMPLE_ROOT / "_generated" / "pump_external_workflow_results.csv"


@function(kind="merge", category="merge")
def merge_pump_inputs(
    target: pl.DataFrame | pl.LazyFrame | None,
    fragment: pl.DataFrame | pl.LazyFrame,
    target_keys: list[str],
) -> pl.DataFrame | pl.LazyFrame:
    """Full-join external inputs into the pump profile's current target."""
    if target is None:
        return fragment
    if isinstance(target, pl.DataFrame) and isinstance(fragment, pl.LazyFrame):
        target = target.lazy()
    elif isinstance(target, pl.LazyFrame) and isinstance(fragment, pl.DataFrame):
        fragment = fragment.lazy()
    return target.join(
        fragment,
        on=target_keys,
        how="full",
        coalesce=True,
        nulls_equal=True,
    )


@function(kind="escape", category="workflow")
def process_pump_external_workflow() -> None:
    """Read pump inputs, calculate ratios, and write results internally.

    Returns
    -------
    Results are written to the generated output CSV as a side effect.

    Examples
    --------
    >>> process_pump_external_workflow()  # doctest: +SKIP
    """
    observations = pl.read_csv(SOURCE_PATH)
    result = observations.with_columns(
        (pl.col("measurement") / pl.col("reference_value")).alias("ratio")
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.select("plant_id", "production_line_id", "pump_id", "ratio").write_csv(OUTPUT_PATH)
