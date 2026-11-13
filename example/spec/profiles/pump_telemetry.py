"""Minute-level cooling-pump telemetry and dataframe transformations."""

import polars as pl
from example.spec import dimension
from example.src import analytics, io

from uptimely import (
    Binding,
    Feature,
    FeatureSet,
    Interface,
    Operator,
    Order,
    Profile,
    merge,
    ref,
)
from uptimely.spec.row_context import RowContext

HYDRAULIC_POWER_SCALE = 1.0 / 36.0
"""Converts bar * m3/h into kW for the hydraulic-power numerator."""


class TelemetryFeatures(FeatureSet):
    """Features declared by the cooling-pump telemetry profile."""

    differential_pressure = Feature(
        type="float",
        unit="bar",
        description="Differential pressure across the cooling-water pump.",
    )
    flow_rate = Feature(
        type="float",
        unit="m3/h",
        description="Cooling-water circulation flow rate.",
    )
    bearing_temperature = Feature(
        type="float",
        unit="C",
        description="Drive-end motor-bearing temperature.",
    )
    vibration_rms = Feature(
        type="float",
        unit="mm/s",
        description="Overall cooling-pump vibration RMS.",
    )
    motor_power = Feature(
        type="float",
        unit="kW",
        description="Active electric power consumed by the cooling-pump motor.",
    )
    mode = Feature(
        type="string",
        description=(
            "Flow band: below_rated_flow or at_or_above_rated_flow, based on rated "
            "cooling-water flow."
        ),
    )
    pump_mode = Feature(
        type="string",
        description=(
            "Illustrative condition mode: warning when bearing temperature is at least "
            "90 C or vibration is at least 4.5 mm/s, otherwise operational. Null for "
            "incomplete or non-finite readings unless a warning is established."
        ),
    )
    recommended_flow_rate = Feature(
        type="float",
        unit="m3/h",
        description="Illustrative recommended cooling-water flow rate.",
    )
    recommended_differential_pressure = Feature(
        type="float",
        unit="bar",
        description="Illustrative recommended differential pressure across the pump.",
    )
    energy_cost_score = Feature(
        type="float",
        description="Estimated energy-cost score for the recommended operating point",
    )
    converged = Feature(
        type="boolean",
        description="Whether the optimization converged",
    )
    pressure_flow_efficiency = Feature(
        type="float",
        description=(
            "Hydraulic efficiency proxy from cooling-water differential pressure, "
            "flow, and motor power."
        ),
    )
    room_temperature_reference = Feature(
        type="float",
        unit="C",
        description="Pump-room ambient-temperature reference broadcast to each row.",
    )
    bearing_temperature_rise = Feature(
        type="float",
        unit="C",
        description="Motor-bearing temperature rise above the pump-room ambient reference.",
    )
    bearing_temperature_delta = Feature(
        type="float",
        unit="C",
        description="Motor-bearing temperature change from the previous pump reading.",
    )
    vibration_delta = Feature(
        unit="mm/s",
        description="Vibration change from the previous cooling-pump reading.",
    )
    pump_health_score = Feature(
        type="float",
        description=(
            "Illustrative cooling-pump condition score from motor-bearing temperature "
            "trend, vibration trend, and hydraulic efficiency proxy."
        ),
    )
    operating_point_recommendation = Feature(
        type="object",
        description=(
            "Illustrative cooling-pump operating point based on flow, differential "
            "pressure, power, temperature, and vibration."
        ),
    )


