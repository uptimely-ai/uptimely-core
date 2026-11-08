"""Pump-level profile and declarative dataframe transformations."""

from examples.pump_analytics.functions import analytics, external_workflow
from examples.pump_analytics.spec import dimension

from uptimely import Binding, Feature, FeatureSet, Grain, Interface, Operator, Profile, ref
from uptimely.spec import feature_types


class PumpFeatures(FeatureSet):
    """Features declared by the pump profile."""

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

    id = "pump_profile"
    name = "Pump Summary"
    description = "One row per pump with collapsed condition and workflow inputs."
    category = "Machines"
    grain = [Grain(dimension.MACHINE, "machine")]
    scope = "Pump-level telemetry and external workflow inputs"
    features = PumpFeatures()

    assembly = [
        Operator(
            id="bearing_temperature_by_pump",
            interface=Interface(
                inputs=[ref.feature("bearing_temperature")],
                outputs=[features.bearing_temperature_max],
            ),
            compute=Binding(
                function=analytics.aggregate,
                arguments=dict(
                    dataset=ref.data("pump_telemetry"),
                    feature=ref.feature("bearing_temperature"),
                    method="max",
                    dimensions=ref.profile().grain.ids,
                    output=features.bearing_temperature_max,
                ),
            ),
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
                    dataset=ref.data(),
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
                function=external_workflow.read_pump_external_inputs,
                arguments={},
            ),
            merge=Binding(
                function=external_workflow.merge_pump_inputs,
                arguments={
                    "target": ref.data(),
                    "fragment": ref.fragment(),
                    "target_keys": ref.profile().grain.ids,
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
