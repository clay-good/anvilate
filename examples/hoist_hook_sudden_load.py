"""Worked example: the hoist beam whose static rating means nothing to a dropped load.

A workshop hoist beam carries its rated load at a gentle 100 MPa of bending stress --
a 2.5 factor against the steel's 250 MPa yield, and the static calc sheet looks
generous. But loads do not always arrive gently. The energy method (Roark / Shigley)
says a load applied to an elastic member is amplified by the impact factor

    K = 1 + sqrt(1 + 2*h/delta_st)

where h is the drop height and delta_st the static deflection -- here 4 mm under the
rated load.

The two screens below bracket the danger. A load *suddenly applied* -- released at the
instant of contact, h = 0 -- still doubles every stress (K = 2): the beam sees
200 MPa, and against the 1.5 factor a lifting duty demands, the margin is gone
(1.25 < 1.5). And a real drop of just 20 mm -- a chain snatch, a load slipping off a
block -- amplifies the stress 4.3-fold to 432 MPa, past yield itself: the beam takes a
permanent set the static sheet said was impossible by a factor of 2.5.

The lesson is that impact capacity is bought with *compliance*, not just strength: K
falls as the static deflection grows, so a springier beam, a longer sling, or a rubber
snubber does more for a snatch load than a thicker flange. Rate lifting gear for K = 2
minimum, and never let a static pass speak for a dynamic duty.

Run it directly (``python examples/hoist_hook_sudden_load.py``);
:func:`screen_sudden_application` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import impact_stress
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

STATIC_STRESS = Quantity.parse("100 MPa")  # bending stress with the load placed gently
STATIC_DEFLECTION = Quantity.parse("4 mm")  # beam deflection under the rated load
YIELD_STRENGTH = Quantity.parse("250 MPa")
REQUIRED_FACTOR = 1.5  # lifting-duty minimum against yield

SUDDEN_DROP = Quantity.parse("0 mm")  # released at contact: the classic K = 2
SNATCH_DROP = Quantity.parse("20 mm")  # a chain snatch / load slipping off a block


def _screen(name: str, drop_height: Quantity) -> Scorecard:
    peak = impact_stress(
        static_stress=STATIC_STRESS,
        drop_height=drop_height,
        static_deflection=STATIC_DEFLECTION,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                name,
                computed=YIELD_STRENGTH.to("MPa").magnitude / peak.to("MPa").magnitude,
                required=REQUIRED_FACTOR,
            ),
        )
    )


def screen_gentle_placement() -> Scorecard:
    """Screen the load placed gently: the static case the calc sheet rated."""
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "bending yield, load placed gently",
                computed=YIELD_STRENGTH.to("MPa").magnitude / STATIC_STRESS.to("MPa").magnitude,
                required=REQUIRED_FACTOR,
            ),
        )
    )


def screen_sudden_application() -> Scorecard:
    """Screen the suddenly-applied load: K = 2 erases the static margin."""
    return _screen("bending yield, suddenly applied (K = 2)", SUDDEN_DROP)


def screen_snatch_drop() -> Scorecard:
    """Screen the 20 mm snatch: 4.3x amplification puts the beam past yield."""
    return _screen("bending yield, 20 mm snatch drop", SNATCH_DROP)


def main() -> None:
    print("placed gently:")
    print(screen_gentle_placement().report())
    print("\nsuddenly applied (h = 0):")
    print(screen_sudden_application().report())
    print("\n20 mm snatch drop:")
    print(screen_snatch_drop().report())


if __name__ == "__main__":
    main()
