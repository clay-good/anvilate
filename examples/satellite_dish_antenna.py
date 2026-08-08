"""Worked example: the gain, beamwidth, and sizing of a satellite dish antenna.

A parabolic dish concentrates radio energy into a narrow beam, and its performance follows from its
size and the wavelength. Designing or specifying one turns on three numbers: the gain the aperture
delivers, how narrow (and therefore how pointing-critical) the beam is, and how big a dish a target
gain demands. This example works them for a Ku-band dish.

The dish is a 3 m parabola at 10 GHz (wavelength 30 mm) with a realistic 60% aperture efficiency.
Its effective area of about 4.24 m^2 (a 3 m circle at 60%) gives a gain near 48 dBi. The half-power
beamwidth is only about 0.7 degrees, so the dish must be pointed to a fraction of a degree. Turned
around, reaching a 45 dBi (about 31600x) gain at the same frequency needs a 2.2 m dish. The example
reports the dish gain, its beamwidth, and the diameter for a 45 dBi target.

Run it directly (``python examples/satellite_dish_antenna.py``);
:func:`dish_design` is also exercised in the test suite.
"""

from __future__ import annotations

from math import log10, pi

from anvilate.analysis import (
    aperture_antenna_gain,
    dish_diameter_for_gain,
    parabolic_beamwidth,
)
from anvilate.units import Quantity

DISH_DIAMETER = Quantity.parse("3 m")
WAVELENGTH = Quantity.parse("30 mm")  # 10 GHz
EFFICIENCY = 0.6
TARGET_GAIN_DBI = 45.0


def dish_design() -> dict[str, float]:
    """Return the dish gain (dBi), the beamwidth (deg), and the diameter for a 45 dBi target."""
    area = Quantity(magnitude=pi * (DISH_DIAMETER.to("m").magnitude / 2.0) ** 2, unit="m**2")
    gain = aperture_antenna_gain(aperture_area=area, wavelength=WAVELENGTH, efficiency=EFFICIENCY)
    beamwidth = parabolic_beamwidth(diameter=DISH_DIAMETER, wavelength=WAVELENGTH)
    target_gain_linear = 10 ** (TARGET_GAIN_DBI / 10)
    diameter = dish_diameter_for_gain(
        gain=target_gain_linear, wavelength=WAVELENGTH, efficiency=EFFICIENCY
    )
    return {
        "dish_gain_dbi": 10 * log10(gain),
        "beamwidth_deg": beamwidth,
        "diameter_for_45dbi_m": diameter.to("m").magnitude,
    }


def main() -> None:
    d = dish_design()
    print(f"3 m dish gain: {d['dish_gain_dbi']:.0f} dBi")
    print(f"half-power beamwidth: {d['beamwidth_deg']:.1f} deg")
    print(f"diameter for 45 dBi: {d['diameter_for_45dbi_m']:.1f} m")


if __name__ == "__main__":
    main()
