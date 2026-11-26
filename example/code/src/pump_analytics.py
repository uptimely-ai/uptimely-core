"""Analytical functions for cooling-pump telemetry."""

import collections.abc
import functools
import operator
import types

import polars as pl
import pump_util as util

from uptimely import function

SUPPORTED_AGGREGATIONS = ("max", "min", "mean", "sum")
EMPTY_COLUMN_RENAMES: collections.abc.Mapping[str, str] = types.MappingProxyType({})


@function(category="calculate")
def pump_mode(
    dataset: pl.LazyFrame,
    bearing_temperature: str,
    vibration_rms: str,
    output: str,
    bearing_temperature_warning_limit: float,
    vibration_warning_limit: float,
) -> pl.LazyFrame:
    """Classify each reading using illustrative temperature and vibration limits.

    Parameters
    ----------
    dataset
        DataFrame containing the condition readings.
    bearing_temperature
        Bearing-temperature column in degrees Celsius.
    vibration_rms
        Vibration RMS column in mm/s.
    output
        Name of the resulting mode column.
    bearing_temperature_warning_limit
        Inclusive bearing-temperature warning threshold in degrees Celsius.
    vibration_warning_limit
        Inclusive vibration RMS warning threshold in mm/s.

    Returns
    -------
    DataFrame with ``warning`` when either reading reaches its supplied limit,
    otherwise ``operational``. Missing or non-finite
    readings produce null unless the other reading establishes a warning.
    These limits are illustrative, not validated equipment limits.
    """
    temperature = pl.col(bearing_temperature)
    vibration = pl.col(vibration_rms)
    temperature = pl.when(temperature.is_finite()).then(temperature)
    vibration = pl.when(vibration.is_finite()).then(vibration)
    warning = (temperature >= bearing_temperature_warning_limit) | (
        vibration >= vibration_warning_limit
    )
    mode = (
        pl.when(warning)
        .then(pl.lit("warning"))
        .when(~warning)
        .then(pl.lit("operational"))
        .otherwise(pl.lit(None, dtype=pl.String))
    )
    return dataset.with_columns(mode.alias(output))


@function(category="select")
def filter_rows(
    dataset: pl.LazyFrame,
    feature: str,
    value: str,
    rename: collections.abc.Mapping[str, str] = EMPTY_COLUMN_RENAMES,
) -> pl.LazyFrame:
    """Select matching rows and optionally rename columns for a target profile.

    Parameters
    ----------
    dataset
        Source profile dataset.
    feature
        Column used to select matching rows.
    value
        Required value of the filter column. Null values do not match.
    rename
        Mapping from source column names to target feature names.

    Returns
    -------
    Filtered fragment with source keys and optional column renaming, including
    an empty fragment with the same schema when no rows match.
    """
    return dataset.filter(pl.col(feature) == value).rename(rename)


@function(category="select")
def select_columns(
    dataset: pl.LazyFrame,
    columns: list[str],
    rename: collections.abc.Mapping[str, str] = EMPTY_COLUMN_RENAMES,
) -> pl.LazyFrame:
    """Select profile columns and optionally rename them for the target profile.

    Parameters
    ----------
    dataset
        Source profile dataset.
    columns
        Source columns to select, in order, including identifiers needed for merging.
    rename
        Mapping from selected source column names to output names.

    Returns
    -------
    Selected columns with optional renaming, preserving rows and nulls.
    """
    # Example module import
    util.dummy_pass()

    return dataset.select(columns).rename(rename)


@function(category="aggregate")
def aggregate(
    dataset: pl.LazyFrame,
    aggregations: collections.abc.Mapping[str, str],
    dimensions: list[str],
    rename: collections.abc.Mapping[str, str] = EMPTY_COLUMN_RENAMES,
) -> pl.LazyFrame:
    """Return a dimension-keyed aggregate fragment at the requested grain.

    Parameters
    ----------
    dataset
        DataFrame to aggregate.
    aggregations
        Mapping from source column names to aggregation methods. Each method
        must be one of ``"max"``, ``"min"``, ``"mean"``, or ``"sum"``.
    dimensions
        Dimension columns defining the aggregation grain. When empty,
        the aggregate is computed over the whole dataset.
    rename
        Mapping from aggregated source column names to output names.
        Columns not listed retain their source names.

    Returns
    -------
    Aggregated fragment keyed by the requested dimensions.

    Raises
    ------
    ValueError
        If aggregations are empty, a method is unsupported, or a rename refers
        to a column that is not aggregated.

    Examples
    --------
    >>> frame = pl.LazyFrame({"pump": ["p1", "p1"], "flow": [1.0, 3.0]})
    >>> aggregate(frame, {"flow": "max"}, [], {"flow": "max_flow"}).collect().to_dicts()
    [{'max_flow': 3.0}]
    """
    if not aggregations:
        raise ValueError("At least one aggregation is required")
    unknown_columns = set(rename) - set(aggregations)
    if unknown_columns:
        raise ValueError(
            f"Cannot rename non-aggregated columns: {', '.join(sorted(unknown_columns))}"
        )
    expressions = []
    for feature, method in aggregations.items():
        if method not in SUPPORTED_AGGREGATIONS:
            raise ValueError(f"Unsupported aggregation method: {method}")
        expressions.append(getattr(pl.col(feature), method)().alias(rename.get(feature, feature)))
    data_collapsed = (
        dataset.group_by(dimensions).agg(expressions) if dimensions else dataset.select(expressions)
    )
    return data_collapsed


