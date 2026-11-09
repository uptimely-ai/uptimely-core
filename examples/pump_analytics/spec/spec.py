"""Combined spec declarations for the pump analytics project."""

from uptimely import Spec

from .profiles.constants import Constants
from .profiles.pump import Pump
from .profiles.pump_telemetry import PumpTelemetry

python_spec = Spec(
    profiles=[PumpTelemetry, Pump, Constants],
    name="Pump analytics",
)
