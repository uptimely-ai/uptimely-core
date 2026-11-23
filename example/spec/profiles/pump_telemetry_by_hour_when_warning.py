"""Hourly operating-point calculations on warning-only telemetry."""

import polars as pl
import pump_analytics as analytics
import pump_io as io
from spec import dimension

from uptimely import Bind, Feature, FeatureSet, Operator, Order, Profile, ref


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
    seed = "aggregate_warning"

    assembly = [
        Operator(
            id="aggregate_warning",
            inputs=[
                ref.input("warning_differential_pressure"),
                ref.input("warning_flow_rate"),
                ref.input("warning_motor_power"),
                ref.input("warning_bearing_temperature"),
                ref.input("warning_vibration_rms"),
            ],
            compute=Bind(
                analytics.aggregate,
                dataset=ref.dataset("pump_telemetry_when_warning"),
                aggregations={
                    "warning_differential_pressure": "mean",
                    "warning_flow_rate": "mean",
                    "warning_motor_power": "mean",
                    "warning_bearing_temperature": "max",
                    "warning_vibration_rms": "max",
                },
                dimensions=[
                    ref.key("pump_id"),
                    ref.key("hour"),
                ],
                rename={
                    "warning_differential_pressure": (
                        ref.output("warning_hour_mean_differential_pressure")
                    ),
                    "warning_flow_rate": ref.output("warning_hour_mean_flow_rate"),
                    "warning_motor_power": ref.output("warning_hour_mean_motor_power"),
                    "warning_bearing_temperature": (
                        ref.output("warning_hour_max_bearing_temperature")
                    ),
                    "warning_vibration_rms": ref.output("warning_hour_max_vibration_rms"),
                },
            ),
        ),
        Operator(
            compute=Bind(
                analytics.operation_point_optimization,
                dataset=ref.dataset(),
                optimization_features=[
                    ref.input("warning_hour_mean_differential_pressure"),
                    ref.input("warning_hour_mean_flow_rate"),
                    ref.input("warning_hour_mean_motor_power"),
                    ref.input("warning_hour_max_bearing_temperature"),
                    ref.input("warning_hour_max_vibration_rms"),
                ],
                output=ref.output("operating_point_recommendation"),
                bearing_temperature_warning_limit=90.0,
                vibration_warning_limit=4.5,
            ),
        ),
        Operator(
            outputs=[features.recommended_flow_rate],
            compute=Bind(
                ref.function(
                    pl.LazyFrame.with_columns,
                    returns="dataframe",
                    args={"self": "dataframe", "recommended_flow_rate": "string"},
                    validate_signature=False,
                ),
                self=ref.dataset(),
                recommended_flow_rate=ref.input("warning_hour_mean_flow_rate"),
            ),
        ),
        Operator(
            compute=Bind(
                analytics.extract_field,
                dataset=ref.dataset(),
                column=ref.input("operating_point_recommendation"),
                field="recommended_differential_pressure",
                output=ref.output("recommended_differential_pressure"),
            ),
        ),
        Operator(
            compute=Bind(
                analytics.extract_field,
                dataset=ref.dataset(),
                column=ref.input("operating_point_recommendation"),
                field="energy_cost_score",
                output=ref.output("energy_cost_score"),
            ),
        ),
        Operator(
            compute=Bind(
                analytics.extract_field,
                dataset=ref.dataset(),
                column=ref.input("operating_point_recommendation"),
                field="converged",
                output=ref.output("converged"),
            ),
        ),
        Operator(
            compute=Bind(
                io.write_file,
                dataset=ref.dataset(),
                features=[
                    ref.input("warning_hour_mean_differential_pressure"),
                    ref.input("warning_hour_mean_flow_rate"),
                    ref.input("warning_hour_mean_motor_power"),
                    ref.input("warning_hour_max_bearing_temperature"),
                    ref.input("warning_hour_max_vibration_rms"),
                    ref.input("operating_point_recommendation"),
                    ref.input("recommended_flow_rate"),
                    ref.input("recommended_differential_pressure"),
                    ref.input("energy_cost_score"),
                    ref.input("converged"),
                ],
                output=ref.paths("pump_telemetry_by_hour_when_warning_output"),
            ),
        ),
    ]
