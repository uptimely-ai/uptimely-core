"""Minute-level pump observations and declarative dataframe transformations."""

from examples.pump_analytics.functions import analytics

from uptimely.spec.python import (
    Dataset,
    Feature,
    FunctionMapping,
    Order,
    RowScope,
    ref,
    row_context,
)

from .. import entity
from ..dimension import TIMESTAMP


class Telemetry(Dataset):
    """Process and condition readings at pump-and-timestamp grain."""

    id = "pump_telemetry_dataset"
    description = "Pump process and condition readings sampled at one-minute intervals."
    entity = entity.PUMP_TELEMETRY
    row_scope = RowScope(
        grain="One row per pump and timestamp",
        filtering="Development telemetry selected by the read function",
    )
    order = (Order(dimension=ref.dimension(TIMESTAMP.id), direction="asc"),)

    read_pump_telemetry = FunctionMapping(
        function=analytics.read_pump_telemetry,
        arguments=dict(  # noqa: C408
            source=ref.source("telemetry_source"), environment="development"
        ),
        outputs=[
            Feature(
                name="discharge_pressure",
                type="float",
                unit="bar",
                description="Pump discharge pressure",
            ),
            Feature(
                name="flow_rate", type="float", unit="m3/h", description="Pump discharge flow rate"
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
        ],
    )

    recommended_flow_rate = FunctionMapping(
        function=analytics.extract_recommendation_value,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            column=ref.feature("operating_point_recommendation"),
            optimization_attribute="recommended_flow_rate",
            output=ref.feature("recommended_flow_rate").id,
        ),
        outputs=[
            Feature(
                name="recommended_flow_rate",
                type="float",
                unit="m3/h",
                description="Recommended flow rate for efficient operation",
            )
        ],
    )

    recommended_discharge_pressure = FunctionMapping(
        function=analytics.extract_recommendation_value,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            column=ref.feature("operating_point_recommendation"),
            optimization_attribute="recommended_discharge_pressure",
            output=ref.feature("recommended_discharge_pressure").id,
        ),
        outputs=[
            Feature(
                name="recommended_discharge_pressure",
                type="float",
                unit="bar",
                description="Recommended discharge pressure for efficient operation",
            )
        ],
    )

    energy_cost_score = FunctionMapping(
        function=analytics.extract_recommendation_value,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            column=ref.feature("operating_point_recommendation"),
            optimization_attribute="energy_cost_score",
            output=ref.feature("energy_cost_score").id,
        ),
        outputs=[
            Feature(
                name="energy_cost_score",
                type="float",
                description="Estimated energy-cost score for the recommended operating point",
            )
        ],
    )

    converged = FunctionMapping(
        function=analytics.extract_recommendation_value,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            column=ref.feature("operating_point_recommendation"),
            optimization_attribute="converged",
            output=ref.feature("converged").id,
        ),
        outputs=[
            Feature(
                name="converged", type="boolean", description="Whether the optimization converged"
            )
        ],
    )

    pressure_flow_efficiency = FunctionMapping(
        function=analytics.pressure_flow_efficiency,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            pressure_features=[
                ref.feature("discharge_pressure"),
                ref.feature("flow_rate"),
                ref.feature("motor_power"),
            ],
            output=ref.feature("pressure_flow_efficiency").id,
        ),
        outputs=[
            Feature(
                name="pressure_flow_efficiency",
                type="float",
                description="Hydraulic efficiency proxy from pressure, flow, and motor power",
            )
        ],
    )

    bearing_temperature_delta = FunctionMapping(
        function=analytics.bearing_temperature_delta,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            temperature=ref.feature("bearing_temperature"),
            partition_by=[ref.dimension(key.id) for key in entity.dimensions[:-1]],
            order_by=ref.dimension(TIMESTAMP.id),
            output=ref.feature("bearing_temperature_delta").id,
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
    )

    vibration_delta = FunctionMapping(
        function=analytics.vibration_delta_from_previous,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            vibration=ref.feature("vibration_rms"),
            partition_by=[ref.dimension(key.id) for key in entity.dimensions[:-1]],
            order_by=ref.dimension(TIMESTAMP.id),
            output=ref.feature("vibration_delta").id,
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
    )

    pump_health_score = FunctionMapping(
        function=analytics.pump_health_score,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            health_features=[
                ref.feature("bearing_temperature_delta"),
                ref.feature("vibration_delta"),
                ref.feature("pressure_flow_efficiency"),
            ],
            output=ref.feature("pump_health_score").id,
        ),
        outputs=[
            Feature(
                name="pump_health_score",
                type="float",
                description="Composite pump health score from bearing-temperature trend, "
                "vibration trend, and efficiency.",
            )
        ],
    )

    operating_point_recommendation = FunctionMapping(
        function=analytics.optimize_pump_operating_point,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            optimization_features=[
                ref.feature("discharge_pressure"),
                ref.feature("flow_rate"),
                ref.feature("motor_power"),
                ref.feature("bearing_temperature"),
                ref.feature("vibration_rms"),
            ],
            output=ref.feature("operating_point_recommendation").id,
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
    )

    write_pump_telemetry = FunctionMapping(
        function=analytics.write_pump_telemetry,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset(),
            features=[
                ref.feature("recommended_flow_rate"),
                ref.feature("recommended_discharge_pressure"),
                ref.feature("energy_cost_score"),
                ref.feature("converged"),
                ref.feature("pressure_flow_efficiency"),
                ref.feature("bearing_temperature_delta"),
                ref.feature("vibration_delta"),
                ref.feature("pump_health_score"),
                ref.feature("operating_point_recommendation"),
            ],
        ),
        outputs=[],
    )
