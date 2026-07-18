"""Worked example: three fatigue criteria, three verdicts, one cycle.

A shaft carries a fluctuating stress with an 80 MPa amplitude about a 200 MPa
tensile mean. The material has a 200 MPa endurance limit, a 400 MPa yield, and a
600 MPa ultimate. Whether the part passes a 1.5 fatigue safety factor depends
entirely on which mean-stress criterion you draw the line with -- and the three
common ones disagree.

Soderberg draws the failure line to the *yield* strength, so it is the most
conservative and also the only one that guarantees no first-cycle yielding; here it
gives 1.11 and fails. Goodman draws to the *ultimate*, a little less conservative at
1.36 -- still short of 1.5. Gerber replaces the straight line with a parabola that
hugs the test data, and for a tensile mean it sits above Goodman: 1.70, a pass. The
same stress state is unsafe, unsafe, and safe depending on the model.

The takeaway is not that one criterion is right. Gerber is the best fit to fatigue
data, so it is the least wasteful; Goodman is the common design-code default;
Soderberg is chosen when yielding must also be excluded. A screen should name the
criterion it used, because the number it reports is only as meaningful as the line
it was measured against. The material strengths are declared inline.

Run it directly (``python examples/fatigue_criteria_compared.py``);
:func:`screen_fatigue_criteria` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    gerber_safety_factor,
    goodman_safety_factor,
    soderberg_safety_factor,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

ALTERNATING_STRESS = Quantity.parse("80 MPa")
MEAN_STRESS = Quantity.parse("200 MPa")
ENDURANCE_LIMIT = Quantity.parse("200 MPa")
YIELD_STRENGTH = Quantity.parse("400 MPa")
ULTIMATE_STRENGTH = Quantity.parse("600 MPa")
REQUIRED_SAFETY_FACTOR = 1.5


def screen_fatigue_criteria() -> Scorecard:
    """Screen the same fluctuating stress with each mean-stress criterion against the
    required 1.5 fatigue safety factor."""
    soderberg = soderberg_safety_factor(
        alternating_stress=ALTERNATING_STRESS,
        mean_stress=MEAN_STRESS,
        endurance_limit=ENDURANCE_LIMIT,
        yield_strength=YIELD_STRENGTH,
    )
    goodman = goodman_safety_factor(
        alternating_stress=ALTERNATING_STRESS,
        mean_stress=MEAN_STRESS,
        endurance_limit=ENDURANCE_LIMIT,
        ultimate_strength=ULTIMATE_STRENGTH,
    )
    gerber = gerber_safety_factor(
        alternating_stress=ALTERNATING_STRESS,
        mean_stress=MEAN_STRESS,
        endurance_limit=ENDURANCE_LIMIT,
        ultimate_strength=ULTIMATE_STRENGTH,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "Soderberg (to yield)", computed=soderberg, required=REQUIRED_SAFETY_FACTOR
            ),
            ScorecardEntry.from_safety_factor(
                "Goodman (to ultimate)", computed=goodman, required=REQUIRED_SAFETY_FACTOR
            ),
            ScorecardEntry.from_safety_factor(
                "Gerber (parabola)", computed=gerber, required=REQUIRED_SAFETY_FACTOR
            ),
        )
    )


def main() -> None:
    print(screen_fatigue_criteria())


if __name__ == "__main__":
    main()
