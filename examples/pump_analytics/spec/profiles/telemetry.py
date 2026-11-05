"""Minute-level pump profile and declarative dataframe transformations."""

from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import dimension

from uptimely import Action, Feature, FeatureSet, Grain, Order, Profile, ref
from uptimely.spec.python import row_context

HYDRAULIC_POWER_SCALE = 1.0 / 36.0
"""Converts bar * m3/h into kW for the hydraulic-power numerator."""

TELEMETRY_GRAIN = [
    Grain(dimension.MACHINE, "machine"),
    Grain(dimension.TIMESTAMP, "timestamp"),
]


class TelemetryFeatures(FeatureSet):
    """Features declared by the telemetry profile."""

    discharge_pressure = Feature(
        id="discharge_pressure",
        type="float",
        unit="bar",
        description="Pump discharge pressure",
    )
    flow_rate = Feature(
        id="flow_rate",
        type="float",
        unit="m3/h",
        description="Pump discharge flow rate",
    )
    bearing_temperature = Feature(
        id="bearing_temperature",
        type="float",
        unit="C",
        description="Drive-end bearing temperature",
    )
    vibration_rms = Feature(
        id="vibration_rms",
        type="float",
        unit="mm/s",
        description="Overall pump vibration RMS",
    )
    motor_power = Feature(
        id="motor_power",
        type="float",
        unit="kW",
        description="Electric motor active power consumption",
    )
    operation_mode = Feature(
        id="operation_mode",
        type="string",
        description="Pump speed mode: low_speed below rated flow, otherwise high_speed.",
    )
    recommended_flow_rate = Feature(
        id="recommended_flow_rate",
        type="float",
        unit="m3/h",
        description="Recommended flow rate for efficient operation",
    )
    recommended_discharge_pressure = Feature(
        id="recommended_discharge_pressure",
        type="float",
        unit="bar",
        description="Recommended discharge pressure for efficient operation",
    )
    energy_cost_score = Feature(
        id="energy_cost_score",
        type="float",
        description="Estimated energy-cost score for the recommended operating point",
    )
    converged = Feature(
        id="converged",
        type="boolean",
        description="Whether the optimization converged",
    )
    pressure_flow_efficiency = Feature(
        id="pressure_flow_efficiency",
        type="float",
        description="Hydraulic efficiency proxy from pressure, flow, and motor power",
    )
    room_temperature_reference = Feature(
        id="room_temperature_reference",
        type="float",
        unit="C",
        description="Room-temperature constant broadcast to every telemetry row.",
    )
    bearing_temperature_rise = Feature(
        id="bearing_temperature_rise",
        type="float",
        unit="C",
        description="Bearing-temperature rise above the room-temperature constant.",
    )
    bearing_temperature_delta = Feature(
        id="bearing_temperature_delta",
        type="float",
        unit="C",
        description="Bearing-temperature change from the previous pump reading.",
    )
    vibration_delta = Feature(
        id="vibration_delta",
        type="float",
        unit="mm/s",
        description="Vibration change from the previous pump reading.",
    )
    pump_health_score = Feature(
        id="pump_health_score",
        type="float",
        description=(
            "Composite pump health score from bearing-temperature trend, "
            "vibration trend, and efficiency."
        ),
    )
    operating_point_recommendation = Feature(
        id="operating_point_recommendation",
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

    producers = [
        Action(
            id="read_pump_telemetry",
            function=analytics.read_pump_telemetry,
            arguments=dict(  # noqa: C408
                source=ref.source("telemetry_source"),
                pump_assets_source=ref.source("pump_assets_source"),
                environment="development",
            ),
            outputs=[
                features.discharge_pressure,
                features.flow_rate,
                features.bearing_temperature,
                features.vibration_rms,
                features.motor_power,
                features.operation_mode,
            ],
        ),
        Action(
            id="recommended_flow_rate",
            function=analytics.extract_field,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                column=ref.column("operating_point_recommendation"),
                field="recommended_flow_rate",
                output=ref.output("recommended_flow_rate"),
            ),
            outputs=[features.recommended_flow_rate],
        ),
        Action(
            id="recommended_discharge_pressure",
            function=analytics.extract_field,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                column=ref.column("operating_point_recommendation"),
                field="recommended_discharge_pressure",
                output=ref.output("recommended_discharge_pressure"),
            ),
            outputs=[features.recommended_discharge_pressure],
        ),
        Action(
            id="energy_cost_score",
            function=analytics.extract_field,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                column=ref.column("operating_point_recommendation"),
                field="energy_cost_score",
                output=ref.output("energy_cost_score"),
            ),
            outputs=[features.energy_cost_score],
        ),
        Action(
            id="converged",
            function=analytics.extract_field,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                column=ref.column("operating_point_recommendation"),
                field="converged",
                output=ref.output("converged"),
            ),
            outputs=[features.converged],
        ),
        Action(
            id="pressure_flow_efficiency",
            function=analytics.ratio,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                numerator_features=[
                    ref.column("discharge_pressure"),
                    ref.column("flow_rate"),
                ],
                denominator_features=[ref.column("motor_power")],
                scale=HYDRAULIC_POWER_SCALE,
                output=ref.output("pressure_flow_efficiency"),
            ),
            outputs=[features.pressure_flow_efficiency],
        ),
        Action(
            id="room_temperature_reference",
            function=analytics.broadcast_constant,
            arguments=dict(  # noqa: C408
                constants=ref.dataframe("constants"),
                feature=ref.column("room_temperature"),
                output=ref.output("room_temperature_reference"),
            ),
            outputs=[features.room_temperature_reference],
        ),
        Action(
            id="bearing_temperature_rise",
            function=analytics.subtract,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                feature=ref.column("bearing_temperature"),
                subtrahend=ref.column("room_temperature_reference"),
                output=ref.output("bearing_temperature_rise"),
            ),
            outputs=[features.bearing_temperature_rise],
        ),
        Action(
            id="bearing_temperature_delta",
            function=analytics.delta,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                feature=ref.column("bearing_temperature"),
                partition_by=[ref.feature("pump_id").id],
                order_by=ref.feature("timestamp").id,
                output=ref.output("bearing_temperature_delta"),
            ),
            outputs=[features.bearing_temperature_delta],
            row_context=row_context.rows(1, before=1),
        ),
        Action(
            id="vibration_delta",
            function=analytics.delta,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                feature=ref.column("vibration_rms"),
                partition_by=[ref.feature("pump_id").id],
                order_by=ref.feature("timestamp").id,
                output=ref.output("vibration_delta"),
            ),
            outputs=[features.vibration_delta],
            row_context=row_context.rows(1, before=1),
        ),
        Action(
            id="pump_health_score",
            function=analytics.pump_health_score,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                health_features=[
                    ref.column("bearing_temperature_delta"),
                    ref.column("vibration_delta"),
                    ref.column("pressure_flow_efficiency"),
                ],
                output=ref.output("pump_health_score"),
            ),
            outputs=[features.pump_health_score],
        ),
        Action(
            id="operating_point_recommendation",
            function=analytics.optimize_pump_operating_point,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                optimization_features=[
                    ref.column("discharge_pressure"),
                    ref.column("flow_rate"),
                    ref.column("motor_power"),
                    ref.column("bearing_temperature"),
                    ref.column("vibration_rms"),
                ],
                output=ref.output("operating_point_recommendation"),
            ),
            outputs=[features.operating_point_recommendation],
        ),
    ]
    publishers = [
        Action(
            id="write_pump_telemetry",
            function=analytics.write_pump_telemetry,
            arguments=dict(  # noqa: C408
                dataset=ref.current_profile(),
                features=[
                    ref.column("recommended_flow_rate"),
                    ref.column("recommended_discharge_pressure"),
                    ref.column("energy_cost_score"),
                    ref.column("converged"),
                    ref.column("pressure_flow_efficiency"),
                    ref.column("bearing_temperature_rise"),
                    ref.column("bearing_temperature_delta"),
                    ref.column("vibration_delta"),
                    ref.column("pump_health_score"),
                    ref.column("operating_point_recommendation"),
                ],
            ),
            outputs=[],
        )
    ]
