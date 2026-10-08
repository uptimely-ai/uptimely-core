"""Pump telemetry dataset declarations for example 1."""

from uptimely.spec.python_spec import bind, dataset, feature, fragment, ref

from ...functions import calculation, sink, source

telemetry_read = fragment.Read(
    id="read_pump_telemetry",
    bind=bind.bind(
        source.read_pump_telemetry,
        source=ref.source("telemetry_source"),
        environment="development",
    ),
    features=[
        feature.Raw(id="plant", type="string", description="Manufacturing plant identifier"),
        feature.Raw(id="production_line", type="string", description="Production line identifier"),
        feature.Raw(id="pump", type="string", description="Centrifugal pump asset identifier"),
        feature.Raw(id="timestamp", type="datetime", description="UTC telemetry timestamp"),
        feature.Raw(
            id="discharge_pressure", type="float", unit="bar", description="Pump discharge pressure"
        ),
        feature.Raw(
            id="flow_rate", type="float", unit="m3/h", description="Pump discharge flow rate"
        ),
        feature.Raw(
            id="bearing_temperature",
            type="float",
            unit="C",
            description="Drive-end bearing temperature",
        ),
        feature.Raw(
            id="vibration_rms", type="float", unit="mm/s", description="Overall pump vibration RMS"
        ),
        feature.Raw(
            id="motor_power",
            type="float",
            unit="kW",
            description="Electric motor active power consumption",
        ),
    ],
)

telemetry_calculations = [
    feature.Vectorize(
        id="recommended_flow_rate",
        unit="m3/h",
        description="Recommended flow rate for efficient operation",
        bind=bind.bind(
            calculation.extract_recommendation_value,
            optimization_attribute="recommended_flow_rate",
            column=ref.feature("operating_point_recommendation"),
        ),
    ),
    feature.Vectorize(
        id="recommended_discharge_pressure",
        unit="bar",
        description="Recommended discharge pressure for efficient operation",
        bind=bind.bind(
            calculation.extract_recommendation_value,
            optimization_attribute="recommended_discharge_pressure",
            column=ref.feature("operating_point_recommendation"),
        ),
    ),
    feature.Vectorize(
        id="energy_cost_score",
        description="Estimated energy-cost score for the recommended operating point",
        bind=bind.bind(
            calculation.extract_recommendation_value,
            optimization_attribute="energy_cost_score",
            column=ref.feature("operating_point_recommendation"),
        ),
    ),
    feature.Vectorize(
        id="converged",
        description="Whether the optimization converged",
        bind=bind.bind(
            calculation.converged,
            function_id="extract_convergence_flag",
            recommendation_features=[ref.feature("operating_point_recommendation")],
        ),
    ),
    feature.Vectorize(
        id="pressure_flow_efficiency",
        description="Hydraulic efficiency proxy from pressure, flow, and motor power",
        bind=bind.bind(
            calculation.pressure_flow_efficiency,
            pressure_features=[
                ref.feature("discharge_pressure"),
                ref.feature("flow_rate"),
                ref.feature("motor_power"),
            ],
        ),
    ),
    feature.Vectorize(
        id="bearing_temperature_delta",
        unit="C",
        description="Bearing-temperature change from the previous pump reading.",
        bind=bind.bind(
            calculation.bearing_temperature_delta,
            temperature=ref.feature("bearing_temperature"),
            partition_by=[
                ref.dimension("plant"),
                ref.dimension("production_line"),
                ref.dimension("pump"),
            ],
            order_by=ref.dimension("timestamp"),
        ),
    ),
    feature.Vectorize(
        id="vibration_delta",
        unit="mm/s",
        description="Vibration change from the previous pump reading.",
        bind=bind.bind(
            calculation.vibration_delta_from_previous,
            function_id="vibration_delta_from_previous",
            vibration=ref.feature("vibration_rms"),
            partition_by=[
                ref.dimension("plant"),
                ref.dimension("production_line"),
                ref.dimension("pump"),
            ],
            order_by=ref.dimension("timestamp"),
        ),
    ),
    feature.Vectorize(
        id="pump_health_score",
        description=(
            "Composite pump health score from bearing-temperature trend, "
            "vibration trend, and efficiency."
        ),
        bind=bind.bind(
            calculation.pump_health_score,
            health_features=[
                ref.feature("bearing_temperature_delta"),
                ref.feature("vibration_delta"),
                ref.feature("pressure_flow_efficiency"),
            ],
        ),
    ),
    feature.Vectorize(
        id="operating_point_recommendation",
        description="Recommended pump operating point based on process demand and energy use",
        bind=bind.bind(
            calculation.optimize_pump_operating_point,
            optimization_features=[
                ref.feature("discharge_pressure"),
                ref.feature("flow_rate"),
                ref.feature("motor_power"),
                ref.feature("bearing_temperature"),
                ref.feature("vibration_rms"),
            ],
        ),
    ),
]

telemetry_write = fragment.Write(
    id="write_pump_telemetry",
    bind=bind.bind(
        sink.write_pump_telemetry,
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
)

telemetry_dataset = dataset.Dataset(
    id="pump_telemetry_dataset",
    description="Pump process and condition readings sampled at one-minute intervals.",
    row_scope=dataset.RowScope(
        grain="One row per pump and timestamp",
        filtering="Development telemetry selected by the read function",
    ),
    read=[telemetry_read],
    vectorize=telemetry_calculations,
    write=[telemetry_write],
)
