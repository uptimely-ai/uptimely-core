"""Calculation functions for computing derived features and health metrics."""

import polars as pl


def maximum(
    dataset: pl.LazyFrame, feature: str, dimensions: list[str], output: str
) -> pl.LazyFrame:
    """Return a dimension-keyed maximum fragment at the requested grain."""
    expression = pl.col(feature).max().alias(output)
    return (
        dataset.group_by(dimensions).agg(expression) if dimensions else dataset.select(expression)
    )


def bearing_temperature_delta(
    temperature: str,
    partition_by: list[str],
    order_by: str,
    dataset: pl.LazyFrame,
    output: str,
) -> pl.LazyFrame:
    """Return the ordered bearing-temperature difference within each asset."""
    return dataset.with_columns(
        pl.col(temperature).diff().over(partition_by, order_by=order_by).alias(output)
    )


def converged(
    recommendation_features: list[str], dataset: pl.LazyFrame, output: str
) -> pl.LazyFrame:
    """Return the convergence boolean from the recommendation struct column."""
    recommendation = pl.col(recommendation_features[0])
    return dataset.with_columns(recommendation.struct.field("converged").alias(output))


def extract_recommendation_value(
    optimization_attribute: str,
    column: str,
    dataset: pl.LazyFrame,
    output: str,
) -> pl.LazyFrame:
    """Return the requested field from the recommendation struct column."""
    return dataset.with_columns(pl.col(column).struct.field(optimization_attribute).alias(output))


def normalize_health_signal(
    scale_feature: str,
    lower_bound: float,
    upper_bound: float,
    scaling_features: list[str],
    dataset: pl.LazyFrame,
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
    return dataset.with_columns(expression.alias(output))


def optimize_pump_operating_point(
    optimization_features: list[str], dataset: pl.LazyFrame, output: str
) -> pl.LazyFrame:
    """Return recommended operating values and convergence as a struct column."""
    pressure, flow, power, temperature, vibration = map(pl.col, optimization_features)
    expression = pl.struct(
        recommended_flow_rate=flow,
        recommended_discharge_pressure=pressure,
        energy_cost_score=power / flow,
        converged=(temperature < 90.0) & (vibration < 4.5),
    )
    return dataset.with_columns(expression.alias(output))


def pressure_flow_efficiency(
    pressure_features: list[str], dataset: pl.LazyFrame, output: str
) -> pl.LazyFrame:
    """Return hydraulic power divided by electrical motor power."""
    pressure, flow, power = map(pl.col, pressure_features)
    return dataset.with_columns((pressure * flow / (36.0 * power)).alias(output))


def pump_health_score(
    health_features: list[str], dataset: pl.LazyFrame, output: str
) -> pl.LazyFrame:
    """Return efficiency reduced by temperature and vibration deterioration."""
    temperature_delta, vibration_delta, efficiency = map(pl.col, health_features)
    return dataset.with_columns(
        (efficiency - temperature_delta.abs() / 10.0 - vibration_delta.abs() / 2.0).alias(output)
    )


def vibration_delta_from_previous(
    vibration: str,
    partition_by: list[str],
    order_by: str,
    dataset: pl.LazyFrame,
    output: str,
) -> pl.LazyFrame:
    """Return the ordered vibration difference within each asset."""
    return dataset.with_columns(
        pl.col(vibration).diff().over(partition_by, order_by=order_by).alias(output)
    )
