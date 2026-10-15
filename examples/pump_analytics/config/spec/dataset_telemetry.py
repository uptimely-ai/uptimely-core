"""Pump telemetry dataset declarations for the pump analytics project."""

from uptimely.analytics.python import bind, dataset, feature, mapping, ref, row_context

from . import functions

telemetry_features = [
    feature.Feature(id="plant", type="string", description="Manufacturing plant identifier"),
    feature.Feature(id="production_line", type="string", description="Production line identifier"),
    feature.Feature(id="pump", type="string", description="Centrifugal pump asset identifier"),
    feature.Feature(id="timestamp", type="datetime", description="UTC telemetry timestamp"),
    feature.Feature(
        id="discharge_pressure",
        type="float",
        unit="bar",
        description="Pump discharge pressure",
    ),
    feature.Feature(
        id="flow_rate",
        type="float",
        unit="m3/h",
        description="Pump discharge flow rate",
    ),
    feature.Feature(
        id="bearing_temperature",
        type="float",
        unit="C",
        description="Drive-end bearing temperature",
    ),
    feature.Feature(
        id="vibration_rms",
        type="float",
        unit="mm/s",
        description="Overall pump vibration RMS",
    ),
    feature.Feature(
        id="motor_power",
        type="float",
        unit="kW",
        description="Electric motor active power consumption",
    ),
    feature.Feature(
        id="recommended_flow_rate",
        type="float",
        unit="m3/h",
        description="Recommended flow rate for efficient operation",
    ),
    feature.Feature(
        id="recommended_discharge_pressure",
        type="float",
        unit="bar",
        description="Recommended discharge pressure for efficient operation",
    ),
    feature.Feature(
        id="energy_cost_score",
        type="float",
        description="Estimated energy-cost score for the recommended operating point",
    ),
    feature.Feature(
        id="converged",
        type="boolean",
        description="Whether the optimization converged",
    ),
    feature.Feature(
        id="pressure_flow_efficiency",
        type="float",
        description="Hydraulic efficiency proxy from pressure, flow, and motor power",
    ),
    feature.Feature(
        id="bearing_temperature_delta",
        type="float",
        unit="C",
        description="Bearing-temperature change from the previous pump reading.",
    ),
    feature.Feature(
        id="vibration_delta",
        type="float",
        unit="mm/s",
        description="Vibration change from the previous pump reading.",
    ),
    feature.Feature(
        id="pump_health_score",
        type="float",
        description=(
            "Composite pump health score from bearing-temperature trend, "
            "vibration trend, and efficiency."
        ),
    ),
    feature.Feature(
        id="operating_point_recommendation",
        type="object",
        description="Recommended pump operating point based on process demand and energy use",
    ),
]

