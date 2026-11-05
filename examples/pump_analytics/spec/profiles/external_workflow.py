"""Declared profile boundary for the pump-level uncontrolled workflow."""

from examples.pump_analytics.functions import external_workflow
from examples.pump_analytics.spec import dimension

from uptimely import Action, Feature, FeatureSet, Grain, Profile, ref


class PumpExternalWorkflowFeatures(FeatureSet):
    """Features declared by the external-workflow profile."""

    measurement = Feature(
        id="measurement",
        type="float",
        description="Measured pump value provided to the external workflow.",
    )
    reference_value = Feature(
        id="reference_value",
        type="float",
        description="Reference value used to normalize the pump measurement.",
    )
    ratio = Feature(
        id="ratio",
        type="float",
        description="Pump measurement divided by its reference value.",
    )


class PumpExternalWorkflow(Profile):
    """Declare the logical inputs and output of a workflow that owns its I/O."""

    id = "pump_external_workflow"
    name = "Pump External Workflow"
    description = "Pump-level inputs and outputs for an uncontrolled local workflow."
    category = "Machines"
    grain = [Grain(dimension.MACHINE, "machine")]
    features = PumpExternalWorkflowFeatures()

    actions = [
        Action(
            id="read_pump_external_inputs",
            function=external_workflow.read_pump_external_inputs,
            arguments={},
            outputs=[features.measurement, features.reference_value],
        ),
        Action(
            id="process_pump_external_workflow",
            function=external_workflow.process_pump_external_workflow,
            arguments={},
            inputs=[ref.column("measurement"), ref.column("reference_value")],
            outputs=[features.ratio],
        ),
    ]
