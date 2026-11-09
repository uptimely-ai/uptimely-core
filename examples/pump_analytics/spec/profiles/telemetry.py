"""Minute-level pump profile and declarative dataframe transformations."""

from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import dimension

from uptimely import (
    Binding,
    Feature,
    FeatureSet,
    Grain,
    Interface,
    Operator,
    Order,
    Profile,
    ref,
)
from uptimely.spec.row_context import RowContext

HYDRAULIC_POWER_SCALE = 1.0 / 36.0
"""Converts bar * m3/h into kW for the hydraulic-power numerator."""

TELEMETRY_GRAIN = [
    Grain(dimension.MACHINE, "machine"),
    Grain(dimension.TIMESTAMP, "timestamp"),
]


class TelemetryFeatures(FeatureSet):
    """Features declared by the telemetry profile."""

    discharge_pressure = Feature(
        type="float",
        unit="bar",
        description="Pump discharge pressure",
    )
    flow_rate = Feature(
        type="float",
        unit="m3/h",
        description="Pump discharge flow rate",
    )
    bearing_temperature = Feature(
        type="float",
        unit="C",
        description="Drive-end bearing temperature",
    )
    vibration_rms = Feature(
        type="float",
        unit="mm/s",
        description="Overall pump vibration RMS",
    )
    motor_power = Feature(
        type="float",
        unit="kW",
        description="Electric motor active power consumption",
    )
    operation_mode = Feature(
        type="string",
        description="Pump speed mode: low_speed below rated flow, otherwise high_speed.",
    )
    recommended_flow_rate = Feature(
        type="float",
        unit="m3/h",
        description="Recommended flow rate for efficient operation",
    )
    recommended_discharge_pressure = Feature(
        type="float",
        unit="bar",
        description="Recommended discharge pressure for efficient operation",
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
        description="Hydraulic efficiency proxy from pressure, flow, and motor power",
    )
    room_temperature_reference = Feature(
        type="float",
        unit="C",
        description="Room-temperature constant broadcast to every telemetry row.",
    )
    bearing_temperature_rise = Feature(
        type="float",
        unit="C",
        description="Bearing-temperature rise above the room-temperature constant.",
    )
    bearing_temperature_delta = Feature(
        type="float",
        unit="C",
        description="Bearing-temperature change from the previous pump reading.",
    )
    vibration_delta = Feature(
        unit="mm/s",
        description="Vibration change from the previous pump reading.",
    )
    pump_health_score = Feature(
        type="float",
        description=(
            "Composite pump health score from bearing-temperature trend, "
            "vibration trend, and efficiency."
        ),
    )
    operating_point_recommendation = Feature(
        type="object",
        description="Recommended pump operating point based on process demand and energy use",
    )


class Telemetry(Profile):
    """Process and condition readings at pump-and-timestamp grain."""

    id = "pump_telemetry"
    name = "Pump Telemetry"
    description = "Pump process and condition readings sampled at one-minute intervals."
    category = "Telemetry"
    grain = TELEMETRY_GRAIN
    scope = "Development telemetry selected by the read function"
    order = (Order(dimension.TIMESTAMP, "timestamp", direction="asc"),)
    features = TelemetryFeatures()

    assembly = dict(
        ingestion=[
            Operator(
                id="read_pump_telemetry",
                interface=Interface(
                    outputs=[
                        features.discharge_pressure,
                        features.flow_rate,
                        features.bearing_temperature,
                        features.vibration_rms,
                        features.motor_power,
                        features.operation_mode,
                    ],
                ),
                compute=Binding(
                    function=analytics.read_pump_telemetry,
                    arguments=dict(
                        source=ref.params("telemetry_source"),
                        pump_assets_source=ref.params("pump_assets_source"),
                        environment="development",
                    ),
                ),
            ),
        ],
        calculations=[
            Operator(
                id="recommended_flow_rate",
                interface=Interface(
                    outputs=[features.recommended_flow_rate],
                ),
                compute=Binding(
                    function=analytics.extract_field,
                    arguments=dict(
                        dataset=ref.dataset(),
                        column=features.operating_point_recommendation,
                        field="recommended_flow_rate",
                        output=features.recommended_flow_rate,
                    ),
                ),
            ),
            Operator(
                id="recommended_discharge_pressure",
                interface=Interface(
                    outputs=[features.recommended_discharge_pressure],
                ),
                compute=Binding(
                    function=analytics.extract_field,
                    arguments=dict(
                        dataset=ref.dataset(),
                        column=features.operating_point_recommendation,
                        field="recommended_discharge_pressure",
                        output=features.recommended_discharge_pressure,
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
                            features.discharge_pressure,
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
                    function=analytics.broadcast_constant,
                    arguments=dict(
                        constants=ref.dataset("constants"),
                        feature=ref.feature("room_temperature"),
                        output=features.room_temperature_reference,
                    ),
                ),
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
                        partition_by=[ref.dimension("machine").resolution("machine").key],
                        order_by=ref.dimension("timestamp").resolution("timestamp").key,
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
                        partition_by=[ref.dimension("machine").resolution("machine").key],
                        order_by=ref.dimension("timestamp").resolution("timestamp").key,
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
                    function=analytics.operation_point_quantum_optimization,
                    arguments=dict(
                        dataset=ref.dataset(),
                        optimization_features=[
                            features.discharge_pressure,
                            features.flow_rate,
                            features.motor_power,
                            features.bearing_temperature,
                            features.vibration_rms,
                        ],
                        output=features.operating_point_recommendation,
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
                    function=analytics.write_pump_telemetry,
                    arguments=dict(
                        dataset=ref.dataset(),
                        features=[
                            features.recommended_flow_rate,
                            features.recommended_discharge_pressure,
                            features.energy_cost_score,
                            features.converged,
                            features.pressure_flow_efficiency,
                            features.bearing_temperature_rise,
                            features.bearing_temperature_delta,
                            features.vibration_delta,
                            features.pump_health_score,
                            features.operating_point_recommendation,
                        ],
                    ),
                ),
            )
        ],
    )
