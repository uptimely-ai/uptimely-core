"""Minute-level cooling-pump telemetry profile."""

import pump_analytics as analytics
import pump_io as io
from spec import dimension

from uptimely import (
    Bind,
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
    seed = "read_pump_telemetry"

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
                compute=Bind(
                    io.read_pump_telemetry,
                    pump_telemetry_source=ref.paths("telemetry_source"),
                    pump_source=ref.paths("pump_assets_source"),
                ),
            ),
        ],
        calculations=[
            Operator(
                compute=Bind(
                    analytics.pump_mode,
                    dataset=ref.dataset(),
                    bearing_temperature=ref.input("bearing_temperature"),
                    vibration_rms=ref.input("vibration_rms"),
                    output=ref.output("pump_mode"),
                    bearing_temperature_warning_limit=90.0,
                    vibration_warning_limit=4.5,
                ),
            ),
            Operator(
                compute=Bind(
                    analytics.ratio,
                    dataset=ref.dataset(),
                    numerator_features=[
                        ref.input("differential_pressure"),
                        ref.input("flow_rate"),
                    ],
                    denominator_features=[ref.input("motor_power")],
                    scale=HYDRAULIC_POWER_SCALE,
                    output=ref.output("pressure_flow_efficiency"),
                ),
            ),
            Operator(
                compute=Bind(
                    analytics.select_columns,
                    dataset=ref.dataset("constants"),
                    columns=[ref.input("room_temperature")],
                    rename={"room_temperature": ref.output("room_temperature_reference")},
                ),
                merge=merge.default(),
            ),
            Operator(
                compute=Bind(
                    analytics.subtract,
                    dataset=ref.dataset(),
                    feature=ref.input("bearing_temperature"),
                    subtrahend=ref.input("room_temperature_reference"),
                    output=ref.output("bearing_temperature_rise"),
                ),
            ),
            Operator(
                row_context=RowContext(before=1),
                compute=Bind(
                    analytics.delta,
                    dataset=ref.dataset(),
                    feature=ref.input("bearing_temperature"),
                    partition_by=[ref.dimension("machine_dimension").resolution("machine").key],
                    order_by=ref.dimension("machine_timestamp").resolution("timestamp").key,
                    num_rows=ref.row_context("before"),
                    output=ref.output("bearing_temperature_delta"),
                ),
            ),
            Operator(
                row_context=RowContext(before=1),
                compute=Bind(
                    analytics.delta,
                    dataset=ref.dataset(),
                    feature=ref.input("vibration_rms"),
                    partition_by=[ref.dimension("machine_dimension").resolution("machine").key],
                    order_by=ref.dimension("machine_timestamp").resolution("timestamp").key,
                    num_rows=ref.row_context("before"),
                    output=ref.output("vibration_delta"),
                ),
            ),
            Operator(
                compute=Bind(
                    analytics.pump_health_score,
                    dataset=ref.dataset(),
                    health_features=[
                        ref.input("bearing_temperature_delta"),
                        ref.input("vibration_delta"),
                        ref.input("pressure_flow_efficiency"),
                    ],
                    output=ref.output("pump_health_score"),
                ),
            ),
        ],
        publishing=[
            Operator(
                compute=Bind(
                    io.write_file,
                    dataset=ref.dataset(),
                    features=[
                        ref.input("mode"),
                        ref.input("pump_mode"),
                        ref.input("differential_pressure"),
                        ref.input("flow_rate"),
                        ref.input("bearing_temperature"),
                        ref.input("vibration_rms"),
                        ref.input("motor_power"),
                        ref.input("pressure_flow_efficiency"),
                        ref.input("room_temperature_reference"),
                        ref.input("bearing_temperature_rise"),
                        ref.input("bearing_temperature_delta"),
                        ref.input("vibration_delta"),
                        ref.input("pump_health_score"),
                    ],
                    output=ref.paths("pump_telemetry_output"),
                ),
            )
        ],
    )
