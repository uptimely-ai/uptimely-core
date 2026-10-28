"""Combined spec declarations for the pump analytics project."""

from uptimely import Spec

from . import dimension, entity
from .datasets.external_workflow import PumpExternalWorkflow
from .datasets.pump import Pump
from .datasets.telemetry import Telemetry

python_spec = Spec(
    dimensions=[dimension.PLANT, dimension.PRODUCTION_LINE, dimension.PUMP, dimension.TIMESTAMP],
    entities=entity.entities,
    datasets=[Telemetry, Pump, PumpExternalWorkflow],
    name="Pump analytics",
)
