"""Calculation functions for computing derived features and health metrics."""

import polars as pl


def aggregate_by_dimension(
    dataset: pl.LazyFrame,
    dimensions: list[str],
    aggregations: dict[str, pl.Expr],
) -> pl.LazyFrame:
    """Collapse a dataset by dimensions using generated feature expressions."""
    return dataset.group_by(dimensions).agg(list(aggregations.values()))


def maximum(feature: str) -> pl.Expr:
    """Generate a maximum expression from a source feature."""
    return pl.col(feature).max()


def bearing_temperature_delta(
    temperature: str,
    partition_by: list[str],
    order_by: str,
) -> pl.Expr:
    """Return the ordered bearing-temperature difference within each asset."""
    return pl.col(temperature).diff().over(partition_by, order_by=order_by)


def converged(recommendation_features: list[str]) -> pl.Expr:
    """Return the convergence boolean from the recommendation struct column."""
    recommendation = pl.col(recommendation_features[0])
    return recommendation.struct.field("converged")


def extract_recommendation_value(
    optimization_attribute: str,
    column: str,
) -> pl.Expr:
    """Return the requested field from the recommendation struct column."""
    return pl.col(column).struct.field(optimization_attribute)


def normalize_health_signal(
    scale_feature: str,
    lower_bound: float,
    upper_bound: float,
    scaling_features: list[str],
) -> pl.Expr:
    """Return a min-max-scaled health signal with a stable constant-data value."""
    _ = scaling_features
    feature = pl.col(scale_feature)
    minimum = feature.min()
    spread = feature.max() - minimum
    return (
        pl.when(spread == 0)
        .then(pl.lit(lower_bound))
        .otherwise(lower_bound + (feature - minimum) * (upper_bound - lower_bound) / spread)
    )


def optimize_pump_operating_point(optimization_features: list[str]) -> pl.Expr:
    """Return recommended operating values and convergence as a struct column."""
    pressure, flow, power, temperature, vibration = map(pl.col, optimization_features)
    return pl.struct(
        recommended_flow_rate=flow,
        recommended_discharge_pressure=pressure,
        energy_cost_score=power / flow,
        converged=(temperature < 90.0) & (vibration < 4.5),
    )


def pressure_flow_efficiency(pressure_features: list[str]) -> pl.Expr:
    """Return hydraulic power divided by electrical motor power."""
    pressure, flow, power = map(pl.col, pressure_features)
    return pressure * flow / (36.0 * power)


def pump_health_score(health_features: list[str]) -> pl.Expr:
    """Return efficiency reduced by temperature and vibration deterioration."""
    temperature_delta, vibration_delta, efficiency = map(pl.col, health_features)
    return efficiency - temperature_delta.abs() / 10.0 - vibration_delta.abs() / 2.0


def vibration_delta_from_previous(
    vibration: str,
    partition_by: list[str],
    order_by: str,
) -> pl.Expr:
    """Return the ordered vibration difference within each asset."""
    return pl.col(vibration).diff().over(partition_by, order_by=order_by)
