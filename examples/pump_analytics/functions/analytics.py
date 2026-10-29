"""Analytical, source, and sink functions for pump telemetry."""

import functools
import operator

import polars as pl

from uptimely import function

SUPPORTED_AGGREGATIONS = ("max", "min", "mean", "sum")


@function(kind="read")
def read_pump_telemetry(
    source: str,
    pump_assets_source: str,
    production_line: str | None = None,
    environment: str = "development",
) -> pl.LazyFrame:
    """Load telemetry for an optional production line from a mock environment.

    Parameters
    ----------
    source
        Path to the JSON file containing pump telemetry records.
    pump_assets_source
        Path to the JSON file containing pump asset metadata.
    production_line
        Production line to filter telemetry by. If ``None``, all lines
        are included.
    environment
        Target environment name; one of ``"development"``, ``"qa"``, or
        ``"production"``. Defaults to ``"development"``.

    Returns:
    -------
    Telemetry joined with pump assets and an ``operation_mode`` column.

    Raises:
    ------
    ValueError
        If ``environment`` is not a supported environment name.

    Examples:
    --------
    >>> telemetry = read_pump_telemetry(
    ...     "data/pump_telemetry.json",
    ...     "data/pump_assets.json",
    ...     production_line="line_1",
    ... )  # doctest: +SKIP
    """
    if environment not in {"development", "qa", "production"}:
        raise ValueError(f"Unsupported environment: {environment}")

    telemetry = (
        pl.read_json(source)
        .lazy()
        .with_columns(pl.col("timestamp").str.to_datetime(time_zone="UTC"))
    )
    pump_assets = (
        pl.read_json(pump_assets_source)
        .lazy()
        .select("plant", "production_line", "pump", "rated_flow_rate")
    )
    data_read = (
        telemetry.join(
            pump_assets,
            on=["plant", "production_line", "pump"],
            how="left",
            validate="m:1",
        )
        .with_columns(
            pl.when(pl.col("flow_rate") < pl.col("rated_flow_rate"))
            .then(pl.lit("low_speed"))
            .otherwise(pl.lit("high_speed"))
            .alias("operation_mode")
        )
        .drop("rated_flow_rate")
    )
    if production_line:
        data_read = data_read.filter(pl.col("production_line") == production_line)
    return data_read


@function(kind="read")
def read_constants(source: str) -> pl.LazyFrame:
    """Load project-wide physical constants.

    Parameters
    ----------
    source
        Path to the JSON file containing the constants.

    Returns:
    -------
    Constants as a single-row lazy frame.

    Examples:
    --------
    >>> constants = read_constants("data/constants.json")  # doctest: +SKIP
    """
    return pl.read_json(source).lazy()


@function(kind="write")
def write_pump_telemetry(dataset: pl.LazyFrame, features: list[str]) -> None:
    """Write calculated telemetry features as JSON to standard output.

    Parameters
    ----------
    dataset
        Dataset containing the calculated telemetry features.
    features
        Names of the feature columns to write.

    Returns:
    -------
    This mock sink discards the dataset.

    Examples:
    --------
    >>> write_pump_telemetry(pl.LazyFrame({"efficiency": [0.5]}), ["efficiency"])
    """
    return


@function(kind="collapse")
def aggregate(
    dataset: pl.LazyFrame, feature: str, method: str, dimensions: list[str], output: str
) -> pl.LazyFrame:
    """Return a dimension-keyed aggregate fragment at the requested grain.

    Parameters
    ----------
    dataset
        Dataset to aggregate.
    feature
        Name of the column to aggregate.
    method
        Aggregation method; one of ``"max"``, ``"min"``, ``"mean"``, or
        ``"sum"``.
    dimensions
        Dimension columns defining the aggregation grain. When empty,
        the aggregate is computed over the whole dataset.
    output
        Name of the resulting aggregate column.

    Returns:
    -------
    Aggregated fragment keyed by the requested dimensions.

    Raises:
    ------
    ValueError
        If ``method`` is not a supported aggregation method.

    Examples:
    --------
    >>> frame = pl.LazyFrame({"pump": ["p1", "p1"], "flow": [1.0, 3.0]})
    >>> aggregate(frame, "flow", "max", [], "max_flow").collect().to_dicts()
    [{'max_flow': 3.0}]
    """
    if method not in SUPPORTED_AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation method: {method}")
    expression = getattr(pl.col(feature), method)().alias(output)
    data_collapsed = (
        dataset.group_by(dimensions).agg(expression) if dimensions else dataset.select(expression)
    )
    return data_collapsed


