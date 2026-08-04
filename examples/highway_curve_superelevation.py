"""Worked example: banking a highway curve for its design speed, and the safe-speed range it buys.

A highway curve is banked so that gravity and tire friction together turn the vehicle. This example
designs a curve for a 90 km/h (25 m/s) road. With the AASHTO maximums — a 6% superelevation and a
0.12 side-friction factor — the sharpest allowable curve has a radius of about 354 m. The example
then shows the two limiting cases the design lives between: the ideal superelevation rate that would
turn the vehicle on gravity alone (much steeper than any road is built, which is why real curves
lean on friction too), and the maximum speed the built curve can actually be taken at before the
tires slide — which comes back to the 25 m/s design speed, confirming the radius and the banking are
matched. The friction factor and the superelevation cap are the AASHTO policy values; the geometry
follows.

Run it directly (``python examples/highway_curve_superelevation.py``);
:func:`curve_design` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    banked_curve_max_speed,
    ideal_superelevation_rate,
    minimum_curve_radius,
)
from anvilate.units import Quantity

DESIGN_SPEED = Quantity.parse("25 m/s")  # 90 km/h
SUPERELEVATION_RATE = 0.06  # 6% AASHTO maximum
SIDE_FRICTION_FACTOR = 0.12


def curve_design() -> dict[str, float]:
    """Return the minimum radius, the friction-free ideal rate, and the built curve's max speed."""
    radius = minimum_curve_radius(
        design_speed=DESIGN_SPEED,
        superelevation_rate=SUPERELEVATION_RATE,
        side_friction_factor=SIDE_FRICTION_FACTOR,
    )
    ideal_rate = ideal_superelevation_rate(speed=DESIGN_SPEED, radius=radius)
    max_speed = banked_curve_max_speed(
        radius=radius,
        superelevation_rate=SUPERELEVATION_RATE,
        side_friction_factor=SIDE_FRICTION_FACTOR,
    )
    return {
        "radius_m": radius.to("m").magnitude,
        "ideal_superelevation_rate": ideal_rate,
        "max_speed_m_s": max_speed.to("m/s").magnitude,
    }


def main() -> None:
    c = curve_design()
    print(f"minimum radius (90 km/h)   : {c['radius_m']:.0f} m")
    print(
        f"friction-free ideal e      : {c['ideal_superelevation_rate'] * 100:.0f}% "
        f"(vs the 6% built — real curves lean on friction)"
    )
    print(f"max speed of the built curve: {c['max_speed_m_s']:.1f} m/s (back to the design speed)")
    print("  -> the radius and the 6% bank are matched to the design speed and friction allowance")


if __name__ == "__main__":
    main()