@function(category="calculate")
def delta(
    dataset: pl.LazyFrame,
    feature: str,
    partition_by: list[str],
    order_by: str,
    num_rows: int,
    output: str,
) -> pl.LazyFrame:
    """Return the ordered difference from a preceding row within each partition.

    Parameters
    ----------
    dataset
        DataFrame containing the readings.
    feature
        Name of the column to difference.
    partition_by
        Columns identifying each partition.
    order_by
        Column defining the ordering within each partition.
    num_rows
        Number of rows to look back for the difference.
    output
        Name of the resulting difference column.

    Returns
    -------
    DataFrame with the ordered difference appended.

    Examples
    --------
    >>> frame = pl.LazyFrame({"pump_id": ["p1", "p1"], "ts": [1, 2], "temp": [60.0, 61.5]})
    >>> delta(frame, "temp", ["pump_id"], "ts", 1, "temp_delta").collect()["temp_delta"].to_list()
    [None, 1.5]
    """
    data_vectorized = dataset.with_columns(
        pl.col(feature).diff(n=num_rows).over(partition_by, order_by=order_by).alias(output)
    )
    return data_vectorized


@function(category="calculate")
def ratio(
    dataset: pl.LazyFrame,
    numerator_features: list[str],
    denominator_features: list[str],
    output: str,
    scale: float = 1.0,
) -> pl.LazyFrame:
    """Return the scaled ratio of the numerator and denominator products.

    Parameters
    ----------
    dataset
        DataFrame containing the numerator and denominator columns.
    numerator_features
        Names of the columns multiplied into the numerator.
    denominator_features
        Names of the columns multiplied into the denominator.
    output
        Name of the resulting ratio column.
    scale
        Constant factor applied to the ratio, for example a unit
        conversion. Defaults to ``1.0``.

    Returns
    -------
    DataFrame with the scaled ratio appended.

    Examples
    --------
    >>> frame = pl.LazyFrame({"hydraulic": [5.0], "electrical": [10.0]})
    >>> ratio(frame, ["hydraulic"], ["electrical"], "efficiency").collect()[
    ...     "efficiency"
    ... ].to_list()
    [0.5]
    """
    numerator = functools.reduce(operator.mul, (pl.col(name) for name in numerator_features))
    denominator = functools.reduce(operator.mul, (pl.col(name) for name in denominator_features))
    data_vectorized = dataset.with_columns((scale * numerator / denominator).alias(output))
    return data_vectorized


@function(category="calculate")
def subtract(
    dataset: pl.LazyFrame,
    feature: str,
    subtrahend: str,
    output: str,
) -> pl.LazyFrame:
    """Return the difference between two feature columns.

    Parameters
    ----------
    dataset
        DataFrame containing both feature columns.
    feature
        Name of the column subtracted from.
    subtrahend
        Name of the column subtracted from the feature.
    output
        Name of the resulting difference column.

    Returns
    -------
    DataFrame with the difference appended.

    Examples
    --------
    >>> frame = pl.LazyFrame({"temperature": [25.0], "ambient": [20.0]})
    >>> subtract(frame, "temperature", "ambient", "rise").collect()["rise"].to_list()
    [5.0]
    """
    data_vectorized = dataset.with_columns((pl.col(feature) - pl.col(subtrahend)).alias(output))
    return data_vectorized


@function(category="select")
def extract_field(
    dataset: pl.LazyFrame,
    field: str,
    column: str,
    output: str,
) -> pl.LazyFrame:
    """Return the requested field from a struct column.

    Parameters
    ----------
    dataset
        DataFrame containing the struct column.
    field
        Name of the struct field to extract.
    column
        Name of the struct column.
    output
        Name of the resulting extracted column.

    Returns
    -------
    DataFrame with the extracted field appended.

    Examples
    --------
    >>> frame = pl.LazyFrame({"recommendation": [{"converged": True}]})
    >>> extract_field(frame, "converged", "recommendation", "ok").collect()["ok"].to_list()
    [True]
    """
    data_vectorized = dataset.with_columns(pl.col(column).struct.field(field).alias(output))
    return data_vectorized


