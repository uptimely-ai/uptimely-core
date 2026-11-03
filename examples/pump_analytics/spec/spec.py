"""Combined spec declarations for the pump analytics project."""

from uptimely import Spec

from .profiles.constants import Constants
from .profiles.external_workflow import PumpExternalWorkflow
from .profiles.pump import Pump
from .profiles.telemetry import Telemetry

python_spec = Spec(
    profiles=[Telemetry, Pump, PumpExternalWorkflow, Constants],
    name="Pump analytics",
)
