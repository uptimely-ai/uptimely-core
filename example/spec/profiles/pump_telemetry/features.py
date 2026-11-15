"""Feature declarations for the cooling-pump telemetry profile."""

from uptimely import Feature, FeatureSet


class TelemetryFeatures(FeatureSet):
    """Features declared by the cooling-pump telemetry profile."""

    differential_pressure = Feature(
        type="float",
        unit="bar",
        description="Differential pressure across the cooling-water pump.",
    )
    flow_rate = Feature(
        type="float",
        unit="m3/h",
        description="Cooling-water circulation flow rate.",
    )
    bearing_temperature = Feature(
        type="float",
        unit="C",
        description="Drive-end motor-bearing temperature.",
    )
    vibration_rms = Feature(
        type="float",
        unit="mm/s",
        description="Overall cooling-pump vibration RMS.",
    )
    motor_power = Feature(
        type="float",
        unit="kW",
        description="Active electric power consumed by the cooling-pump motor.",
    )
    mode = Feature(
        type="string",
        description=(
            "Flow band: below_rated_flow or at_or_above_rated_flow, based on rated "
            "cooling-water flow."
        ),
    )
    pump_mode = Feature(
        type="string",
        description=(
            "Illustrative condition mode: warning when bearing temperature is at least "
            "90 C or vibration is at least 4.5 mm/s, otherwise operational. Null for "
            "incomplete or non-finite readings unless a warning is established."
        ),
    )
    pressure_flow_efficiency = Feature(
        type="float",
        description=(
            "Hydraulic efficiency proxy from cooling-water differential pressure, "
            "flow, and motor power."
        ),
    )
    room_temperature_reference = Feature(
        type="float",
        unit="C",
        description="Pump-room ambient-temperature reference broadcast to each row.",
    )
    bearing_temperature_rise = Feature(
        type="float",
        unit="C",
        description="Motor-bearing temperature rise above the pump-room ambient reference.",
    )
    bearing_temperature_delta = Feature(
        type="float",
        unit="C",
        description="Motor-bearing temperature change from the previous pump reading.",
    )
    vibration_delta = Feature(
        unit="mm/s",
        description="Vibration change from the previous cooling-pump reading.",
    )
    pump_health_score = Feature(
        type="float",
        description=(
            "Illustrative cooling-pump condition score from motor-bearing temperature "
            "trend, vibration trend, and hydraulic efficiency proxy."
        ),
    )
