"""Worked example: does the Earth's rotation steer a flow? — Coriolis parameter and Rossby number.

The Earth's rotation deflects any moving air or water through the Coriolis effect, but whether that
deflection actually shapes a flow depends on its scale. A continent-spanning weather system is ruled
by rotation; water draining from a sink is not. The Rossby number settles it by comparing the flow's
own inertia to the Coriolis effect, using the local Coriolis parameter set by latitude.

This example takes a mid-latitude location (45 deg) on Earth (rotation rate 7.292e-5 rad/s). The
Coriolis parameter there is about 1.03e-4 /s. For a synoptic weather system — wind about 10 m/s over
a 1000 km scale — the Rossby number is about 0.10, well below 1, so rotation dominates and the flow
runs nearly along the isobars (geostrophic). For a 1 m draining sink at the same 10 m/s, the Rossby
number is about 1e5, so the Coriolis effect is utterly negligible — the folk claim that it sets a
sink's swirl is off by many orders of magnitude. The example reports the Coriolis parameter and both
Rossby numbers.

Run it directly (``python examples/coriolis_weather_scale.py``);
:func:`rotation_matters` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import coriolis_parameter, rossby_number
from anvilate.units import Quantity

EARTH_ROTATION = Quantity(magnitude=7.292e-5, unit="rad/s")
LATITUDE = 45.0
FLOW_SPEED = Quantity.parse("10 m/s")
WEATHER_SCALE = Quantity.parse("1000 km")
SINK_SCALE = Quantity.parse("1 m")


def rotation_matters() -> dict[str, float]:
    """Return the Coriolis parameter and the Rossby number for a weather system and a sink."""
    f = coriolis_parameter(angular_velocity=EARTH_ROTATION, latitude=LATITUDE)
    weather_rossby = rossby_number(
        velocity=FLOW_SPEED, coriolis_parameter=f, length_scale=WEATHER_SCALE
    )
    sink_rossby = rossby_number(velocity=FLOW_SPEED, coriolis_parameter=f, length_scale=SINK_SCALE)
    return {
        "coriolis_parameter_per_s": f.to("1/s").magnitude,
        "weather_rossby": weather_rossby,
        "sink_rossby": sink_rossby,
    }


def main() -> None:
    d = rotation_matters()
    print(f"Coriolis parameter at 45 deg: {d['coriolis_parameter_per_s']:.2e} /s")
    print(f"weather-system Rossby number: {d['weather_rossby']:.2f} (rotation dominates)")
    print(f"draining-sink Rossby number:  {d['sink_rossby']:.1e} (rotation negligible)")


if __name__ == "__main__":
    main()
