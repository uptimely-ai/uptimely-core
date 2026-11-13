"""Input, output, and workflow I/O functions for the pump example."""

import collections.abc
import pathlib
import types

import polars as pl

from uptimely import function

EMPTY_COLUMN_RENAMES: collections.abc.Mapping[str, str] = types.MappingProxyType({})
COLUMN_TYPES = {
    "float": pl.Float64,
    "integer": pl.Int64,
    "string": pl.String,
    "boolean": pl.Boolean,
}


EXAMPLE_ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_PATH = EXAMPLE_ROOT / "data" / "input" / "pump_external_workflow.csv"
OUTPUT_PATH = EXAMPLE_ROOT / "_generated" / "pump_external_workflow_results.csv"


@function(category="read")
def read_pump_telemetry(
    pump_telemetry_source: str,
    pump_source: str,
    production_line_id: str | None = None,
) -> pl.LazyFrame:
    """Load pump telemetry and join its pump profile data.

    Parameters
    ----------
    pump_telemetry_source
        Path to the data for the ``pump_telemetry`` profile.
    pump_source
        Path to the data for the ``pump`` profile.
    production_line_id
        Optional production line ID to filter the telemetry.

    Returns
    -------
    Telemetry joined with pump metadata and an ``operation_mode`` column.

    Examples
    --------
    >>> telemetry = read_pump_telemetry(
    ...     "data/input/pump_telemetry.json",
    ...     "data/input/pump_assets.json",
    ...     production_line_id="line_1",
    ... )  # doctest: +SKIP
    """
    pump_telemetry = (
        pl.read_json(pump_telemetry_source)
        .lazy()
        .with_columns(pl.col("timestamp").str.to_datetime(time_zone="UTC"))
    )
    pump = (
        pl.read_json(pump_source)
        .lazy()
        .select(
            "plant_id",
            "production_line_id",
            "pump_id",
            "machine_series_id",
            "machine_category_id",
            "rated_flow_rate",
        )
    )
    if production_line_id:
        pump_telemetry = pump_telemetry.filter(pl.col("production_line_id") == production_line_id)

    return (
        pump_telemetry.join(
            pump,
            on=["plant_id", "production_line_id", "pump_id"],
            how="left",
            validate="m:1",
        )
        .with_columns(
            pl.when(pl.col("flow_rate") < pl.col("rated_flow_rate"))
            .then(pl.lit("low_speed"))
            .otherwise(pl.lit("high_speed"))
            .alias("operation_mode"),
            pl.col("timestamp").dt.truncate("1m").alias("minute"),
            pl.col("timestamp").dt.truncate("1h").alias("hour"),
            pl.col("timestamp").dt.truncate("1d").alias("day"),
        )
        .drop("rated_flow_rate")
    )


@function(category="write")
def write_pump_telemetry(dataset: pl.LazyFrame, features: list[str]) -> None:
    """Write calculated telemetry features as JSON to standard output.

    Parameters
    ----------
    dataset
        DataFrame containing the calculated telemetry features.
    features
        Names of the feature columns to write.

    Returns
    -------
    This mock sink discards the dataset.

    Examples
    --------
    >>> write_pump_telemetry(pl.LazyFrame({"efficiency": [0.5]}), ["efficiency"])
    """
    return


@function(category="read")
def read_file(
    source: str,
    columns: list[str] | None = None,
    rename: collections.abc.Mapping[str, str] = EMPTY_COLUMN_RENAMES,
    schema: collections.abc.Mapping[str, str] = EMPTY_COLUMN_RENAMES,
) -> pl.LazyFrame:
    """Read a JSON or CSV file into a profile.

    Parameters
    ----------
    source
        Path to a JSON array of records or a CSV file.
    columns
        Source columns to select, in order. If omitted, read all columns.
    rename
        Mapping from source column names to feature names, applied after selection.
    schema
        Optional source column types: float, integer, string, or boolean.
        Applied before selection and renaming, including for all-null columns.

    Returns
    -------
    File observations as a lazy frame.

    Raises
    ------
    ValueError
        If the file extension or a requested column type is unsupported.
    """
    suffix = pathlib.Path(source).suffix.lower()
    if suffix == ".json":
        dataset = pl.read_json(source).lazy()
    elif suffix == ".csv":
        dataset = pl.scan_csv(source)
    else:
        raise ValueError(f"Unsupported file extension: {suffix}")
    for column, dtype in schema.items():
        if dtype not in COLUMN_TYPES:
            raise ValueError(f"Unsupported column type for {column}: {dtype}")
    if schema:
        dataset = dataset.cast({column: COLUMN_TYPES[dtype] for column, dtype in schema.items()})
    if columns is not None:
        dataset = dataset.select(columns)
    if rename:
        dataset = dataset.rename(rename)
    return dataset


@function(returns="any", category="workflow")
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
