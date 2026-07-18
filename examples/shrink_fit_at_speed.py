"""Worked example: the shrink fit that let go at speed.

A steel coupling hub is shrink-fitted onto a shaft at a 100 mm fit radius with
0.05 mm of radial interference — plenty to grip cold, where holding the design
torque needs only 0.03 mm of squeeze. The fit is assembled and checked at rest,
and it passes with a 1.67 margin.

But the hub spins, and a spinning rim grows. Centrifugal loading stretches the
hub radially by delta = rho*omega^2*r^3/E, and that growth eats straight into the
interference: the bore pulls away from the shaft and the squeeze bleeds off. At
6000 rpm the hub has grown 0.016 mm and the remaining interference (0.035 mm)
still clears the 0.03 mm minimum, just. Double the speed to 12000 rpm and the
growth quadruples to 0.062 mm — more than the whole 0.05 mm interference — so the
fit is not merely weakened but *gone*: the hub is running loose on its shaft.

A shrink fit must be checked at operating speed, not just at assembly. The
interference that grips cold rides on omega^2 toward zero, and a fit sized only
at rest can spin free at speed. Density and modulus are material data, declared
inline like any allowable.

Run it directly (``python examples/shrink_fit_at_speed.py``);
:func:`screen_shrink_fit` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rotating_rim_radial_growth
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

DENSITY = Quantity.parse("7850 kg/m**3")
ELASTIC_MODULUS = Quantity.parse("200 GPa")
FIT_RADIUS = Quantity.parse("100 mm")
ASSEMBLY_INTERFERENCE = Quantity.parse("0.05 mm")
MIN_INTERFERENCE = Quantity.parse("0.03 mm")  # to hold the design torque

SPEEDS = {
    "at rest": Quantity.parse("0.001 rpm"),
    "at 6000 rpm": Quantity.parse("6000 rpm"),
    "at 12000 rpm": Quantity.parse("12000 rpm"),
}


def remaining_interference(speed: Quantity) -> float:
    """The interference (mm) left after the hub grows radially at ``speed``."""
    growth = rotating_rim_radial_growth(
        density=DENSITY,
        mean_radius=FIT_RADIUS,
        rotational_speed=speed,
        elastic_modulus=ELASTIC_MODULUS,
    )
    return ASSEMBLY_INTERFERENCE.to("mm").magnitude - growth.to("mm").magnitude


def screen_shrink_fit() -> Scorecard:
    """Screen the remaining interference against the minimum the torque needs, at
    each speed (safety factor = remaining / minimum)."""
    minimum = MIN_INTERFERENCE.to("mm").magnitude
    entries = [
        ScorecardEntry.from_safety_factor(
            name, computed=remaining_interference(speed) / minimum, required=1.0
        )
        for name, speed in SPEEDS.items()
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, speed in SPEEDS.items():
        print(f"{name}: {remaining_interference(speed):.4f} mm interference left")
    print(screen_shrink_fit())


if __name__ == "__main__":
    main()
