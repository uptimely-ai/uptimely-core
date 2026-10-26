"""Combined spec declarations for the pump analytics project."""

from uptimely.spec.python import PythonSpec

from .datasets.pump import Pump
from .datasets.telemetry import Telemetry

python_spec = PythonSpec(
    datasets=[Telemetry, Pump],
    name="Pump analytics",
)
