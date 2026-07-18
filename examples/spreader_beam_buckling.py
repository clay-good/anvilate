"""Capstone: the spreader beam that is secretly a column.

A 30 kN load is lifted on a spreader: a 4 m horizontal bar with a sling from each end down
to the load and a sling from each end up to the crane hook, the top slings raked in at 45°.
The rigger checks the obvious thing -- the slings -- and they are fine: each of the two top
legs carries 21.2 kN against a 24 kN rating, a safety factor of 1.13.

The bar is the trap. A spreader looks like a beam, but its job is to hold the bottom slings
apart, and it does that by taking the *inward horizontal pull* of the raked top slings as
pure axial **compression** -- 15 kN of it here. A 4 m tube is a slender column (slenderness
ratio 251, deep in the Euler range), and at 48 mm diameter its Euler buckling load is only
13.3 kN. The 15 kN compression exceeds it: the spreader buckles sideways at a safety factor
of 0.89, with the slings none the wiser. The one member that reads as a beam is the one that
fails as a column.

The fix is not a beam sized for bending -- there is barely any bending. It is a *stubbier
column*: swapping the 48 mm tube for a 60 mm one lifts the Euler load to 27 kN and the
buckling safety factor to 1.80, at the same wall thickness and length. A spreader is sized by
its slenderness, and the horizontal sling force -- invisible on a free-body sketch that only
shows the vertical load -- is what it must not buckle under.

Run it directly (``python examples/spreader_beam_buckling.py``);
:func:`screen_spreader` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    euler_buckling_load,
    hollow_circular_second_moment,
    sling_horizontal_force,
    sling_leg_tension,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

LOAD = Quantity.parse("30 kN")
TOP_SLING_LEGS = 2
SLING_ANGLE = 45.0  # degrees from horizontal
SLING_RATING = Quantity.parse("24 kN")
SPREADER_LENGTH = Quantity.parse("4 m")
ELASTIC_MODULUS = Quantity.parse("200 GPa")
WALL_THICKNESS = Quantity.parse("3 mm")

AS_DRAWN_OUTER_DIAMETER = Quantity.parse("48 mm")  # slender tube
REDESIGNED_OUTER_DIAMETER = Quantity.parse("60 mm")  # stubbier tube


def _screen(outer_diameter: Quantity) -> Scorecard:
    leg_tension = sling_leg_tension(
        load=LOAD, number_of_legs=TOP_SLING_LEGS, angle_from_horizontal=SLING_ANGLE
    )
    # The raked slings squeeze the spreader in pure axial compression.
    compression = sling_horizontal_force(
        load=LOAD, number_of_legs=TOP_SLING_LEGS, angle_from_horizontal=SLING_ANGLE
    )
    inner = Quantity(
        magnitude=outer_diameter.to("mm").magnitude - 2 * WALL_THICKNESS.to("mm").magnitude,
        unit="mm",
    )
    second_moment = hollow_circular_second_moment(
        outer_diameter=outer_diameter, inner_diameter=inner
    )
    buckling_load = euler_buckling_load(
        elastic_modulus=ELASTIC_MODULUS, second_moment=second_moment, length=SPREADER_LENGTH
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "top sling leg tension",
                computed=SLING_RATING.to("kN").magnitude / leg_tension.to("kN").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "spreader column buckling",
                computed=buckling_load.to("kN").magnitude / compression.to("kN").magnitude,
                required=1.0,
            ),
        )
    )


def screen_spreader() -> Scorecard:
    """Screen the slender 48 mm spreader: slings pass, but the bar buckles as a column."""
    return _screen(AS_DRAWN_OUTER_DIAMETER)


def screen_stubbier_spreader() -> Scorecard:
    """Screen the 60 mm spreader: the stubbier column clears the same compression."""
    return _screen(REDESIGNED_OUTER_DIAMETER)


def main() -> None:
    print("as drawn (48 mm tube):")
    print(screen_spreader())
    print("\nstubbier (60 mm tube):")
    print(screen_stubbier_spreader())


if __name__ == "__main__":
    main()
