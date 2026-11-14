"""Filter telemetry to warning readings at the original timestamp grain."""

import pump_analytics as analytics
from spec import dimension

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Order, Profile, merge, ref


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
    assembly = [
        Operator(
            id="select_warning_telemetry",
            interface=Interface(
                inputs=[
                    ref.feature("pump_mode"),
                    ref.feature("differential_pressure"),
                    ref.feature("flow_rate"),
                    ref.feature("motor_power"),
                    ref.feature("bearing_temperature"),
                    ref.feature("vibration_rms"),
                ],
                outputs=[
                    features.warning_differential_pressure,
                    features.warning_flow_rate,
                    features.warning_motor_power,
                    features.warning_bearing_temperature,
                    features.warning_vibration_rms,
                ],
            ),
            compute=Binding(
                function=analytics.filter_rows,
                arguments=dict(
                    dataset=ref.dataset("pump_telemetry"),
                    feature=ref.feature("pump_mode"),
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
            merge=merge.default(),
        ),
    ]
