"""Declared dataframe boundary for the pump-level uncontrolled workflow."""

from examples.pump_analytics.functions import external_workflow
from examples.pump_analytics.spec import dimension

from uptimely import Action, Feature, Grain, Profile, ref


class PumpExternalWorkflow(Profile):
    """Declare the logical inputs and output of a workflow that owns its I/O."""

    id = "pump_external_workflow_dataset"
    name = "Pump External Workflow"
    description = "Pump-level inputs and outputs for an uncontrolled local workflow."
    category = "assets"
    grain = [Grain(dimension.MACHINE, "machine")]

    producers = [
        Action(
            id="read_pump_external_inputs",
            function=external_workflow.read_pump_external_inputs,
            arguments={},
            outputs=[
                Feature(
                    id="measurement",
                    type="float",
                    description="Measured pump value provided to the external workflow.",
                ),
                Feature(
                    id="reference_value",
                    type="float",
                    description="Reference value used to normalize the pump measurement.",
                ),
            ],
        )
    ]
    pipelines = [
        Action(
            id="process_pump_external_workflow",
            function=external_workflow.process_pump_external_workflow,
            arguments={},
            inputs=[ref.column("measurement"), ref.column("reference_value")],
            outputs=[
                Feature(
                    id="ratio",
                    type="float",
                    description="Pump measurement divided by its reference value.",
                )
            ],
        )
    ]
