"""Combined spec declarations for the data-center cooling pump project."""

from uptimely import Spec

from .profiles.constants import Constants
from .profiles.pump import Pump
from .profiles.pump_category import PumpCategory
from .profiles.pump_series import PumpSeries
from .profiles.pump_telemetry import PumpTelemetry
from .profiles.pump_telemetry_by_day import PumpTelemetryByDay
from .profiles.pump_telemetry_by_hour import PumpTelemetryByHour
from .profiles.pump_telemetry_by_hour_when_warning import PumpTelemetryByHourWhenWarning
from .profiles.pump_telemetry_by_minute import PumpTelemetryByMinute
from .profiles.pump_telemetry_when_warning import PumpTelemetryWhenWarning

python_spec = Spec(
    profiles=[
        PumpTelemetry,
        Pump,
        Constants,
        PumpSeries,
        PumpCategory,
        PumpTelemetryByMinute,
        PumpTelemetryWhenWarning,
        PumpTelemetryByHourWhenWarning,
        PumpTelemetryByHour,
        PumpTelemetryByDay,
    ],
    name="Data center cooling pump analytics",
)