telemetry_mappings = [
    mapping.Read(
        id="read_pump_telemetry",
        bind=bind.bind(
            ref.function(functions.source.read_pump_telemetry),
            source=ref.source("telemetry_source"),
            environment="development",
        ),
        outputs=[
            ref.feature("plant"),
            ref.feature("production_line"),
            ref.feature("pump"),
            ref.feature("timestamp"),
            ref.feature("discharge_pressure"),
            ref.feature("flow_rate"),
            ref.feature("bearing_temperature"),
            ref.feature("vibration_rms"),
            ref.feature("motor_power"),
        ],
    ),
    mapping.Vectorize(
        id="recommended_flow_rate",
        bind=bind.bind(
            ref.function(
                "examples.pump_analytics.functions.calculation:extract_recommendation_value"
            ),
            optimization_attribute="recommended_flow_rate",
            column=ref.feature("operating_point_recommendation"),
            dataset=ref.current_dataset().dataframe,
            output=ref.feature("recommended_flow_rate").id,
        ),
        inputs=[ref.feature("operating_point_recommendation")],
        outputs=[ref.feature("recommended_flow_rate")],
    ),
    mapping.Vectorize(
        id="recommended_discharge_pressure",
        bind=bind.bind(
            ref.function(functions.calculation.extract_recommendation_value),
            optimization_attribute="recommended_discharge_pressure",
            column=ref.feature("operating_point_recommendation"),
            dataset=ref.current_dataset().dataframe,
            output=ref.feature("recommended_discharge_pressure").id,
        ),
        inputs=[ref.feature("operating_point_recommendation")],
        outputs=[ref.feature("recommended_discharge_pressure")],
    ),
    mapping.Vectorize(
        id="energy_cost_score",
        bind=bind.bind(
            ref.function(functions.calculation.extract_recommendation_value),
            optimization_attribute="energy_cost_score",
            column=ref.feature("operating_point_recommendation"),
            dataset=ref.current_dataset().dataframe,
            output=ref.feature("energy_cost_score").id,
        ),
        inputs=[ref.feature("operating_point_recommendation")],
        outputs=[ref.feature("energy_cost_score")],
    ),
    mapping.Vectorize(
        id="converged",
        bind=bind.bind(
            ref.function(functions.calculation.extract_recommendation_value),
            optimization_attribute="converged",
            column=ref.feature("operating_point_recommendation"),
            dataset=ref.current_dataset().dataframe,
            output=ref.feature("converged").id,
        ),
        inputs=[ref.feature("operating_point_recommendation")],
        outputs=[ref.feature("converged")],
    ),
    mapping.Vectorize(
        id="pressure_flow_efficiency",
        bind=bind.bind(
            ref.function(
                "examples/pump_analytics/functions/calculation.py:pressure_flow_efficiency"
            ),
            pressure_features=[
                ref.feature("discharge_pressure"),
                ref.feature("flow_rate"),
                ref.feature("motor_power"),
            ],
            dataset=ref.current_dataset().dataframe,
            output=ref.feature("pressure_flow_efficiency").id,
        ),
        inputs=[ref.feature(name) for name in ("discharge_pressure", "flow_rate", "motor_power")],
        outputs=[ref.feature("pressure_flow_efficiency")],
    ),
    mapping.Vectorize(
        id="bearing_temperature_delta",
        row_context=row_context.rows(1, before=1),
        bind=bind.bind(
            ref.function(functions.calculation.bearing_temperature_delta),
            temperature=ref.feature("bearing_temperature"),
            partition_by=[
                ref.dimension("plant"),
                ref.dimension("production_line"),
                ref.dimension("pump"),
            ],
            order_by=ref.dimension("timestamp"),
            dataset=ref.current_dataset().dataframe,
            output=ref.feature("bearing_temperature_delta").id,
        ),
        inputs=[ref.feature("bearing_temperature")],
        outputs=[ref.feature("bearing_temperature_delta")],
    ),
    mapping.Vectorize(
        id="vibration_delta",
        row_context=row_context.rows(1, before=1),
        bind=bind.bind(
            ref.function(functions.calculation.vibration_delta_from_previous),
            function_id="vibration_delta_from_previous",
            vibration=ref.feature("vibration_rms"),
            partition_by=[
                ref.dimension("plant"),
                ref.dimension("production_line"),
                ref.dimension("pump"),
            ],
            order_by=ref.dimension("timestamp"),
            dataset=ref.current_dataset().dataframe,
            output=ref.feature("vibration_delta").id,
        ),
        inputs=[ref.feature("vibration_rms")],
        outputs=[ref.feature("vibration_delta")],
    ),
    mapping.Vectorize(
        id="pump_health_score",
        bind=bind.bind(
            ref.function(functions.calculation.pump_health_score),
            health_features=[
                ref.feature("bearing_temperature_delta"),
                ref.feature("vibration_delta"),
                ref.feature("pressure_flow_efficiency"),
            ],
            dataset=ref.current_dataset().dataframe,
            output=ref.feature("pump_health_score").id,
        ),
        inputs=[
            ref.feature(name)
            for name in ("bearing_temperature_delta", "vibration_delta", "pressure_flow_efficiency")
        ],
        outputs=[ref.feature("pump_health_score")],
    ),
    mapping.Vectorize(
        id="operating_point_recommendation",
        bind=bind.bind(
            ref.function(functions.calculation.optimize_pump_operating_point),
            optimization_features=[
                ref.feature("discharge_pressure"),
                ref.feature("flow_rate"),
                ref.feature("motor_power"),
                ref.feature("bearing_temperature"),
                ref.feature("vibration_rms"),
            ],
            dataset=ref.current_dataset().dataframe,
            output=ref.feature("operating_point_recommendation").id,
        ),
        inputs=[
            ref.feature(name)
            for name in (
                "discharge_pressure",
                "flow_rate",
                "motor_power",
                "bearing_temperature",
                "vibration_rms",
            )
        ],
        outputs=[ref.feature("operating_point_recommendation")],
    ),
    mapping.Write(
        id="write_pump_telemetry",
        inputs=[
            ref.feature(name)
            for name in (
                "recommended_flow_rate",
                "recommended_discharge_pressure",
                "energy_cost_score",
                "converged",
                "pressure_flow_efficiency",
                "bearing_temperature_delta",
                "vibration_delta",
                "pump_health_score",
                "operating_point_recommendation",
            )
        ],
        bind=bind.bind(
            ref.function(functions.sink.write_pump_telemetry),
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
    ),
]

TELEMETRY_DATASET = dataset.Dataset(
    id="pump_telemetry_dataset",
    description="Pump process and condition readings sampled at one-minute intervals.",
    row_scope=dataset.RowScope(
        grain="One row per pump and timestamp",
        filtering="Development telemetry selected by the read function",
    ),
    features=telemetry_features,
    mappings=telemetry_mappings,
    order=[dataset.Order(dimension=ref.dimension("timestamp"), direction="asc")],
)
