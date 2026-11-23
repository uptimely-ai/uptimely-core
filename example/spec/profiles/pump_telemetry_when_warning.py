"""Filter telemetry to warning readings at the original timestamp grain."""

import pump_analytics as analytics
from spec import dimension

from uptimely import Bind, Feature, FeatureSet, Operator, Order, Profile, ref


class WarningTelemetryFeatures(FeatureSet):
    """Measurements from warning telemetry."""

    warning_differential_pressure = Feature(
        type="float", unit="bar", description="Differential pressure from a warning reading."
    )
    warning_flow_rate = Feature(
        type="float", unit="m3/h", description="Cooling-water flow from a warning reading."
    )
    warning_motor_power = Feature(
        type="float", unit="kW", description="Motor power from a warning reading."
    )
    warning_bearing_temperature = Feature(
        type="float", unit="C", description="Bearing temperature from a warning reading."
    )
    warning_vibration_rms = Feature(
        type="float", unit="mm/s", description="Vibration RMS from a warning reading."
    )


class PumpTelemetryWhenWarning(Profile):
    """Warning observations at pump-and-timestamp grain."""

    id = "pump_telemetry_when_warning"
    name = "Telemetry when Warning"
    description = "Telemetry readings filtered to warning condition."
    category = "Telemetry"
    grain = [
        dimension.MACHINE_DIMENSION.resolution("machine"),
        dimension.MACHINE_TIMESTAMP.resolution("timestamp"),
    ]
    relations = [
        dimension.MACHINE_TIMESTAMP.resolution("hour"),
    ]
    scope = "Only telemetry records with pump_mode = warning."
    order = (Order(dimension.MACHINE_TIMESTAMP, "timestamp", direction="asc"),)
    features = WarningTelemetryFeatures()
    seed = "filter_warning"
    assembly = [
        Operator(
            id="filter_warning",
            inputs=[
                ref.input("pump_mode"),
                ref.input("differential_pressure"),
                ref.input("flow_rate"),
                ref.input("motor_power"),
                ref.input("bearing_temperature"),
                ref.input("vibration_rms"),
            ],
            outputs=[
                features.warning_differential_pressure,
                features.warning_flow_rate,
                features.warning_motor_power,
                features.warning_bearing_temperature,
                features.warning_vibration_rms,
            ],
            compute=Bind(
                analytics.filter_rows,
                dataset=ref.dataset("pump_telemetry"),
                feature=ref.input("pump_mode"),
                value="warning",
                rename={
                    "differential_pressure": features.warning_differential_pressure,
                    "flow_rate": features.warning_flow_rate,
                    "motor_power": features.warning_motor_power,
                    "bearing_temperature": features.warning_bearing_temperature,
                    "vibration_rms": features.warning_vibration_rms,
                },
            ),
        ),
    ]
