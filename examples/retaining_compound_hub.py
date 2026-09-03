"""Worked example: the thin hub a press fit cannot hold and an adhesive can.

A 20 mm shaft must carry 60 N·m through a sprocket with a thin aluminum hub, engaged
over 15 mm. The classic answer is a press fit, but a press fit transmits torque only
through friction -- μ·p over the mating area -- and *both* factors are capped here: the
thin hub's bore yields past a 12 MPa fit pressure, and steel-on-aluminum friction is
about 0.15. That is an effective shear of just 1.8 MPa, and the fit tops out at 17 N·m
against the 60 N·m duty (SF 0.28). Pressing harder is not on the table; the hub, not
the friction, is the limit.

A retaining compound changes the mechanism instead of the numbers: cured in the same
annulus, the bond shears over the identical π·d·L area but at its own strength -- a
derated 10 MPa design value here, from a 25 MPa datasheet cured strength -- with *no
fit pressure required at all*. The same slip-fit interface now carries 94 N·m (1.57),
five times the press fit, and the hub bore sees no assembly stress. The comparison is
exact: friction offers μ·p = 1.8 MPa of shear, the adhesive offers τ = 10 MPa, and
the capacities scale in that ratio.

The lesson is that a cylindrical joint's torque is shear stress times π·d²·L/2,
whatever supplies the shear -- and when the hub is too delicate to press, an adhesive
supplies far more of it than friction ever could. The bond's number comes from its
datasheet, derated for gap, temperature, and surface; the geometry does the rest.

Run it directly (``python examples/retaining_compound_hub.py``);
:func:`screen_press_fit` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    cylindrical_bond_torque_capacity,
    interference_torque_capacity,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

REQUIRED_TORQUE = Quantity.parse("60 N*m")
INTERFACE_DIAMETER = Quantity.parse("20 mm")
ENGAGEMENT_LENGTH = Quantity.parse("15 mm")

# The press-fit route: the thin aluminum hub caps the fit pressure.
HUB_PRESSURE_LIMIT = Quantity.parse("12 MPa")
FRICTION_COEFFICIENT = 0.15  # steel on aluminum

# The bonded route: the retaining compound's derated design shear strength.
BOND_DESIGN_STRENGTH = Quantity.parse("10 MPa")  # from a 25 MPa datasheet, derated


def screen_press_fit() -> Scorecard:
    """Screen the press fit at the thin hub's pressure limit: friction falls short."""
    capacity = interference_torque_capacity(
        HUB_PRESSURE_LIMIT,
        interface_diameter=INTERFACE_DIAMETER,
        engagement_length=ENGAGEMENT_LENGTH,
        friction_coefficient=FRICTION_COEFFICIENT,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "press-fit friction torque vs duty",
                computed=capacity.to("N*m").magnitude / REQUIRED_TORQUE.to("N*m").magnitude,
                required=1.0,
            ),
        )
    )


def screen_bonded_hub() -> Scorecard:
    """Screen the retaining-compound bond on the same slip-fit interface."""
    capacity = cylindrical_bond_torque_capacity(
        interface_diameter=INTERFACE_DIAMETER,
        engagement_length=ENGAGEMENT_LENGTH,
        bond_shear_strength=BOND_DESIGN_STRENGTH,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "bonded torque vs duty",
                computed=capacity.to("N*m").magnitude / REQUIRED_TORQUE.to("N*m").magnitude,
                required=1.0,
            ),
        )
    )


def main() -> None:
    friction_shear = FRICTION_COEFFICIENT * HUB_PRESSURE_LIMIT.to("MPa").magnitude
    print(f"friction offers mu*p = {friction_shear:.1f} MPa of interface shear")
    print(f"the bond offers tau  = {BOND_DESIGN_STRENGTH.to('MPa').magnitude:.1f} MPa")
    print("\npress fit at the hub's 12 MPa limit:")
    print(screen_press_fit().report())
    print("\nretaining compound on a slip fit:")
    print(screen_bonded_hub().report())


if __name__ == "__main__":
    main()
