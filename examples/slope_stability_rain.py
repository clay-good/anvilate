"""Worked example: the cut slope that friction can't hold, cohesion saves, and rain nearly loses.

A 35° cut slope is steeper than the soil's 30° friction angle, so on friction alone it would
already be sliding — the dry cohesionless factor of safety is below 1. What actually holds it up
is the soil's cohesion, and with it the slope is comfortably stable. But cohesion is the fragile
part of the strength: when heavy rain saturates the slope, seepage builds pore-water pressure on
the failure plane that cancels much of the frictional strength, and the factor of safety slides
back toward 1. This example runs the same infinite-slope check in all three states — friction
only, cohesive and dry, cohesive and saturated — to show why so many slopes stand for years and
then fail in a storm. The soil never changed; the water did.

Run it directly (``python examples/slope_stability_rain.py``);
:func:`slope_factors` is also exercised in the test suite.
"""

from __future__ import annotations

from math import cos, radians

from anvilate.analysis import infinite_slope_factor_of_safety
from anvilate.units import Quantity

FRICTION_ANGLE = 30.0  # phi, degrees
SLOPE_ANGLE = 35.0  # beta, degrees (steeper than phi)
COHESION = Quantity.parse("15 kPa")
UNIT_WEIGHT = Quantity.parse("19 kN/m**3")
DEPTH = Quantity.parse("2.5 m")  # to the failure plane
WATER_UNIT_WEIGHT = Quantity.parse("9.81 kN/m**3")


def slope_factors() -> dict[str, float]:
    """Return the friction-only, cohesive-dry, and cohesive-saturated factors of safety."""
    friction_only = infinite_slope_factor_of_safety(
        cohesion=Quantity.parse("0 kPa"),
        friction_angle=FRICTION_ANGLE,
        unit_weight=UNIT_WEIGHT,
        depth=DEPTH,
        slope_angle=SLOPE_ANGLE,
    )
    dry = infinite_slope_factor_of_safety(
        cohesion=COHESION,
        friction_angle=FRICTION_ANGLE,
        unit_weight=UNIT_WEIGHT,
        depth=DEPTH,
        slope_angle=SLOPE_ANGLE,
    )
    # Seepage parallel to the slope: u = gamma_w * z * cos^2(beta) on the failure plane.
    z = DEPTH.to("m").magnitude
    u = WATER_UNIT_WEIGHT.to("kN/m**3").magnitude * z * cos(radians(SLOPE_ANGLE)) ** 2
    saturated = infinite_slope_factor_of_safety(
        cohesion=COHESION,
        friction_angle=FRICTION_ANGLE,
        unit_weight=UNIT_WEIGHT,
        depth=DEPTH,
        slope_angle=SLOPE_ANGLE,
        pore_pressure=Quantity(magnitude=u, unit="kPa"),
    )
    return {
        "friction_only": friction_only,
        "dry": dry,
        "saturated": saturated,
    }


def main() -> None:
    f = slope_factors()

    def verdict(fs: float) -> str:
        return "FAIL" if fs < 1.0 else "PASS"

    print(f"friction only    : FS = {f['friction_only']:.2f}  ({verdict(f['friction_only'])})")
    print(f"cohesive, dry    : FS = {f['dry']:.2f}  ({verdict(f['dry'])})")
    print(f"cohesive, soaked : FS = {f['saturated']:.2f}  ({verdict(f['saturated'])})")
    print("  -> friction alone can't hold it; cohesion does, until rain washes the margin away")


if __name__ == "__main__":
    main()
