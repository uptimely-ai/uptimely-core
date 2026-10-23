"""Entity declaration for the simple analytics example."""

from uptimely.spec.python import Dimension, Entity

ID = Dimension(
    id="id",
    type="integer",
    description="Stable identifier for each input row",
)

SIMPLE_ANALYTICS = Entity(
    id="simple_analytics",
    name="Simple analytics",
    dimensions=[ID],
    description="Simple analytics entity.",
)
