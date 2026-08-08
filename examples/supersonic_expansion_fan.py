"""Worked example: a supersonic expansion fan around a convex corner.

When supersonic air flows past a convex corner it turns through a Prandtl-Meyer expansion fan,
accelerating isentropically. The Prandtl-Meyer angle ν(M) tracks how far the flow has turned from
sonic conditions, the Mach angle sets the inclination of the fan's characteristic lines, and the
maximum turning angle bounds how sharp a corner an attached expansion can round.

Air (γ = 1.4) arrives at Mach 2.0. Its Prandtl-Meyer angle is about 26.4°, and the leading Mach line
of the fan sits at the Mach angle asin(1/2) = 30° to the flow. In the limit of turning all the way
to vacuum (M → ∞) the flow could rotate through at most about 130.5° — the maximum turning angle for
air. This example reports the Prandtl-Meyer angle, the Mach angle, and that maximum turning angle.

Run it directly (``python examples/supersonic_expansion_fan.py``);
:func:`expansion_fan_angles` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    mach_angle,
    maximum_turning_angle,
    prandtl_meyer_angle,
)

MACH = 2.0
HEAT_CAPACITY_RATIO = 1.4  # air


def expansion_fan_angles() -> dict[str, float]:
    """Return the Prandtl-Meyer angle, Mach angle, and maximum turning angle in degrees."""
    nu = prandtl_meyer_angle(mach_number=MACH, heat_capacity_ratio=HEAT_CAPACITY_RATIO)
    mu = mach_angle(mach_number=MACH)
    nu_max = maximum_turning_angle(heat_capacity_ratio=HEAT_CAPACITY_RATIO)
    return {
        "prandtl_meyer_angle_deg": nu.to("degree").magnitude,
        "mach_angle_deg": mu.to("degree").magnitude,
        "maximum_turning_angle_deg": nu_max.to("degree").magnitude,
    }


def main() -> None:
    d = expansion_fan_angles()
    print(f"Prandtl-Meyer angle nu(M): {d['prandtl_meyer_angle_deg']:.1f} deg")
    print(f"Mach angle mu = asin(1/M): {d['mach_angle_deg']:.1f} deg")
    print(f"maximum turning angle nu(inf): {d['maximum_turning_angle_deg']:.1f} deg")


if __name__ == "__main__":
    main()