@function(category="calculate")
def min_max_scale(
    dataset: pl.LazyFrame,
    feature: str,
    lower_bound: float,
    upper_bound: float,
    features: list[str],
    output: str,
) -> pl.LazyFrame:
    """Return a min-max-scaled column with a stable constant-data value.

    Parameters
    ----------
    dataset
        DataFrame containing the column to scale.
    feature
        Name of the column to scale.
    lower_bound
        Lower bound of the scaled range; also used when the input
        column is constant.
    upper_bound
        Upper bound of the scaled range.
    features
        Declared feature dependencies; unused by the calculation.
    output
        Name of the resulting scaled column.

    Returns
    -------
    DataFrame with the scaled column appended.

    Examples
    --------
    >>> frame = pl.LazyFrame({"score": [0.0, 5.0, 10.0]})
    >>> min_max_scale(frame, "score", 0.0, 1.0, [], "scaled").collect()["scaled"].to_list()
    [0.0, 0.5, 1.0]
    """
    _ = features
    column = pl.col(feature)
    minimum = column.min()
    spread = column.max() - minimum
    expression = (
        pl.when(spread == 0)
        .then(pl.lit(lower_bound))
        .otherwise(lower_bound + (column - minimum) * (upper_bound - lower_bound) / spread)
    )
    data_vectorized = dataset.with_columns(expression.alias(output))
    return data_vectorized


@function(category="estimate")
def operation_point_optimization(
    dataset: pl.LazyFrame,
    optimization_features: list[str],
    output: str,
    bearing_temperature_warning_limit: float,
    vibration_warning_limit: float,
    method: str = "quantum",
) -> pl.LazyFrame:
    """Return recommended operating values and convergence as a struct column.

    Illustrative mockup for a cooling-pump operating-point recommendation.

    Parameters
    ----------
    dataset
        DataFrame containing cooling-pump operating measurements.
    optimization_features
        Names of the differential-pressure, flow, power, temperature, and vibration
        columns, in that order.
    output
        Name of the resulting struct column.
    bearing_temperature_warning_limit
        Bearing-temperature limit in degrees Celsius, excluding convergence at
        or above the limit.
    vibration_warning_limit
        Vibration RMS limit in mm/s, excluding convergence at or above the limit.
    method
        Optimization method. Only ``"quantum"`` is supported.

    Returns
    -------
    DataFrame with the recommendation struct appended.

    Raises
    ------
    ValueError
        If ``method`` is not ``"quantum"``.

    Examples
    --------
    >>> frame = pl.LazyFrame(
    ...     {"pressure": [4.0], "flow": [10.0], "power": [5.0], "temp": [80.0], "vib": [3.0]}
    ... )
    >>> features = ["pressure", "flow", "power", "temp", "vib"]
    >>> result = operation_point_optimization(frame, features, "recommendation", 90.0, 4.5)
    >>> result.collect()["recommendation"].to_list()[0]["converged"]
    True
    """
    if method.lower() != "quantum":
        raise ValueError("Only 'quantum' method is supported.")
    pressure, flow, power, temperature, vibration = map(pl.col, optimization_features)
    expression = pl.struct(
        recommended_flow_rate=flow,
        recommended_differential_pressure=pressure,
        energy_cost_score=power / flow,
        converged=(temperature < bearing_temperature_warning_limit)
        & (vibration < vibration_warning_limit),
    )
    data_vectorized = dataset.with_columns(expression.alias(output))
    return data_vectorized


@function(category="calculate")
def pump_health_score(
    dataset: pl.LazyFrame, health_features: list[str], output: str
) -> pl.LazyFrame:
    """Return a cooling-pump score reduced by temperature and vibration changes.

    Parameters
    ----------
    dataset
        DataFrame containing the health input features.
    health_features
        Names of the temperature-delta, vibration-delta, and efficiency
        columns, in that order.
    output
        Name of the resulting health-score column.

    Returns
    -------
    DataFrame with the health score appended.

    Examples
    --------
    >>> frame = pl.LazyFrame({"temp_delta": [5.0], "vib_delta": [0.5], "efficiency": [1.0]})
    >>> pump_health_score(frame, ["temp_delta", "vib_delta", "efficiency"], "health").collect()[
    ...     "health"
    ... ].to_list()
    [0.25]
    """
    temperature_delta, vibration_delta, efficiency = map(pl.col, health_features)
    data_vectorized = dataset.with_columns(
        (efficiency - temperature_delta.abs() / 10.0 - vibration_delta.abs() / 2.0).alias(output)
    )
    return data_vectorized


@function(category="calculate")
def first_non_null_value(dataset: pl.LazyFrame, features: list[str], output: str) -> pl.LazyFrame:
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
