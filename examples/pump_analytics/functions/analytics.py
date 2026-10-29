"""Analytical, source, and sink functions for pump telemetry."""

import polars as pl

from uptimely import function


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
def maximum(
    dataset: pl.LazyFrame, feature: str, dimensions: list[str], output: str
) -> pl.LazyFrame:
    """Return a dimension-keyed maximum fragment at the requested grain.

    Parameters
    ----------
    dataset
        Dataset to aggregate.
    feature
        Name of the column to take the maximum of.
    dimensions
        Dimension columns defining the aggregation grain. When empty,
        the maximum is computed over the whole dataset.
    output
        Name of the resulting aggregate column.

    Returns:
    -------
    Aggregated fragment keyed by the requested dimensions.

    Examples:
    --------
    >>> frame = pl.LazyFrame({"pump": ["p1", "p1"], "flow": [1.0, 3.0]})
    >>> maximum(frame, "flow", [], "max_flow").collect().to_dicts()
    [{'max_flow': 3.0}]
    """
    expression = pl.col(feature).max().alias(output)
    data_collapsed = (
        dataset.group_by(dimensions).agg(expression) if dimensions else dataset.select(expression)
    )
    return data_collapsed


@function(kind="vectorize")
def bearing_temperature_delta(
    dataset: pl.LazyFrame,
    temperature: str,
    partition_by: list[str],
    order_by: str,
    output: str,
) -> pl.LazyFrame:
    """Return the ordered bearing-temperature difference within each asset.

    Parameters
    ----------
    dataset
        Dataset containing the bearing-temperature readings.
    temperature
        Name of the bearing-temperature column.
    partition_by
        Columns identifying each asset partition.
    order_by
        Column defining the ordering within each partition.
    output
        Name of the resulting difference column.

    Returns:
    -------
    Dataset with the ordered temperature difference appended.

    Examples:
    --------
    >>> frame = pl.LazyFrame({"pump": ["p1", "p1"], "ts": [1, 2], "temp": [60.0, 61.5]})
    >>> bearing_temperature_delta(frame, "temp", ["pump"], "ts", "delta").collect()[
    ...     "delta"
    ... ].to_list()
    [None, 1.5]
    """
    data_vectorized = dataset.with_columns(
        pl.col(temperature).diff().over(partition_by, order_by=order_by).alias(output)
    )
    return data_vectorized


@function(kind="vectorize")
def extract_recommendation_value(
    dataset: pl.LazyFrame,
    optimization_attribute: str,
    column: str,
    output: str,
) -> pl.LazyFrame:
    """Return the requested field from the recommendation struct column.

    Parameters
    ----------
    dataset
        Dataset containing the recommendation struct column.
    optimization_attribute
        Name of the struct field to extract.
    column
        Name of the struct column holding the recommendations.
    output
        Name of the resulting extracted column.

    Returns:
    -------
    Dataset with the extracted field appended.

    Examples:
    --------
    >>> frame = pl.LazyFrame({"recommendation": [{"converged": True}]})
    >>> extract_recommendation_value(frame, "converged", "recommendation", "ok").collect()[
    ...     "ok"
    ... ].to_list()
    [True]
    """
    data_vectorized = dataset.with_columns(
        pl.col(column).struct.field(optimization_attribute).alias(output)
    )
    return data_vectorized


@function(kind="vectorize")
def normalize_health_signal(
    dataset: pl.LazyFrame,
    scale_feature: str,
    lower_bound: float,
    upper_bound: float,
    scaling_features: list[str],
    output: str,
) -> pl.LazyFrame:
    """Return a min-max-scaled health signal with a stable constant-data value.

    Parameters
    ----------
    dataset
        Dataset containing the health signal.
    scale_feature
        Name of the column to scale.
    lower_bound
        Lower bound of the scaled range; also used when the input
        column is constant.
    upper_bound
        Upper bound of the scaled range.
    scaling_features
        Declared feature dependencies; unused by the calculation.
    output
        Name of the resulting scaled column.

    Returns:
    -------
    Dataset with the scaled health signal appended.

    Examples:
    --------
    >>> frame = pl.LazyFrame({"score": [0.0, 5.0, 10.0]})
    >>> normalize_health_signal(frame, "score", 0.0, 1.0, [], "scaled").collect()[
    ...     "scaled"
    ... ].to_list()
    [0.0, 0.5, 1.0]
    """
    _ = scaling_features
    feature = pl.col(scale_feature)
    minimum = feature.min()
    spread = feature.max() - minimum
    expression = (
        pl.when(spread == 0)
        .then(pl.lit(lower_bound))
        .otherwise(lower_bound + (feature - minimum) * (upper_bound - lower_bound) / spread)
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
def pressure_flow_efficiency(
    dataset: pl.LazyFrame, pressure_features: list[str], output: str
) -> pl.LazyFrame:
    """Return hydraulic power divided by electrical motor power.

    Parameters
    ----------
    dataset
        Dataset containing the pressure, flow, and power measurements.
    pressure_features
        Names of the pressure, flow, and power columns, in that order.
    output
        Name of the resulting efficiency column.

    Returns:
    -------
    Dataset with the efficiency ratio appended.

    Examples:
    --------
    >>> frame = pl.LazyFrame({"pressure": [3.6], "flow": [10.0], "power": [2.0]})
    >>> pressure_flow_efficiency(frame, ["pressure", "flow", "power"], "efficiency").collect()[
    ...     "efficiency"
    ... ].to_list()
    [0.5]
    """
    pressure, flow, power = map(pl.col, pressure_features)
    data_vectorized = dataset.with_columns((pressure * flow / (36.0 * power)).alias(output))
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


@function(kind="vectorize")
def vibration_delta_from_previous(
    dataset: pl.LazyFrame,
    vibration: str,
    partition_by: list[str],
    order_by: str,
    output: str,
) -> pl.LazyFrame:
    """Return the ordered vibration difference within each asset.

    Parameters
    ----------
    dataset
        Dataset containing the vibration readings.
    vibration
        Name of the vibration column.
    partition_by
        Columns identifying each asset partition.
    order_by
        Column defining the ordering within each partition.
    output
        Name of the resulting difference column.

    Returns:
    -------
    Dataset with the ordered vibration difference appended.

    Examples:
    --------
    >>> frame = pl.LazyFrame({"pump": ["p1", "p1"], "ts": [1, 2], "vib": [2.0, 3.5]})
    >>> vibration_delta_from_previous(frame, "vib", ["pump"], "ts", "delta").collect()[
    ...     "delta"
    ... ].to_list()
    [None, 1.5]
    """
    data_vectorized = dataset.with_columns(
        pl.col(vibration).diff().over(partition_by, order_by=order_by).alias(output)
    )
    return data_vectorized
