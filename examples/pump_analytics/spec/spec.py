"""Combined spec declarations for the pump analytics project."""

from uptimely import Spec

from .profiles.constants import Constants
from .profiles.pump import Pump
from .profiles.telemetry import Telemetry

python_spec = Spec(
    profiles=[Telemetry, Pump, Constants],
    name="Pump analytics",
)
