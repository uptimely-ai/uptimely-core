"""Minute-level pump observations and declarative dataframe transformations."""

from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import dimension, entity

from uptimely import Action, Dataset, Feature, Order, RowScope, ref
from uptimely.spec.python import row_context


class Telemetry(Dataset):
    """Process and condition readings at pump-and-timestamp grain."""

    id = "pump_telemetry_dataset"
    description = "Pump process and condition readings sampled at one-minute intervals."
    entity = entity.PUMP_TELEMETRY
    row_scope = RowScope(
        grain="One row per pump and timestamp",
        filtering="Development telemetry selected by the read function",
    )
    order = (Order(dimension=ref.dimension(dimension.TIMESTAMP.id), direction="asc"),)

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
                Feature(
                    name="discharge_pressure",
                    type="float",
                    unit="bar",
                    description="Pump discharge pressure",
                ),
                Feature(
                    name="flow_rate",
                    type="float",
                    unit="m3/h",
                    description="Pump discharge flow rate",
                ),
                Feature(
                    name="bearing_temperature",
                    type="float",
                    unit="C",
                    description="Drive-end bearing temperature",
                ),
                Feature(
                    name="vibration_rms",
                    type="float",
                    unit="mm/s",
                    description="Overall pump vibration RMS",
                ),
                Feature(
                    name="motor_power",
                    type="float",
                    unit="kW",
                    description="Electric motor active power consumption",
                ),
                Feature(
                    name="operation_mode",
                    type="string",
                    description=(
                        "Pump speed mode: low_speed below rated flow, otherwise high_speed."
                    ),
                ),
            ],
        ),
        Action(
            id="recommended_flow_rate",
            function=analytics.extract_recommendation_value,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                column=ref.column("operating_point_recommendation"),
                optimization_attribute="recommended_flow_rate",
                output=ref.output("recommended_flow_rate"),
            ),
            outputs=[
                Feature(
                    name="recommended_flow_rate",
                    type="float",
                    unit="m3/h",
                    description="Recommended flow rate for efficient operation",
                )
            ],
        ),
        Action(
            id="recommended_discharge_pressure",
            function=analytics.extract_recommendation_value,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                column=ref.column("operating_point_recommendation"),
                optimization_attribute="recommended_discharge_pressure",
                output=ref.output("recommended_discharge_pressure"),
            ),
            outputs=[
                Feature(
                    name="recommended_discharge_pressure",
                    type="float",
                    unit="bar",
                    description="Recommended discharge pressure for efficient operation",
                )
            ],
        ),
        Action(
            id="energy_cost_score",
            function=analytics.extract_recommendation_value,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                column=ref.column("operating_point_recommendation"),
                optimization_attribute="energy_cost_score",
                output=ref.output("energy_cost_score"),
            ),
            outputs=[
                Feature(
                    name="energy_cost_score",
                    type="float",
                    description="Estimated energy-cost score for the recommended operating point",
                )
            ],
        ),
        Action(
            id="converged",
            function=analytics.extract_recommendation_value,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                column=ref.column("operating_point_recommendation"),
                optimization_attribute="converged",
                output=ref.output("converged"),
            ),
            outputs=[
                Feature(
                    name="converged",
                    type="boolean",
                    description="Whether the optimization converged",
                )
            ],
        ),
        Action(
            id="pressure_flow_efficiency",
            function=analytics.pressure_flow_efficiency,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                pressure_features=[
                    ref.column("discharge_pressure"),
                    ref.column("flow_rate"),
                    ref.column("motor_power"),
                ],
                output=ref.output("pressure_flow_efficiency"),
            ),
            outputs=[
                Feature(
                    name="pressure_flow_efficiency",
                    type="float",
                    description="Hydraulic efficiency proxy from pressure, flow, and motor power",
                )
            ],
        ),
        Action(
            id="bearing_temperature_delta",
            function=analytics.bearing_temperature_delta,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                temperature=ref.column("bearing_temperature"),
                partition_by=[ref.dimension(key.id) for key in entity.dimensions[:-1]],
                order_by=ref.dimension(dimension.TIMESTAMP.id),
                output=ref.output("bearing_temperature_delta"),
            ),
            outputs=[
                Feature(
                    name="bearing_temperature_delta",
                    type="float",
                    unit="C",
                    description="Bearing-temperature change from the previous pump reading.",
                )
            ],
            row_context=row_context.rows(1, before=1),
        ),
        Action(
            id="vibration_delta",
            function=analytics.vibration_delta_from_previous,
            arguments=dict(  # noqa: C408
                dataset=ref.dataframe(),
                vibration=ref.column("vibration_rms"),
                partition_by=[ref.dimension(key.id) for key in entity.dimensions[:-1]],
                order_by=ref.dimension(dimension.TIMESTAMP.id),
                output=ref.output("vibration_delta"),
            ),
            outputs=[
                Feature(
                    name="vibration_delta",
                    type="float",
                    unit="mm/s",
                    description="Vibration change from the previous pump reading.",
                )
            ],
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
            outputs=[
                Feature(
                    name="pump_health_score",
                    type="float",
                    description="Composite pump health score from bearing-temperature trend, "
                    "vibration trend, and efficiency.",
                )
            ],
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
            outputs=[
                Feature(
                    name="operating_point_recommendation",
                    type="object",
                    description=(
                        "Recommended pump operating point based on process demand and energy use"
                    ),
                )
            ],
        ),
    ]
    publishers = [
        Action(
            id="write_pump_telemetry",
            function=analytics.write_pump_telemetry,
            arguments=dict(  # noqa: C408
                dataset=ref.current_dataset(),
                features=[
                    ref.column("recommended_flow_rate"),
                    ref.column("recommended_discharge_pressure"),
                    ref.column("energy_cost_score"),
                    ref.column("converged"),
                    ref.column("pressure_flow_efficiency"),
                    ref.column("bearing_temperature_delta"),
                    ref.column("vibration_delta"),
                    ref.column("pump_health_score"),
                    ref.column("operating_point_recommendation"),
                ],
            ),
            outputs=[],
        )
    ]
