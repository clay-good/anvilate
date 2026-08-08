"""Worked example: a rotating-analyzer polarizer used as a light attenuator.

Two polarizers in series make a simple variable attenuator: the first fixes the polarization, and
rotating the second (the analyzer) dims the beam by Malus's law. The unpolarized-light half-law sets
what the first polarizer passes, Malus's law sets what the analyzer passes, and inverting it gives
the angle to dial in for a wanted attenuation.

Unpolarized sunlight at 1,000 W/m^2 hits the first polarizer, which passes half — 500 W/m^2 — now
fully polarized. Setting the analyzer at 30 degrees to that polarization passes cos^2(30 deg) = 75%
of it, about 375 W/m^2. To instead cut the polarized beam to a quarter of its intensity (125 W/m^2),
Malus's law inverts to an analyzer angle of 60 degrees. This example reports the intensity after the
first polarizer, the intensity through a 30-degree analyzer, and the angle for a 25% transmission.

Run it directly (``python examples/polarizer_attenuator.py``);
:func:`polarizer_attenuation` is also exercised in the test suite.
"""

from __future__ import annotations

from math import degrees, radians

from anvilate.analysis import (
    malus_angle_for_intensity,
    malus_transmitted_intensity,
    unpolarized_transmitted_intensity,
)
from anvilate.units import Quantity

SUNLIGHT = Quantity(magnitude=1000.0, unit="W/m**2")
ANALYZER_ANGLE_DEG = 30.0
TARGET_FRACTION = 0.25


def polarizer_attenuation() -> dict[str, float]:
    """Return the post-polarizer intensity, the 30-degree transmission, and the 25% angle."""
    after_first = unpolarized_transmitted_intensity(incident_intensity=SUNLIGHT)
    after_analyzer = malus_transmitted_intensity(
        incident_intensity=after_first, angle=radians(ANALYZER_ANGLE_DEG)
    )
    angle = malus_angle_for_intensity(
        incident_intensity=after_first,
        transmitted_intensity=Quantity(
            magnitude=TARGET_FRACTION * after_first.to("W/m**2").magnitude, unit="W/m**2"
        ),
    )
    return {
        "after_first_polarizer_w_m2": after_first.to("W/m**2").magnitude,
        "after_analyzer_w_m2": after_analyzer.to("W/m**2").magnitude,
        "angle_for_25pct_deg": degrees(angle),
    }


def main() -> None:
    d = polarizer_attenuation()
    print(f"after first polarizer: {d['after_first_polarizer_w_m2']:.0f} W/m^2")
    print(f"through 30-deg analyzer: {d['after_analyzer_w_m2']:.0f} W/m^2")
    print(f"angle for 25% transmission: {d['angle_for_25pct_deg']:.0f} deg")


if __name__ == "__main__":
    main()
