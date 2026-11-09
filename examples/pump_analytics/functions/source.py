"""Generic file sources for profile observations."""

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


@function(kind="read")
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
