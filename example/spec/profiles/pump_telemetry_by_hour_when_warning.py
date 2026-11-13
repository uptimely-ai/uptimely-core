"""Hourly operating-point calculations on warning-only telemetry."""

import polars as pl
from example.spec import dimension
from example.src import analytics, io

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Order, Profile, merge, ref


class HourlyWarningTelemetryFeatures(FeatureSet):
    """Aggregated measurements and recommendations for warning observations."""

    warning_hour_mean_differential_pressure = Feature(
        type="float",
        unit="bar",
        description="Mean differential pressure over warning readings in the hour.",
    )
    warning_hour_mean_flow_rate = Feature(
        type="float",
        unit="m3/h",
        description="Mean cooling-water flow over warning readings in the hour.",
    )
    warning_hour_mean_motor_power = Feature(
        type="float",
        unit="kW",
        description="Mean motor power over warning readings in the hour.",
    )
    warning_hour_max_bearing_temperature = Feature(
        type="float",
        unit="C",
        description="Maximum bearing temperature over warning readings in the hour.",
    )
    warning_hour_max_vibration_rms = Feature(
        type="float",
        unit="mm/s",
        description="Maximum vibration RMS over warning readings in the hour.",
    )
    recommended_flow_rate = Feature(
        type="float",
        unit="m3/h",
        description="Illustrative recommended cooling-water flow for a warning record.",
    )
    recommended_differential_pressure = Feature(
        type="float",
        unit="bar",
        description="Illustrative recommended differential pressure for a warning record.",
    )
    energy_cost_score = Feature(
        type="float",
        description="Estimated energy-cost score for the recommended operating point.",
    )
    converged = Feature(
        type="boolean",
        description="Whether the illustrative optimization converged.",
    )
    operating_point_recommendation = Feature(
        type="object",
        description="Illustrative operating-point recommendation for a warning record.",
    )


class PumpTelemetryByHourWhenWarning(Profile):
    """One observation per cooling pump and hour containing warning readings."""

    id = "pump_telemetry_by_hour_when_warning"
    name = "Telemetry by Hour when Warning"
    description = "Operating-point recommendations calculated from hourly warning telemetry."
    category = "Telemetry"
    grain = [
        dimension.MACHINE_DIMENSION.resolution("machine"),
        dimension.MACHINE_TIMESTAMP.resolution("hour"),
    ]
    scope = "Only telemetry records with pump_mode = warning."
    order = (Order(dimension.MACHINE_TIMESTAMP, "hour", direction="asc"),)
    features = HourlyWarningTelemetryFeatures()

    assembly = [
        Operator(
            id="aggregate_warning_telemetry",
            interface=Interface(
                inputs=[
                    ref.feature("warning_differential_pressure"),
                    ref.feature("warning_flow_rate"),
                    ref.feature("warning_motor_power"),
                    ref.feature("warning_bearing_temperature"),
                    ref.feature("warning_vibration_rms"),
                ],
                outputs=[
                    features.warning_hour_mean_differential_pressure,
                    features.warning_hour_mean_flow_rate,
                    features.warning_hour_mean_motor_power,
                    features.warning_hour_max_bearing_temperature,
                    features.warning_hour_max_vibration_rms,
                ],
            ),
            compute=Binding(
                function=analytics.aggregate,
                arguments=dict(
                    dataset=ref.dataset("pump_telemetry_when_warning"),
                    aggregations={
                        "warning_differential_pressure": "mean",
                        "warning_flow_rate": "mean",
                        "warning_motor_power": "mean",
                        "warning_bearing_temperature": "max",
                        "warning_vibration_rms": "max",
                    },
                    dimensions=[
                        dimension.MACHINE_DIMENSION.resolution("machine").key,
                        dimension.MACHINE_TIMESTAMP.resolution("hour").key,
                    ],
                    rename={
                        "warning_differential_pressure": (
                            features.warning_hour_mean_differential_pressure
                        ),
                        "warning_flow_rate": features.warning_hour_mean_flow_rate,
                        "warning_motor_power": features.warning_hour_mean_motor_power,
                        "warning_bearing_temperature": (
                            features.warning_hour_max_bearing_temperature
                        ),
                        "warning_vibration_rms": features.warning_hour_max_vibration_rms,
                    },
                ),
            ),
            merge=merge.default(),
        ),
        Operator(
            id="operating_point_recommendation",
            interface=Interface(outputs=[features.operating_point_recommendation]),
            compute=Binding(
                function=analytics.operation_point_optimization,
                arguments=dict(
                    dataset=ref.dataset(),
                    optimization_features=[
                        features.warning_hour_mean_differential_pressure,
                        features.warning_hour_mean_flow_rate,
                        features.warning_hour_mean_motor_power,
                        features.warning_hour_max_bearing_temperature,
                        features.warning_hour_max_vibration_rms,
                    ],
                    output=features.operating_point_recommendation,
                    bearing_temperature_warning_limit=90.0,
                    vibration_warning_limit=4.5,
                ),
            ),
        ),
        Operator(
            id="recommended_flow_rate",
            interface=Interface(outputs=[features.recommended_flow_rate]),
            compute=Binding(
                function=ref.function(
                    pl.LazyFrame.with_columns,
                    returns="dataframe",
                    args={"self": "dataframe", "recommended_flow_rate": "string"},
                    validate_signature=False,
                ),
                arguments=dict(
                    self=ref.dataset(),
                    recommended_flow_rate=features.warning_hour_mean_flow_rate,
                ),
            ),
        ),
        Operator(
            id="recommended_differential_pressure",
            interface=Interface(outputs=[features.recommended_differential_pressure]),
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
            interface=Interface(outputs=[features.energy_cost_score]),
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
            interface=Interface(outputs=[features.converged]),
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
            id="write_pump_telemetry_by_hour_when_warning",
            interface=Interface(outputs=[]),
            compute=Binding(
                function=io.write_file,
                arguments=dict(
                    dataset=ref.dataset(),
                    features=[
                        features.warning_hour_mean_differential_pressure,
                        features.warning_hour_mean_flow_rate,
                        features.warning_hour_mean_motor_power,
                        features.warning_hour_max_bearing_temperature,
                        features.warning_hour_max_vibration_rms,
                        features.operating_point_recommendation,
                        features.recommended_flow_rate,
                        features.recommended_differential_pressure,
                        features.energy_cost_score,
                        features.converged,
                    ],
                    output=ref.paths("pump_telemetry_by_hour_when_warning_output"),
                ),
            ),
        ),
    ]
