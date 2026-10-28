"""Declared dataframe boundary for the pump-level uncontrolled workflow."""

from examples.pump_analytics.functions import external_workflow
from examples.pump_analytics.spec import entity

from uptimely import Action, Dataset, Feature, RowScope, ref


class PumpExternalWorkflow(Dataset):
    """Declare the pump inputs and output of a workflow that owns its I/O."""

    id = "pump_external_workflow_dataset"
    description = "Pump-level inputs and outputs for an uncontrolled local workflow."
    entity = entity.PUMP
    row_scope = RowScope(grain="One row per pump")

    producers = [
        Action(
            id="read_pump_external_inputs",
            function=external_workflow.read_pump_external_inputs,
            arguments={},
            outputs=[
                Feature(name="measurement", type="float"),
                Feature(name="reference_value", type="float"),
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
                    name="ratio",
                    type="float",
                    description="Measurement divided by its reference value.",
                )
            ],
        )
    ]
