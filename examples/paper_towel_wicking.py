"""Worked example: water wicking up a paper strip (Washburn imbibition).

Dip the edge of a paper strip in water and it climbs on its own, sucked up by the fine pores between
the fibers. The Washburn law describes the climb: capillary suction pulls the water in while viscous
drag holds it back, so the wet front advances as the square root of time — quick at first, then
crawling.

Modeling the paper as pores of 10 micrometre radius, with water (surface tension 0.0728 N/m,
viscosity 0.001 Pa·s) that wets the fibers perfectly (contact angle 0), the driving suction is about
14.6 kPa. In one second the water wicks about 19 mm up the strip; to reach 50 mm takes about 6.9
seconds, far longer than a linear guess because the time grows with the square of the distance. This
example reports the capillary pressure, the penetration in one second, and the time to reach 50 mm.

Run it directly (``python examples/paper_towel_wicking.py``);
:func:`paper_wicking` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    washburn_capillary_pressure,
    washburn_penetration_length,
    washburn_penetration_time,
)
from anvilate.units import Quantity

SURFACE_TENSION = Quantity(magnitude=0.0728, unit="N/m")  # water in air
PORE_RADIUS = Quantity(magnitude=1e-5, unit="m")  # 10 micrometres
VISCOSITY = Quantity(magnitude=0.001, unit="Pa*s")  # water
CONTACT_ANGLE = 0.0  # perfect wetting
TIME = Quantity(magnitude=1.0, unit="s")
TARGET_LENGTH = Quantity(magnitude=0.05, unit="m")  # 50 mm


def paper_wicking() -> dict[str, float]:
    """Return the capillary pressure, the 1 s penetration, and the time to reach 50 mm."""
    pressure = washburn_capillary_pressure(
        surface_tension=SURFACE_TENSION, pore_radius=PORE_RADIUS, contact_angle=CONTACT_ANGLE
    )
    length = washburn_penetration_length(
        surface_tension=SURFACE_TENSION,
        pore_radius=PORE_RADIUS,
        viscosity=VISCOSITY,
        time=TIME,
        contact_angle=CONTACT_ANGLE,
    )
    time = washburn_penetration_time(
        surface_tension=SURFACE_TENSION,
        pore_radius=PORE_RADIUS,
        viscosity=VISCOSITY,
        length=TARGET_LENGTH,
        contact_angle=CONTACT_ANGLE,
    )
    return {
        "capillary_pressure_kpa": pressure.to("Pa").magnitude / 1000.0,
        "penetration_1s_mm": length.to("m").magnitude * 1000.0,
        "time_to_50mm_s": time.to("s").magnitude,
    }


def main() -> None:
    d = paper_wicking()
    print(f"capillary pressure: {d['capillary_pressure_kpa']:.1f} kPa")
    print(f"penetration in 1 s: {d['penetration_1s_mm']:.1f} mm")
    print(f"time to reach 50 mm: {d['time_to_50mm_s']:.1f} s")


if __name__ == "__main__":
    main()
