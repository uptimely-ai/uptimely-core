"""Input, output, and workflow I/O functions for the cooling-pump example."""

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


@function(category="read")
def read_pump_telemetry(
    pump_telemetry_source: str,
    pump_source: str,
    server_room_id: str | None = None,
) -> pl.LazyFrame:
    """Load cooling-pump telemetry and join its asset metadata.

    Parameters
    ----------
    pump_telemetry_source
        Resolved path to the data for the ``pump_telemetry`` profile.
    pump_source
        Resolved path to pump asset metadata.
    server_room_id
        Optional server room ID to filter the telemetry.

    Returns
    -------
    Cooling-pump telemetry joined with asset metadata and an ``operation_mode`` column.

    Examples
    --------
    >>> telemetry = read_pump_telemetry(
    ...     "data/input/pump_telemetry.json",
    ...     "data/input/pump_assets.json",
    ...     server_room_id="SR-A",
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
            "data_center_id",
            "server_room_id",
            "pump_id",
            "machine_series_id",
            "machine_category_id",
            "rated_flow_rate",
        )
    )
    if server_room_id:
        pump_telemetry = pump_telemetry.filter(pl.col("server_room_id") == server_room_id)

    return (
        pump_telemetry.join(
            pump,
            on=["data_center_id", "server_room_id", "pump_id"],
            how="left",
            validate="m:1",
        )
        .with_columns(
            pl.when(pl.col("flow_rate") < pl.col("rated_flow_rate"))
            .then(pl.lit("below_rated_flow"))
            .otherwise(pl.lit("at_or_above_rated_flow"))
            .alias("operation_mode"),
            pl.col("timestamp").dt.truncate("1m").alias("minute"),
            pl.col("timestamp").dt.truncate("1h").alias("hour"),
            pl.col("timestamp").dt.truncate("1d").alias("day"),
        )
        .drop("rated_flow_rate")
    )


@function(category="write")
def write_file(dataset: pl.LazyFrame, features: list[str], output: str) -> None:
    """Write the complete profile frame to a configured JSON or CSV file.

    Parameters
    ----------
    dataset
        Complete profile dataframe, including identifiers and relations.
    features
        Declared profile features that must be present in the dataframe.
    output
        Resolved path to the output file.

    Returns
    -------
    This function writes the dataframe to the configured file.

    Raises
    ------
    ValueError
        If a declared feature is missing or the file extension is unsupported.

    Examples
    --------
    >>> write_file(
    ...     pl.LazyFrame({"pump_id": ["CWP-101"], "efficiency": [0.5]}),
    ...     ["efficiency"],
    ...     "data/output/telemetry.csv",
    ... )  # doctest: +SKIP
    """
    output_path = pathlib.Path(output)
    if output_path.suffix.lower() not in {".csv", ".json"}:
        raise ValueError(f"Unsupported file extension: {output_path.suffix}")

    frame = dataset.collect()
    missing_features = sorted(set(features) - set(frame.columns))
    if missing_features:
        raise ValueError("Missing profile features: " + ", ".join(missing_features))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".csv":
        frame.write_csv(output_path)
    else:
        frame.write_json(output_path)


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
        Path to a JSON array of records or a CSV file. The Engine resolves
        configured project paths before calling this function.
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
    path = pathlib.Path(source)
    suffix = path.suffix.lower()
    if suffix == ".json":
        dataset = pl.read_json(path).lazy()
    elif suffix == ".csv":
        dataset = pl.scan_csv(path)
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
def process_pump_external_workflow(source: str, output: str) -> None:
    """Read cooling-pump inputs, calculate ratios, and write results internally.

    Parameters
    ----------
    source
        Resolved path to the external workflow input CSV.
    output
        Resolved path for the workflow output CSV.

    Returns
    -------
    Results are written to the output CSV as a side effect.

    Examples
    --------
    >>> process_pump_external_workflow("input.csv", "output.csv")  # doctest: +SKIP
    """
    observations = pl.read_csv(source)
    result = observations.with_columns(
        (pl.col("measurement") / pl.col("reference_value")).alias("ratio")
    )
    output_path = pathlib.Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.select("data_center_id", "server_room_id", "pump_id", "ratio").write_csv(output_path)