class PumpTelemetry(Profile):
    """Cooling-water and condition readings at pump-and-timestamp grain."""

    id = "pump_telemetry"
    name = "Cooling Pump Telemetry"
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
                interface=Interface(
                    outputs=[
                        features.differential_pressure,
                        features.flow_rate,
                        features.bearing_temperature,
                        features.vibration_rms,
                        features.motor_power,
                        features.mode,
                    ],
                ),
                compute=Binding(
                    function=io.read_pump_telemetry,
                    arguments=dict(
                        pump_telemetry_source=ref.paths("telemetry_source"),
                        pump_source=ref.paths("pump_assets_source"),
                    ),
                ),
                merge=merge.default(),
            ),
        ],
        calculations=[
            Operator(
                id="pump_mode",
                interface=Interface(
                    outputs=[features.pump_mode],
                ),
                compute=Binding(
                    function=analytics.pump_mode,
                    arguments=dict(
                        dataset=ref.dataset(),
                        bearing_temperature=features.bearing_temperature,
                        vibration_rms=features.vibration_rms,
                        output=features.pump_mode,
                        bearing_temperature_warning_limit=90.0,
                        vibration_warning_limit=4.5,
                    ),
                ),
            ),
            Operator(
                id="recommended_flow_rate",
                interface=Interface(
                    outputs=[features.recommended_flow_rate],
                ),
                # A shortcut to bind a 3rd party function directly
                compute=Binding(
                    function=ref.function(
                        pl.LazyFrame.with_columns,
                        returns="dataframe",
                        args={"self": "dataframe", "recommended_flow_rate": "string"},
                        validate_signature=False,
                    ),
                    arguments=dict(
                        self=ref.dataset(),
                        recommended_flow_rate=features.flow_rate,
                    ),
                ),
            ),
            Operator(
                id="recommended_differential_pressure",
                interface=Interface(
                    outputs=[features.recommended_differential_pressure],
                ),
                compute=Binding(
                    function=analytics.extract_field,
                    arguments=dict(
                        dataset=ref.dataset(),
                        column=features.operating_point_recommendation,
                        field="recommended_differential_pressure",
                        output=features.recommended_differential_pressure,
                    ),
                ),
            ),
            Operator(
                id="energy_cost_score",
                interface=Interface(
                    outputs=[features.energy_cost_score],
                ),
                compute=Binding(
                    function=analytics.extract_field,
                    arguments=dict(
                        dataset=ref.dataset(),
                        column=features.operating_point_recommendation,
                        field="energy_cost_score",
                        output=features.energy_cost_score,
                    ),
                ),
            ),
            Operator(
                id="converged",
                interface=Interface(
                    outputs=[features.converged],
                ),
                compute=Binding(
                    function=analytics.extract_field,
                    arguments=dict(
                        dataset=ref.dataset(),
                        column=features.operating_point_recommendation,
                        field="converged",
                        output=features.converged,
                    ),
                ),
            ),
            Operator(
                id="pressure_flow_efficiency",
                interface=Interface(
                    outputs=[features.pressure_flow_efficiency],
                ),
                compute=Binding(
                    function=analytics.ratio,
                    arguments=dict(
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
            ),
            Operator(
                id="room_temperature_reference",
                interface=Interface(
                    outputs=[features.room_temperature_reference],
                ),
                compute=Binding(
                    function=analytics.select_columns,
                    arguments=dict(
                        dataset=ref.dataset("constants"),
                        columns=[ref.feature("room_temperature")],
                        rename={"room_temperature": features.room_temperature_reference},
                    ),
                ),
                merge=merge.default(),
            ),
            Operator(
                id="bearing_temperature_rise",
                interface=Interface(
                    outputs=[features.bearing_temperature_rise],
                ),
                compute=Binding(
                    function=analytics.subtract,
                    arguments=dict(
                        dataset=ref.dataset(),
                        feature=features.bearing_temperature,
                        subtrahend=features.room_temperature_reference,
                        output=features.bearing_temperature_rise,
                    ),
                ),
            ),
            Operator(
                id="bearing_temperature_delta",
                interface=Interface(
                    outputs=[features.bearing_temperature_delta],
                ),
                row_context=RowContext(before=1),
                compute=Binding(
                    function=analytics.delta,
                    arguments=dict(
                        dataset=ref.dataset(),
                        feature=features.bearing_temperature,
                        partition_by=[ref.dimension("machine_dimension").resolution("machine").key],
                        order_by=ref.dimension("machine_timestamp").resolution("timestamp").key,
                        num_rows=ref.row_context("before"),
                        output=features.bearing_temperature_delta,
                    ),
                ),
            ),
            Operator(
                id="vibration_delta",
                interface=Interface(
                    outputs=[features.vibration_delta],
                ),
                row_context=RowContext(before=1),
                compute=Binding(
                    function=analytics.delta,
                    arguments=dict(
                        dataset=ref.dataset(),
                        feature=features.vibration_rms,
                        partition_by=[ref.dimension("machine_dimension").resolution("machine").key],
                        order_by=ref.dimension("machine_timestamp").resolution("timestamp").key,
                        num_rows=ref.row_context("before"),
                        output=features.vibration_delta,
                    ),
                ),
            ),
            Operator(
                id="pump_health_score",
                interface=Interface(
                    outputs=[features.pump_health_score],
                ),
                compute=Binding(
                    function=analytics.pump_health_score,
                    arguments=dict(
                        dataset=ref.dataset(),
                        health_features=[
                            features.bearing_temperature_delta,
                            features.vibration_delta,
                            features.pressure_flow_efficiency,
                        ],
                        output=features.pump_health_score,
                    ),
                ),
            ),
            Operator(
                id="operating_point_recommendation",
                interface=Interface(
                    outputs=[features.operating_point_recommendation],
                ),
                compute=Binding(
                    function=analytics.operation_point_optimization,
                    arguments=dict(
                        dataset=ref.dataset(),
                        optimization_features=[
                            features.differential_pressure,
                            features.flow_rate,
                            features.motor_power,
                            features.bearing_temperature,
                            features.vibration_rms,
                        ],
                        output=features.operating_point_recommendation,
                        bearing_temperature_warning_limit=90.0,
                        vibration_warning_limit=4.5,
                    ),
                ),
            ),
        ],
        publishing=[
            Operator(
                id="write_pump_telemetry",
                interface=Interface(
                    outputs=[],
                ),
                compute=Binding(
                    function=io.write_file,
                    arguments=dict(
                        dataset=ref.dataset(),
                        features=[
                            features.recommended_flow_rate,
                            features.recommended_differential_pressure,
                            features.mode,
                            features.pump_mode,
                            features.differential_pressure,
                            features.flow_rate,
                            features.bearing_temperature,
                            features.vibration_rms,
                            features.motor_power,
                            features.energy_cost_score,
                            features.converged,
                            features.pressure_flow_efficiency,
                            features.room_temperature_reference,
                            features.bearing_temperature_rise,
                            features.bearing_temperature_delta,
                            features.vibration_delta,
                            features.pump_health_score,
                            features.operating_point_recommendation,
                        ],
                        output=ref.paths("pump_telemetry_output"),
                    ),
                ),
            )
        ],
    )
