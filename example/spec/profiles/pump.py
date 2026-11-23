"""Cooling-pump profile and declarative dataframe transformations."""

import pump_analytics as analytics
import pump_io as io
import pump_merge as merge_functions
from spec import dimension

from uptimely import Bind, Feature, FeatureSet, Operator, Profile, merge, ref
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
    seed = "read_pump_assets"

    assembly = [
        Operator(
            id="read_pump_assets",
            outputs=[features.pump_max_capacity],
            compute=Bind(
                io.read_file,
                source=ref.paths("pump_assets_source"),
                rename={"max_capacity": ref.output("pump_max_capacity")},
                schema={"max_capacity": "float"},
            ),
        ),
        Operator(
            compute=Bind(
                analytics.select_columns,
                dataset=ref.dataset("pump_series"),
                columns=[
                    dimension.MACHINE_DIMENSION.resolution("machine_series").key,
                    ref.input("max_capacity_series"),
                ],
                rename={"max_capacity_series": ref.output("series_max_capacity")},
            ),
            merge=merge.default(),
        ),
        Operator(
            compute=Bind(
                analytics.select_columns,
                dataset=ref.dataset("pump_category"),
                columns=[
                    dimension.MACHINE_DIMENSION.resolution("machine_category").key,
                    ref.input("max_capacity_category"),
                ],
                rename={"max_capacity_category": ref.output("category_max_capacity")},
            ),
            merge=merge.default(),
        ),
        Operator(
            compute=Bind(
                analytics.first_non_null_value,
                dataset=ref.dataset(),
                features=[
                    ref.input("pump_max_capacity"),
                    ref.input("series_max_capacity"),
                    ref.input("category_max_capacity"),
                ],
                output=ref.output("max_capacity"),
            ),
        ),
        Operator(
            id="bearing_temperature_by_pump",
            inputs=[ref.input("bearing_temperature")],
            compute=Bind(
                analytics.aggregate,
                dataset=ref.dataset("pump_telemetry"),
                aggregations={"bearing_temperature": "max"},
                dimensions=ref.profile().grain.ids,
                rename={"bearing_temperature": ref.output("bearing_temperature_max")},
            ),
            merge=merge.default(),
        ),
        Operator(
            compute=Bind(
                analytics.min_max_scale,
                dataset=ref.dataset(),
                feature=ref.input("bearing_temperature_max"),
                lower_bound=-1.0,
                upper_bound=1.0,
                features=[ref.input("bearing_temperature_max")],
                output=ref.output("health_signal_normalized"),
            ),
        ),
        Operator(
            outputs=[features.measurement, features.reference_value],
            compute=Bind(
                io.read_file,
                source=ref.paths("pump_external_inputs_source"),
                schema={"measurement": "float", "reference_value": "float"},
                rename={
                    "measurement": ref.output("measurement"),
                    "reference_value": ref.output("reference_value"),
                },
            ),
            merge=Bind(
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
            inputs=[ref.input("measurement"), ref.input("reference_value")],
            compute=Bind(
                io.process_pump_external_workflow,
                source=ref.paths("pump_external_inputs_source"),
                output=ref.paths("pump_external_workflow_output"),
            ),
        ),
        Operator(
            compute=Bind(
                io.write_file,
                dataset=ref.dataset(),
                features=[
                    ref.input("pump_max_capacity"),
                    ref.input("series_max_capacity"),
                    ref.input("category_max_capacity"),
                    ref.input("max_capacity"),
                    ref.input("measurement"),
                    ref.input("reference_value"),
                    ref.input("bearing_temperature_max"),
                    ref.input("health_signal_normalized"),
                ],
                output=ref.paths("pump_output"),
            ),
        ),
    ]
