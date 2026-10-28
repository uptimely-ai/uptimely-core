"""Analytical, source, and sink functions for pump telemetry."""

import polars as pl

from uptimely.spec.python import kind


@kind("read")
def read_pump_telemetry(
    source: str,
    production_line: str | None = None,
    environment: str = "development",
) -> pl.LazyFrame:
    """Load telemetry for an optional production line from a mock environment."""
    if environment not in {"development", "qa", "production"}:
        raise ValueError(f"Unsupported environment: {environment}")

    data_read = (
        pl.read_json(source)
        .lazy()
        .with_columns(pl.col("timestamp").str.to_datetime(time_zone="UTC"))
    )
    if production_line:
        data_read = data_read.filter(pl.col("production_line") == production_line)
    return data_read


@kind("write")
def write_pump_telemetry(dataset: pl.LazyFrame, features: list[str]) -> None:
    """Write calculated telemetry features as JSON to standard output."""
    return


@kind("collapse")
def maximum(
    dataset: pl.LazyFrame, feature: str, dimensions: list[str], output: str
) -> pl.LazyFrame:
    """Return a dimension-keyed maximum fragment at the requested grain."""
    expression = pl.col(feature).max().alias(output)
    data_collapsed = (
        dataset.group_by(dimensions).agg(expression) if dimensions else dataset.select(expression)
    )
    return data_collapsed


@kind("vectorize")
def bearing_temperature_delta(
    dataset: pl.LazyFrame,
    temperature: str,
    partition_by: list[str],
    order_by: str,
    output: str,
) -> pl.LazyFrame:
    """Return the ordered bearing-temperature difference within each asset."""
    data_vectorized = dataset.with_columns(
        pl.col(temperature).diff().over(partition_by, order_by=order_by).alias(output)
    )
    return data_vectorized


@kind("vectorize")
def extract_recommendation_value(
    dataset: pl.LazyFrame,
    optimization_attribute: str,
    column: str,
    output: str,
) -> pl.LazyFrame:
    """Return the requested field from the recommendation struct column."""
    data_vectorized = dataset.with_columns(
        pl.col(column).struct.field(optimization_attribute).alias(output)
    )
    return data_vectorized


@kind("vectorize")
def normalize_health_signal(
    dataset: pl.LazyFrame,
    scale_feature: str,
    lower_bound: float,
    upper_bound: float,
    scaling_features: list[str],
    output: str,
) -> pl.LazyFrame:
    """Return a min-max-scaled health signal with a stable constant-data value."""
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


@kind("vectorize")
def optimize_pump_operating_point(
    dataset: pl.LazyFrame, optimization_features: list[str], output: str
) -> pl.LazyFrame:
    """Return recommended operating values and convergence as a struct column."""
    pressure, flow, power, temperature, vibration = map(pl.col, optimization_features)
    expression = pl.struct(
        recommended_flow_rate=flow,
        recommended_discharge_pressure=pressure,
        energy_cost_score=power / flow,
        converged=(temperature < 90.0) & (vibration < 4.5),
    )
    data_vectorized = dataset.with_columns(expression.alias(output))
    return data_vectorized


@kind("vectorize")
def pressure_flow_efficiency(
    dataset: pl.LazyFrame, pressure_features: list[str], output: str
) -> pl.LazyFrame:
    """Return hydraulic power divided by electrical motor power."""
    pressure, flow, power = map(pl.col, pressure_features)
    data_vectorized = dataset.with_columns((pressure * flow / (36.0 * power)).alias(output))
    return data_vectorized


@kind("vectorize")
def pump_health_score(
    dataset: pl.LazyFrame, health_features: list[str], output: str
) -> pl.LazyFrame:
    """Return efficiency reduced by temperature and vibration deterioration."""
    temperature_delta, vibration_delta, efficiency = map(pl.col, health_features)
    data_vectorized = dataset.with_columns(
        (efficiency - temperature_delta.abs() / 10.0 - vibration_delta.abs() / 2.0).alias(output)
    )
    return data_vectorized


@kind("vectorize")
def vibration_delta_from_previous(
    dataset: pl.LazyFrame,
    vibration: str,
    partition_by: list[str],
    order_by: str,
    output: str,
) -> pl.LazyFrame:
    """Return the ordered vibration difference within each asset."""
    data_vectorized = dataset.with_columns(
        pl.col(vibration).diff().over(partition_by, order_by=order_by).alias(output)
    )
    return data_vectorized
