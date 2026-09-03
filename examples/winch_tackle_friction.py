"""Worked example: the six-part tackle whose winch is overloaded by sheave friction.

A 30 kN load hangs from a six-part block and tackle, hoisted by a winch rated for a 6 kN
line pull. The frictionless arithmetic everyone does first says the lead line sees
W/n = 5 kN -- a tidy 1.20 margin, order the winch. But a tackle only delivers its part
count if the sheaves are free: hoisting, every sheave pass raises the rope tension by
1/η, so the six supporting parts carry a geometric series of tensions and the lead line
-- one more pass beyond the last part -- carries the biggest number in the whole reeving.

On the yard's plain-bushing blocks (η = 0.94 per sheave) the actual mechanical advantage
is not 6 but 4.86, and the winch must pull 6.17 kN -- 23% over the frictionless estimate
and past its 6 kN rating (0.97, stalls or trips). Nothing about the load changed; the
part count simply overstated the tackle. Swapping to rolling-bearing sheaves (η = 0.98)
lifts the advantage to 5.59 and the lead line drops to 5.36 kN (1.12, clears).

The lesson is that a block and tackle's advantage is a *friction* number, not a
geometry number: the frictionless W/n is the floor of what the winch will see, never
the answer. The lead line is also the highest-tension rope in the system, so it -- not
the load share -- is what both the winch rating and the rope selection must screen
against. When a tackle comes up short, the cheap fix is better sheaves, not a bigger
winch.

Run it directly (``python examples/winch_tackle_friction.py``);
:func:`screen_plain_bushing_tackle` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import tackle_lead_line_tension, tackle_mechanical_advantage
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

LOAD = Quantity.parse("30 kN")
SUPPORTING_PARTS = 6
LEAD_SHEAVES = 1  # one more pass over the head sheave down to the winch
WINCH_LINE_PULL_RATING = Quantity.parse("6 kN")

PLAIN_BUSHING_EFFICIENCY = 0.94  # per sheave, worn plain-bushing blocks
ROLLING_BEARING_EFFICIENCY = 0.98  # per sheave, rolling-bearing sheaves


def _screen(sheave_efficiency: float) -> Scorecard:
    frictionless_lead = LOAD.to("kN").magnitude / SUPPORTING_PARTS
    actual_lead = tackle_lead_line_tension(
        load=LOAD,
        supporting_parts=SUPPORTING_PARTS,
        sheave_efficiency=sheave_efficiency,
        lead_sheaves=LEAD_SHEAVES,
    )
    rating = WINCH_LINE_PULL_RATING.to("kN").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "frictionless lead line vs winch rating",
                computed=rating / frictionless_lead,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "actual lead line vs winch rating",
                computed=rating / actual_lead.to("kN").magnitude,
                required=1.0,
            ),
        )
    )


def screen_plain_bushing_tackle() -> Scorecard:
    """Screen the tackle on plain-bushing blocks: friction overloads the winch."""
    return _screen(PLAIN_BUSHING_EFFICIENCY)


def screen_rolling_bearing_tackle() -> Scorecard:
    """Screen the same tackle on rolling-bearing sheaves: the winch clears."""
    return _screen(ROLLING_BEARING_EFFICIENCY)


def main() -> None:
    for name, eta in (
        ("plain bushings", PLAIN_BUSHING_EFFICIENCY),
        ("rolling bearings", ROLLING_BEARING_EFFICIENCY),
    ):
        advantage = tackle_mechanical_advantage(
            supporting_parts=SUPPORTING_PARTS,
            sheave_efficiency=eta,
            lead_sheaves=LEAD_SHEAVES,
        )
        print(f"{name} (eta {eta}): actual MA {advantage:.2f} of {SUPPORTING_PARTS} parts")
    print("\nplain-bushing blocks:")
    print(screen_plain_bushing_tackle().report())
    print("\nrolling-bearing sheaves:")
    print(screen_rolling_bearing_tackle().report())


if __name__ == "__main__":
    main()
