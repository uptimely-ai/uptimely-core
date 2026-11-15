"""Cooling-pump profile and declarative dataframe transformations."""

import pump_analytics as analytics
import pump_io as io
import pump_merge as merge_functions
from spec import dimension

from uptimely import Binding, Feature, FeatureSet, Interface, Operator, Profile, merge, ref
from uptimely.spec import feature_types


class PumpFeatures(FeatureSet):
    """Features declared by the cooling-pump profile."""

    pump_max_capacity = Feature(
        type=feature_types.FLOAT,
        unit="m3/h",
        description="Maximum chilled-water flow capacity specified for this pump.",
    )
    series_max_capacity = Feature(
        type=feature_types.FLOAT,
        unit="m3/h",
        description="Maximum chilled-water flow capacity inherited from the pump series.",
    )
    category_max_capacity = Feature(
        type=feature_types.FLOAT,
        unit="m3/h",
        description="Maximum chilled-water flow capacity inherited from the pump category.",
    )
    max_capacity = Feature(
        type=feature_types.FLOAT,
        unit="m3/h",
        description=(
            "First available maximum chilled-water flow capacity at pump, series, "
            "then category resolution."
        ),
    )
    measurement = Feature(
        id="measurement",
        type=feature_types.FLOAT,
        description="Measured cooling-system value provided to the external workflow.",
    )
    reference_value = Feature(
        id="reference_value",
        type=feature_types.FLOAT,
        description="Reference value used to normalize the cooling-system measurement.",
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
        description="Normalized motor-bearing temperature signal by cooling pump.",
    )


class Pump(Profile):
    """One observation per cooling pump with collapsed telemetry and external inputs."""

    id = "pump"
    name = "Cooling Pump"
    description = "One row per cooling pump with condition and workflow inputs."
    category = "Cooling System"
    grain = [dimension.MACHINE_DIMENSION.resolution("machine")]
    relations = [
        dimension.FACILITY_DIMENSION.resolution("server_room"),
        dimension.FACILITY_DIMENSION.resolution("data_center"),
        dimension.MACHINE_DIMENSION.resolution("machine_series"),
        dimension.MACHINE_DIMENSION.resolution("machine_category"),
    ]
    scope = "Cooling-pump telemetry and external workflow inputs for data centers"
    features = PumpFeatures()

    assembly = [
        Operator(
            interface=Interface(outputs=[features.pump_max_capacity]),
            compute=Binding(
                io.read_file,
                source=ref.paths("pump_assets_source"),
                rename={"max_capacity": features.pump_max_capacity},
                schema={"max_capacity": "float"},
            ),
            merge=merge.default(),
        ),
        Operator(
            interface=Interface(
                inputs=[ref.feature("max_capacity_series")],
                outputs=[features.series_max_capacity],
            ),
            compute=Binding(
                analytics.select_columns,
                dataset=ref.dataset("pump_series"),
                columns=[
                    dimension.MACHINE_DIMENSION.resolution("machine_series").key,
                    ref.feature("max_capacity_series"),
                ],
                rename={"max_capacity_series": features.series_max_capacity},
            ),
            merge=merge.default(),
        ),
        Operator(
            interface=Interface(
                inputs=[ref.feature("max_capacity_category")],
                outputs=[features.category_max_capacity],
            ),
            compute=Binding(
                analytics.select_columns,
                dataset=ref.dataset("pump_category"),
                columns=[
                    dimension.MACHINE_DIMENSION.resolution("machine_category").key,
                    ref.feature("max_capacity_category"),
                ],
                rename={"max_capacity_category": features.category_max_capacity},
            ),
            merge=merge.default(),
        ),
        Operator(
            interface=Interface(
                inputs=[
                    features.pump_max_capacity,
                    features.series_max_capacity,
                    features.category_max_capacity,
                ],
                outputs=[features.max_capacity],
            ),
            compute=Binding(
                analytics.first_non_null_value,
                dataset=ref.dataset(),
                features=[
                    features.pump_max_capacity,
                    features.series_max_capacity,
                    features.category_max_capacity,
                ],
                output=features.max_capacity,
            ),
        ),
        Operator(
            id="bearing_temperature_by_pump",
            interface=Interface(
                inputs=[ref.feature("bearing_temperature")],
                outputs=[features.bearing_temperature_max],
            ),
            compute=Binding(
                analytics.aggregate,
                dataset=ref.dataset("pump_telemetry"),
                aggregations={"bearing_temperature": "max"},
                dimensions=ref.profile().grain.ids,
                rename={"bearing_temperature": features.bearing_temperature_max},
            ),
            merge=merge.default(),
        ),
        Operator(
            interface=Interface(
                inputs=[features.bearing_temperature_max],
                outputs=[features.health_signal_normalized],
            ),
            compute=Binding(
                analytics.min_max_scale,
                dataset=ref.dataset(),
                feature=features.bearing_temperature_max,
                lower_bound=-1.0,
                upper_bound=1.0,
                features=[features.bearing_temperature_max],
                output=features.health_signal_normalized,
            ),
        ),
        Operator(
            interface=Interface(
                outputs=[features.measurement, features.reference_value],
            ),
            compute=Binding(
                io.read_file,
                source=ref.paths("pump_external_inputs_source"),
                schema={"measurement": "float", "reference_value": "float"},
                rename={
                    "measurement": features.measurement,
                    "reference_value": features.reference_value,
                },
            ),
            merge=Binding(
                merge_functions.merge_pump_inputs,
                dataset=ref.dataset(),
                fragment=ref.fragment(),
                dataset_identifiers=[
                    dimension.MACHINE_DIMENSION.resolution("machine").key,
                    dimension.FACILITY_DIMENSION.resolution("server_room").key,
                    dimension.FACILITY_DIMENSION.resolution("data_center").key,
                ],
            ),
        ),
        Operator(
            interface=Interface(
                inputs=[features.measurement, features.reference_value],
                outputs=[features.ratio],
            ),
            compute=Binding(
                io.process_pump_external_workflow,
                source=ref.paths("pump_external_inputs_source"),
                output=ref.paths("pump_external_workflow_output"),
            ),
        ),
        Operator(
            interface=Interface(outputs=[]),
            compute=Binding(
                io.write_file,
                dataset=ref.dataset(),
                features=[
                    features.pump_max_capacity,
                    features.series_max_capacity,
                    features.category_max_capacity,
                    features.max_capacity,
                    features.measurement,
                    features.reference_value,
                    features.bearing_temperature_max,
                    features.health_signal_normalized,
                ],
                output=ref.paths("pump_output"),
            ),
        ),
    ]
