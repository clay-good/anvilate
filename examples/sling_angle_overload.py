"""Worked example: the sling that is safe straight down and overloaded at an angle.

A 12 kN load is lifted on a two-leg sling, each leg rated for 8 kN. Picked straight down,
the sum is obvious and comfortable: each leg carries half the load, 6 kN, a safety factor
of 1.33 on its rating. Nobody would call that a marginal lift.

Rig the same two legs out to a 30-degree spread, though, and each leg is now pulling
12 kN -- the *whole* load, not half of it -- and blows past its 8 kN rating at a safety
factor of 0.67. Nothing about the load or the sling changed; only the angle did. A sling
leg's tension is its share of the load divided by sin θ, so as the sling flattens the
tension climbs: 1.15 at 60 degrees, already failing at 0.94 by 45 degrees, and 0.67 at 30.
The flat lift also drives a 10 kN horizontal force inward at each pick point, crushing the
load or the lifting beam.

The lesson is that sling capacity is an angle problem, not a weight problem. The rated
capacity printed on the sling assumes a vertical pull; every degree the legs open out
derates it. For this load the legs must stay above about 49 degrees from horizontal (where
each leg reaches its 8 kN rating); the usual shop rule of "keep sling angles above 45-60
degrees" is exactly this calculation. The fix is a steeper sling -- longer legs or a
spreader bar -- not a bigger crane.

Run it directly (``python examples/sling_angle_overload.py``);
:func:`screen_sling` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rigging
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

LOAD = Quantity.parse("12 kN")
NUMBER_OF_LEGS = 2
LEG_RATING = Quantity.parse("8 kN")  # working load limit per leg
SHALLOW_ANGLE = 30.0  # degrees from horizontal, as rigged
STEEP_ANGLE = 60.0  # degrees, the fix


def _screen(angle_from_horizontal: float) -> Scorecard:
    tension = rigging.sling_leg_tension(
        load=LOAD, number_of_legs=NUMBER_OF_LEGS, angle_from_horizontal=angle_from_horizontal
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "leg tension vs rating",
                computed=LEG_RATING.to("kN").magnitude / tension.to("kN").magnitude,
                required=1.0,
            ),
        )
    )


def screen_sling() -> Scorecard:
    """Screen the sling as rigged at a shallow 30-degree angle: each leg overloaded."""
    return _screen(SHALLOW_ANGLE)


def screen_steep_sling() -> Scorecard:
    """Screen the same sling rigged steeper at 60 degrees: back inside its rating."""
    return _screen(STEEP_ANGLE)


def main() -> None:
    print("as rigged (30 degrees from horizontal):")
    print(screen_sling())
    print("\nsteeper rig (60 degrees):")
    print(screen_steep_sling())


if __name__ == "__main__":
    main()
