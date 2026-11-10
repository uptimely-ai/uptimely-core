"""Pump-level profile and declarative dataframe transformations."""

from examples.pump_analytics.functions import analytics, capacity, external_workflow, source
from examples.pump_analytics.spec import dimension

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Profile, merge, ref
from uptimely.spec import feature_types


class PumpFeatures(FeatureSet):
    """Features declared by the pump profile."""

    pump_max_capacity = Feature(
        type=feature_types.FLOAT,
        unit="m3/h",
        description="Maximum flow capacity specified for this individual pump.",
    )
    series_max_capacity = Feature(
        type=feature_types.FLOAT,
        unit="m3/h",
        description="Maximum flow capacity inherited from the pump series.",
    )
    category_max_capacity = Feature(
        type=feature_types.FLOAT,
        unit="m3/h",
        description="Maximum flow capacity inherited from the pump category.",
    )
    max_capacity = Feature(
        type=feature_types.FLOAT,
        unit="m3/h",
        description="First available maximum capacity at pump, series, then category resolution.",
    )
    measurement = Feature(
        id="measurement",
        type=feature_types.FLOAT,
        description="Measured pump value provided to the external workflow.",
    )
    reference_value = Feature(
        id="reference_value",
        type=feature_types.FLOAT,
        description="Reference value used to normalize the pump measurement.",
    )
    ratio = Feature(
        id="ratio",
        type=feature_types.FLOAT,
        description="Pump measurement divided by its reference value.",
    )
    bearing_temperature_max = Feature(
        id="bearing_temperature_max",
        type=feature_types.FLOAT,
        unit="C",
        description="Maximum observed bearing temperature",
    )
    health_signal_normalized = Feature(
        id="health_signal_normalized",
        type=feature_types.FLOAT,
        description="Normalized bearing-temperature health signal by pump.",
    )


class Pump(Profile):
    """One observation per pump with collapsed telemetry and external inputs."""

    id = "pump"
    name = "Pump"
    description = "One row per pump with collapsed condition and workflow inputs."
    category = "Machines"
    grain = [dimension.MACHINE_DIMENSION.resolution("machine")]
    relations = [
        dimension.MACHINE_DIMENSION.resolution("machine_series"),
        dimension.MACHINE_DIMENSION.resolution("machine_category"),
    ]
    scope = "Pump-level telemetry and external workflow inputs"
    features = PumpFeatures()

    assembly = [
        Operator(
            id="read_pump_capacity",
            interface=Interface(outputs=[features.pump_max_capacity]),
            compute=Binding(
                function=source.read_file,
                arguments=dict(
                    source=ref.params("pump_assets_source"),
                    rename={"max_capacity": features.pump_max_capacity},
                    schema={"max_capacity": "float"},
                ),
            ),
            merge=merge.default(),
        ),
        Operator(
            id="expand_series_capacity",
            interface=Interface(
                inputs=[ref.feature("max_capacity_series")],
                outputs=[features.series_max_capacity],
            ),
            compute=Binding(
                function=analytics.select_columns,
                arguments=dict(
                    dataset=ref.dataset("pump_series"),
                    columns=[
                        dimension.MACHINE_DIMENSION.resolution("machine_series").key,
                        ref.feature("max_capacity_series"),
                    ],
                    rename={"max_capacity_series": features.series_max_capacity},
                ),
            ),
            merge=merge.default(),
        ),
        Operator(
            id="expand_category_capacity",
            interface=Interface(
                inputs=[ref.feature("max_capacity_category")],
                outputs=[features.category_max_capacity],
            ),
            compute=Binding(
                function=analytics.select_columns,
                arguments=dict(
                    dataset=ref.dataset("pump_category"),
                    columns=[
                        dimension.MACHINE_DIMENSION.resolution("machine_category").key,
                        ref.feature("max_capacity_category"),
                    ],
                    rename={"max_capacity_category": features.category_max_capacity},
                ),
            ),
            merge=merge.default(),
        ),
        Operator(
            id="resolve_max_capacity",
            interface=Interface(
                inputs=[
                    features.pump_max_capacity,
                    features.series_max_capacity,
                    features.category_max_capacity,
                ],
                outputs=[features.max_capacity],
            ),
            compute=Binding(
                function=capacity.resolve_capacity,
                arguments=dict(
                    dataset=ref.dataset(),
                    features=[
                        features.pump_max_capacity,
                        features.series_max_capacity,
                        features.category_max_capacity,
                    ],
                    output=features.max_capacity,
                ),
            ),
        ),
        Operator(
            id="bearing_temperature_by_pump",
            interface=Interface(
                inputs=[ref.feature("bearing_temperature")],
                outputs=[features.bearing_temperature_max],
            ),
            compute=Binding(
                function=analytics.aggregate,
                arguments=dict(
                    dataset=ref.dataset("pump_telemetry"),
                    feature=ref.feature("bearing_temperature"),
                    method="max",
                    dimensions=ref.profile().grain.ids,
                    output=features.bearing_temperature_max,
                    filter_column="",
                    filter_value="",
                ),
            ),
            merge=merge.default(),
        ),
        Operator(
            id="health_signal_normalized",
            interface=Interface(
                inputs=[features.bearing_temperature_max],
                outputs=[features.health_signal_normalized],
            ),
            compute=Binding(
                function=analytics.min_max_scale,
                arguments=dict(
                    dataset=ref.dataset(),
                    feature=features.bearing_temperature_max,
                    lower_bound=-1.0,
                    upper_bound=1.0,
                    features=[features.bearing_temperature_max],
                    output=features.health_signal_normalized,
                ),
            ),
        ),
        Operator(
            id="read_pump_external_inputs",
            interface=Interface(
                outputs=[features.measurement, features.reference_value],
            ),
            compute=Binding(
                function=source.read_file,
                arguments=dict(
                    source=ref.params("pump_external_inputs_source"),
                    schema={"measurement": "float", "reference_value": "float"},
                    rename={
                        "measurement": features.measurement,
                        "reference_value": features.reference_value,
                    },
                ),
            ),
            merge=Binding(
                function=external_workflow.merge_pump_inputs,
                arguments={
                    "dataset": ref.dataset(),
                    "fragment": ref.fragment(),
                    "dataset_identifiers": ref.profile().grain.ids,
                },
            ),
        ),
        Operator(
            id="process_pump_external_workflow",
            interface=Interface(
                inputs=[features.measurement, features.reference_value],
                outputs=[features.ratio],
            ),
            compute=Binding(
                function=external_workflow.process_pump_external_workflow,
                arguments={},
            ),
        ),
    ]
