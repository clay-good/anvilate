"""Worked example: sizing an office lighting layout, and checking a high-bay's spread.

Lighting design runs in two directions. To lay out a room you work the lumen method backwards —
from the illuminance a task needs, how many luminaires does the ceiling require? This example lights
a 10 m × 8 m open office to 400 lux (a normal reading/screen-work level) with 3400-lumen LED
troffers, discounting for a coefficient of utilization of 0.62 (room geometry and surface
reflectances) and a light loss factor of 0.8 (dirt and lamp aging). The inverse asks for ~19
luminaires; a real ceiling tiles them 5 × 4 = 20, and the example confirms that installed grid
clears the target with a little margin.

The second direction is a single luminaire's reach: a high-bay fitting hung over a workbench acts as
a point source, so its illuminance falls off as the inverse-square cosine law. The example finds the
lux directly under a 20,000 cd high-bay 6 m up, then 3 m off to the side — where both the longer
throw and the oblique incidence pull the level down.

Run it directly (``python examples/office_lighting_layout.py``);
:func:`lighting_layout` is also exercised in the test suite.
"""

from __future__ import annotations

import math

from anvilate.analysis import (
    lumen_method_illuminance,
    lumen_method_luminaire_count,
    point_source_illuminance,
)
from anvilate.units import Quantity

ROOM_AREA = Quantity.parse("80 m**2")  # 10 m x 8 m open office
TARGET = Quantity.parse("400 lux")  # office reading / screen-work level
LUMINAIRE_FLUX = Quantity.parse("3400 lumen")  # one LED troffer
CU = 0.62  # coefficient of utilization
LLF = 0.8  # light loss factor (maintenance)
INSTALLED_GRID = 20  # a 5 x 4 ceiling layout

HIGH_BAY_INTENSITY = Quantity.parse("20000 cd")
MOUNTING_HEIGHT = Quantity.parse("6 m")
SIDE_OFFSET = Quantity.parse("3 m")


def lighting_layout() -> dict[str, float]:
    """Return the required/installed luminaire counts and achieved and point-source lux."""
    exact = lumen_method_luminaire_count(
        target_illuminance=TARGET,
        area=ROOM_AREA,
        lumens_per_luminaire=LUMINAIRE_FLUX,
        coefficient_of_utilization=CU,
        light_loss_factor=LLF,
    )
    achieved = lumen_method_illuminance(
        luminaire_count=INSTALLED_GRID,
        lumens_per_luminaire=LUMINAIRE_FLUX,
        coefficient_of_utilization=CU,
        light_loss_factor=LLF,
        area=ROOM_AREA,
    )
    # High-bay point source: directly below, then offset to the side.
    below = point_source_illuminance(
        luminous_intensity=HIGH_BAY_INTENSITY, distance=MOUNTING_HEIGHT
    )
    h = MOUNTING_HEIGHT.to("m").magnitude
    s = SIDE_OFFSET.to("m").magnitude
    slant = Quantity(magnitude=math.hypot(h, s), unit="m")
    offset = point_source_illuminance(
        luminous_intensity=HIGH_BAY_INTENSITY,
        distance=slant,
        incidence_angle=math.atan2(s, h),
    )
    return {
        "required_count": exact,
        "installed_count": INSTALLED_GRID,
        "achieved_lux": achieved.to("lux").magnitude,
        "highbay_below_lux": below.to("lux").magnitude,
        "highbay_offset_lux": offset.to("lux").magnitude,
    }


def main() -> None:
    r = lighting_layout()
    target = TARGET.to("lux").magnitude
    print(f"office needs {r['required_count']:.1f} troffers -> install {r['installed_count']}")
    print(f"  installed grid delivers {r['achieved_lux']:.0f} lux (target {target:.0f})")
    print(f"high-bay: {r['highbay_below_lux']:.0f} lux directly below, 6 m up")
    print(f"  {r['highbay_offset_lux']:.0f} lux 3 m to the side (longer throw + oblique incidence)")


if __name__ == "__main__":
    main()
