"""Combined spec declarations for the pump analytics project."""

from uptimely.spec.python import PythonSpec

from . import entity
from .datasets.pump import Pump
from .datasets.telemetry import Telemetry

python_spec = PythonSpec(
    datasets={
        entity.PUMP_TELEMETRY: [Telemetry()],
        entity.PUMP: [Pump()],
    },
    name="Pump analytics",
)
