"""Worked example: the force on a submerged gate acts lower than you'd guess.

A rectangular gate holds back water in a channel. Finding the total push is the easy part —
it's the pressure at the gate's mid-height times its area. The subtlety that sizes the hinge
and the operating gear is *where* that push acts. Because water pressure grows with depth, the
lower half of the gate is loaded harder than the upper half, so the resultant does not act at
the gate's centroid but below it, at the center of pressure. For a gate whose top sits at the
water surface that point lands at two-thirds of the depth, not one-half — a third again lower
than the naive centroid assumption, and exactly the lever arm the hinge moment depends on. This
example works a 3 m tall, 2 m wide surface-piercing gate and shows the force and its true line
of action.

Run it directly (``python examples/submerged_gate_hinge.py``);
:func:`gate_loads` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    center_of_pressure_depth,
    hydrostatic_force_on_plane,
    hydrostatic_pressure,
)
from anvilate.units import Quantity

WATER_DENSITY = Quantity.parse("1000 kg/m**3")
GATE_HEIGHT = Quantity.parse("3 m")
GATE_WIDTH = Quantity.parse("2 m")
# The gate's top is at the free surface, so its centroid is at half its height.
CENTROID_DEPTH = Quantity.parse("1.5 m")


def gate_loads() -> dict[str, float]:
    """Return the base pressure (kPa), resultant force (kN), and center-of-pressure depth (m)."""
    h = GATE_HEIGHT.to("m").magnitude
    b = GATE_WIDTH.to("m").magnitude
    area = Quantity(magnitude=b * h, unit="m**2")
    second_moment = Quantity(magnitude=b * h**3 / 12.0, unit="m**4")  # b*h^3/12, centroidal
    base_pressure = hydrostatic_pressure(depth=GATE_HEIGHT, density=WATER_DENSITY)
    force = hydrostatic_force_on_plane(
        density=WATER_DENSITY, centroid_depth=CENTROID_DEPTH, area=area
    )
    y_cp = center_of_pressure_depth(
        centroid_depth=CENTROID_DEPTH, area=area, second_moment=second_moment
    )
    return {
        "base_pressure_kpa": base_pressure.to("kPa").magnitude,
        "force_kn": force.to("kN").magnitude,
        "center_of_pressure_m": y_cp.to("m").magnitude,
        "centroid_depth_m": CENTROID_DEPTH.to("m").magnitude,
        "gate_height_m": h,
    }


def main() -> None:
    g = gate_loads()
    print(f"pressure at base   : {g['base_pressure_kpa']:.1f} kPa")
    print(f"resultant force    : {g['force_kn']:.1f} kN on the gate")
    cp = g["center_of_pressure_m"]
    frac = cp / g["gate_height_m"]
    centroid = g["centroid_depth_m"]
    print(
        f"acts at depth      : {cp:.2f} m ({frac:.0%} of height), not the {centroid:.2f} m centroid"
    )


if __name__ == "__main__":
    main()
