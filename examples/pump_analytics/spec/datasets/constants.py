"""Project-wide physical constants."""

from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import entity

from uptimely import Action, Dataset, Feature, RowScope, ref


class Constants(Dataset):
    """One row containing project-wide physical constants."""

    id = "constants_dataset"
    description = "Physical constants used by pump analytics."
    entity = entity.CONSTANTS
    row_scope = RowScope(grain="One row per project")

    producers = [
        Action(
            id="read_constants",
            function=analytics.read_constants,
            arguments={"source": ref.source("constants_source")},
            outputs=[
                Feature(name="gravity", type="float", unit="m/s^2"),
                Feature(name="room_temperature", type="float", unit="C"),
            ],
        )
    ]
