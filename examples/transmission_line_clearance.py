"""Worked example: the sag approximation that signs off a line too low.

A power conductor hangs between two towers, and the one thing that must never fail is
ground clearance: the lowest point of the span has to stay a safe height above
whatever is below it. The conductor is attached 69 m up and the code demands 8 m of
clearance, so the midspan sag may not exceed 61 m.

How much it sags depends on which curve you use. The textbook shortcut treats the
cable as a parabola, which for this 400 m span under a 30 N/m conductor at 10 kN of
horizontal tension gives 60.0 m -- one metre inside the limit, a pass. But a cable
does not hang in a parabola; it hangs in a catenary, and the parabola is only its
shallow-sag approximation. Worked exactly, the catenary sags 61.8 m -- past the 61 m
limit, a fail. The 3% the parabola shaves off is exactly the difference between a
line that clears and one that does not, and here it hides a real violation.

For a shallow, taut span the two agree to a fraction of a percent and the parabola is
fine. But a long or heavily loaded span sags deeply, and there the parabola
systematically *under*-predicts both sag and tension -- the unsafe direction for a
clearance check. Use the exact catenary when the sag is a large fraction of the span.
The conductor, span, and tension are declared inline.

Run it directly (``python examples/transmission_line_clearance.py``);
:func:`screen_line_clearance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import catenary_sag, parabolic_cable_sag
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

WEIGHT_PER_LENGTH = Quantity.parse("30 N/m")
SPAN = Quantity.parse("400 m")
HORIZONTAL_TENSION = Quantity.parse("10 kN")
MAX_ALLOWED_SAG = Quantity.parse("61 m")  # 69 m attachment - 8 m ground clearance


def screen_line_clearance() -> Scorecard:
    """Screen the midspan sag against the clearance-limited maximum, computed both by
    the parabolic approximation and the exact catenary (safety factor = max sag /
    predicted sag)."""
    kw = {
        "weight_per_length": WEIGHT_PER_LENGTH,
        "span": SPAN,
        "horizontal_tension": HORIZONTAL_TENSION,
    }
    max_sag = MAX_ALLOWED_SAG.to("m").magnitude
    parabolic = parabolic_cable_sag(**kw).to("m").magnitude
    catenary = catenary_sag(**kw).to("m").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "parabolic-approximation sag", computed=max_sag / parabolic, required=1.0
            ),
            ScorecardEntry.from_safety_factor(
                "exact catenary sag", computed=max_sag / catenary, required=1.0
            ),
        )
    )


def main() -> None:
    kw = {
        "weight_per_length": WEIGHT_PER_LENGTH,
        "span": SPAN,
        "horizontal_tension": HORIZONTAL_TENSION,
    }
    print(f"parabolic sag: {parabolic_cable_sag(**kw).to('m').magnitude:.1f} m")
    print(f"catenary sag:  {catenary_sag(**kw).to('m').magnitude:.1f} m")
    print(f"max allowed:   {MAX_ALLOWED_SAG.to('m').magnitude:.1f} m")
    print(screen_line_clearance())


if __name__ == "__main__":
    main()
