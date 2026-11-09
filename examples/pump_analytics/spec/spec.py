"""Combined spec declarations for the pump analytics project."""

from uptimely import Spec

from .profiles.constants import Constants
from .profiles.pump import Pump
from .profiles.pump_category import PumpCategory
from .profiles.pump_series import PumpSeries
from .profiles.pump_telemetry import PumpTelemetry
from .profiles.pump_telemetry_by_day import PumpTelemetryByDay
from .profiles.pump_telemetry_by_hour import PumpTelemetryByHour
from .profiles.pump_telemetry_by_minute import PumpTelemetryByMinute

python_spec = Spec(
    profiles=[
        PumpTelemetry,
        Pump,
        Constants,
        PumpSeries,
        PumpCategory,
        PumpTelemetryByMinute,
        PumpTelemetryByHour,
        PumpTelemetryByDay,
    ],
    name="Pump analytics",
)
