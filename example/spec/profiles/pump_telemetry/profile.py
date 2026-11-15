"""Minute-level cooling-pump telemetry profile."""

import pump_analytics as analytics
import pump_io as io
from spec import dimension

from uptimely import (
    Binding,
    Operator,
    Order,
    Profile,
    merge,
    ref,
)
from uptimely.spec.row_context import RowContext

from .features import TelemetryFeatures

HYDRAULIC_POWER_SCALE = 1.0 / 36.0
"""Converts bar * m3/h into kW for the hydraulic-power numerator."""


class PumpTelemetry(Profile):
    """Cooling-water and condition readings at pump-and-timestamp grain."""

    id = "pump_telemetry"
    name = "Telemetry"
    description = (
        "Cooling-water and condition readings from data-center pumps, sampled "
        "at one-minute intervals."
    )
    category = "Telemetry"
    grain = [
        dimension.MACHINE_DIMENSION.resolution("machine"),
        dimension.MACHINE_TIMESTAMP.resolution("timestamp"),
    ]
    relations = [
        dimension.FACILITY_DIMENSION.resolution("server_room"),
        dimension.FACILITY_DIMENSION.resolution("data_center"),
        dimension.MACHINE_DIMENSION.resolution("machine_series"),
        dimension.MACHINE_DIMENSION.resolution("machine_category"),
        dimension.MACHINE_TIMESTAMP.resolution("minute"),
        dimension.MACHINE_TIMESTAMP.resolution("hour"),
        dimension.MACHINE_TIMESTAMP.resolution("day"),
    ]
    scope = "Synthetic data-center cooling pump telemetry for demonstration"
    order = (Order(dimension.MACHINE_TIMESTAMP, "timestamp", direction="asc"),)
    features = TelemetryFeatures()

    assembly = dict(
        ingestion=[
            Operator(
                id="read_pump_telemetry",
                outputs=[
                    features.differential_pressure,
                    features.flow_rate,
                    features.bearing_temperature,
                    features.vibration_rms,
                    features.motor_power,
                    features.mode,
                ],
                read=Binding(
                    io.read_pump_telemetry,
                    pump_telemetry_source=ref.paths("telemetry_source"),
                    pump_source=ref.paths("pump_assets_source"),
                ),
                merge=merge.default(),
            ),
        ],
        calculations=[
            Operator(
                outputs=[features.pump_mode],
                compute=Binding(
                    analytics.pump_mode,
                    dataset=ref.dataset(),
                    bearing_temperature=features.bearing_temperature,
                    vibration_rms=features.vibration_rms,
                    output=features.pump_mode,
                    bearing_temperature_warning_limit=90.0,
                    vibration_warning_limit=4.5,
                ),
            ),
            Operator(
                outputs=[features.pressure_flow_efficiency],
                compute=Binding(
                    analytics.ratio,
                    dataset=ref.dataset(),
                    numerator_features=[
                        features.differential_pressure,
                        features.flow_rate,
                    ],
                    denominator_features=[features.motor_power],
                    scale=HYDRAULIC_POWER_SCALE,
                    output=features.pressure_flow_efficiency,
                ),
            ),
            Operator(
                outputs=[features.room_temperature_reference],
                stage=Binding(
                    analytics.select_columns,
                    dataset=ref.dataset("constants"),
                    columns=[ref.feature("room_temperature")],
                    rename={"room_temperature": features.room_temperature_reference},
                ),
                merge=merge.default(),
            ),
            Operator(
                outputs=[features.bearing_temperature_rise],
                compute=Binding(
                    analytics.subtract,
                    dataset=ref.dataset(),
                    feature=features.bearing_temperature,
                    subtrahend=features.room_temperature_reference,
                    output=features.bearing_temperature_rise,
                ),
            ),
            Operator(
                outputs=[features.bearing_temperature_delta],
                row_context=RowContext(before=1),
                compute=Binding(
                    analytics.delta,
                    dataset=ref.dataset(),
                    feature=features.bearing_temperature,
                    partition_by=[ref.dimension("machine_dimension").resolution("machine").key],
                    order_by=ref.dimension("machine_timestamp").resolution("timestamp").key,
                    num_rows=ref.row_context("before"),
                    output=features.bearing_temperature_delta,
                ),
            ),
            Operator(
                outputs=[features.vibration_delta],
                row_context=RowContext(before=1),
                compute=Binding(
                    analytics.delta,
                    dataset=ref.dataset(),
                    feature=features.vibration_rms,
                    partition_by=[ref.dimension("machine_dimension").resolution("machine").key],
                    order_by=ref.dimension("machine_timestamp").resolution("timestamp").key,
                    num_rows=ref.row_context("before"),
                    output=features.vibration_delta,
                ),
            ),
            Operator(
                outputs=[features.pump_health_score],
                compute=Binding(
                    analytics.pump_health_score,
                    dataset=ref.dataset(),
                    health_features=[
                        features.bearing_temperature_delta,
                        features.vibration_delta,
                        features.pressure_flow_efficiency,
                    ],
                    output=features.pump_health_score,
                ),
            ),
        ],
        publishing=[
            Operator(
                outputs=[],
                write=Binding(
                    io.write_file,
                    dataset=ref.dataset(),
                    features=[
                        features.mode,
                        features.pump_mode,
                        features.differential_pressure,
                        features.flow_rate,
                        features.bearing_temperature,
                        features.vibration_rms,
                        features.motor_power,
                        features.pressure_flow_efficiency,
                        features.room_temperature_reference,
                        features.bearing_temperature_rise,
                        features.bearing_temperature_delta,
                        features.vibration_delta,
                        features.pump_health_score,
                    ],
                    output=ref.paths("pump_telemetry_output"),
                ),
            )
        ],
    )