@function(kind="vectorize")
def delta(
    dataset: pl.LazyFrame,
    feature: str,
    partition_by: list[str],
    order_by: str,
    output: str,
) -> pl.LazyFrame:
    """Return the ordered difference from the previous row within each partition.

    Parameters
    ----------
    dataset
        Dataset containing the readings.
    feature
        Name of the column to difference.
    partition_by
        Columns identifying each partition.
    order_by
        Column defining the ordering within each partition.
    output
        Name of the resulting difference column.

    Returns:
    -------
    Dataset with the ordered difference appended.

    Examples:
    --------
    >>> frame = pl.LazyFrame({"pump": ["p1", "p1"], "ts": [1, 2], "temp": [60.0, 61.5]})
    >>> delta(frame, "temp", ["pump"], "ts", "temp_delta").collect()["temp_delta"].to_list()
    [None, 1.5]
    """
    data_vectorized = dataset.with_columns(
        pl.col(feature).diff().over(partition_by, order_by=order_by).alias(output)
    )
    return data_vectorized


@function(kind="vectorize")
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
        Dataset containing the numerator and denominator columns.
    numerator_features
        Names of the columns multiplied into the numerator.
    denominator_features
        Names of the columns multiplied into the denominator.
    output
        Name of the resulting ratio column.
    scale
        Constant factor applied to the ratio, for example a unit
        conversion. Defaults to ``1.0``.

    Returns:
    -------
    Dataset with the scaled ratio appended.

    Examples:
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


@function(kind="vectorize")
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
        Dataset containing the struct column.
    field
        Name of the struct field to extract.
    column
        Name of the struct column.
    output
        Name of the resulting extracted column.

    Returns:
    -------
    Dataset with the extracted field appended.

    Examples:
    --------
    >>> frame = pl.LazyFrame({"recommendation": [{"converged": True}]})
    >>> extract_field(frame, "converged", "recommendation", "ok").collect()["ok"].to_list()
    [True]
    """
    data_vectorized = dataset.with_columns(pl.col(column).struct.field(field).alias(output))
    return data_vectorized


@function(kind="vectorize")
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
        Dataset containing the column to scale.
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

    Returns:
    -------
    Dataset with the scaled column appended.

    Examples:
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


@function(kind="vectorize")
def optimize_pump_operating_point(
    dataset: pl.LazyFrame, optimization_features: list[str], output: str
) -> pl.LazyFrame:
    """Return recommended operating values and convergence as a struct column.

    Parameters
    ----------
    dataset
        Dataset containing the pump operating measurements.
    optimization_features
        Names of the pressure, flow, power, temperature, and vibration
        columns, in that order.
    output
        Name of the resulting struct column.

    Returns:
    -------
    Dataset with the recommendation struct appended.

    Examples:
    --------
    >>> frame = pl.LazyFrame(
    ...     {"pressure": [4.0], "flow": [10.0], "power": [5.0], "temp": [80.0], "vib": [3.0]}
    ... )
    >>> features = ["pressure", "flow", "power", "temp", "vib"]
    >>> result = optimize_pump_operating_point(frame, features, "recommendation")
    >>> result.collect()["recommendation"].to_list()[0]["converged"]
    True
    """
    pressure, flow, power, temperature, vibration = map(pl.col, optimization_features)
    expression = pl.struct(
        recommended_flow_rate=flow,
        recommended_discharge_pressure=pressure,
        energy_cost_score=power / flow,
        converged=(temperature < 90.0) & (vibration < 4.5),
    )
    data_vectorized = dataset.with_columns(expression.alias(output))
    return data_vectorized


@function(kind="vectorize")
def pump_health_score(
    dataset: pl.LazyFrame, health_features: list[str], output: str
) -> pl.LazyFrame:
    """Return efficiency reduced by temperature and vibration deterioration.

    Parameters
    ----------
    dataset
        Dataset containing the health input features.
    health_features
        Names of the temperature-delta, vibration-delta, and efficiency
        columns, in that order.
    output
        Name of the resulting health-score column.

    Returns:
    -------
    Dataset with the health score appended.

    Examples:
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
