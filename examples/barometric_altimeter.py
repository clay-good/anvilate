"""Worked example: the barometric law behind a pressure altimeter.

The atmosphere is a compressible gas column, so its pressure decays exponentially — not linearly —
with altitude. The scale height sets the rate of that decay, the barometric formula gives the
pressure at any height, and inverting it turns a measured pressure back into an altitude, which is
exactly how an aircraft's pressure altimeter works.

Taking dry air at 15 °C (288.15 K) with a sea-level pressure of 101,325 Pa, the scale height is
about 8.4 km — the altitude over which the pressure falls by a factor of e. At a 2,000 m cruise the
barometric formula gives roughly 79,900 Pa, about 79% of sea-level pressure. Feeding a measured
90,000 Pa back through the inverse recovers an altitude of about 1,000 m. This example reports the
scale height, the pressure at 2,000 m, and the altitude for a 90 kPa reading.

Run it directly (``python examples/barometric_altimeter.py``);
:func:`altimeter_readings` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    barometric_altitude,
    barometric_pressure,
    scale_height,
)
from anvilate.units import Quantity

SEA_LEVEL_PRESSURE = Quantity(magnitude=101325.0, unit="Pa")
TEMPERATURE = Quantity(magnitude=288.15, unit="K")  # 15 degC
CRUISE_ALTITUDE = Quantity(magnitude=2000.0, unit="m")
MEASURED_PRESSURE = Quantity(magnitude=90000.0, unit="Pa")


def altimeter_readings() -> dict[str, float]:
    """Return the scale height, pressure at cruise, and altitude for a measured pressure."""
    h_scale = scale_height(temperature=TEMPERATURE)
    p_cruise = barometric_pressure(
        sea_level_pressure=SEA_LEVEL_PRESSURE,
        altitude=CRUISE_ALTITUDE,
        temperature=TEMPERATURE,
    )
    altitude = barometric_altitude(
        sea_level_pressure=SEA_LEVEL_PRESSURE,
        pressure=MEASURED_PRESSURE,
        temperature=TEMPERATURE,
    )
    return {
        "scale_height_km": h_scale.to("m").magnitude / 1000.0,
        "pressure_at_2km_pa": p_cruise.to("Pa").magnitude,
        "altitude_for_90kpa_m": altitude.to("m").magnitude,
    }


def main() -> None:
    d = altimeter_readings()
    print(f"scale height: {d['scale_height_km']:.2f} km")
    print(f"pressure at 2 km: {d['pressure_at_2km_pa']:.0f} Pa")
    print(f"altitude for 90 kPa: {d['altitude_for_90kpa_m']:.0f} m")


if __name__ == "__main__":
    main()
