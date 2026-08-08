"""Worked example: the summer-solstice sun position for a mid-latitude PV site.

Before sizing a solar array you need to know where the sun is: how far north the sun has swung, how
high it climbs at midday, and how much atmosphere its light crosses. These three numbers fix the
tilt and the resource for a fixed panel.

At a site at 40 degN on the June solstice (day 172), the solar declination is +23.45 degrees — the
sun's farthest swing north. At solar noon it stands about 73.45 degrees above the horizon, so a
panel tilted only about 17 degrees from horizontal faces it squarely. At that high sun the light
crosses an air mass of about 1.04 — nearly the straight-down minimum, much clearer than the AM1.5
point. This example reports the declination, the solar-noon altitude, and the air mass.

Run it directly (``python examples/summer_solar_position.py``);
:func:`solstice_sun_position` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    air_mass,
    solar_altitude_at_noon,
    solar_declination,
)

LATITUDE_DEG = 40.0
DAY_OF_YEAR = 172  # June solstice


def solstice_sun_position() -> dict[str, float]:
    """Return the solar declination, the solar-noon altitude, and the air mass."""
    declination = solar_declination(day_of_year=DAY_OF_YEAR)
    altitude = solar_altitude_at_noon(
        latitude=LATITUDE_DEG, declination=declination.to("degree").magnitude
    )
    am = air_mass(solar_altitude=altitude.to("degree").magnitude)
    return {
        "declination_deg": declination.to("degree").magnitude,
        "noon_altitude_deg": altitude.to("degree").magnitude,
        "air_mass": am,
    }


def main() -> None:
    d = solstice_sun_position()
    print(f"solar declination: {d['declination_deg']:.2f} deg")
    print(f"solar-noon altitude: {d['noon_altitude_deg']:.2f} deg")
    print(f"air mass: {d['air_mass']:.3f}")


if __name__ == "__main__":
    main()
