"""Worked example: the sag approximation that used to sign off a line too low.

A power conductor hangs between two towers, and the one thing that must never fail is
ground clearance: the lowest point of the span has to stay a safe height above whatever is
below it. The conductor is attached 69 m up and the code demands 8 m of clearance, so the
midspan sag may not exceed 61 m.

How much it sags depends on which curve you use. The textbook shortcut treats the cable as
a parabola, which for this 400 m span under a 30 N/m conductor at 10 kN of horizontal
tension gives 60.0 m — one metre inside the limit, a pass. But a cable does not hang in a
parabola; it hangs in a catenary, and the parabola is only its shallow-sag approximation.
Worked exactly, the catenary sags 61.8 m — past the 61 m limit, a fail. The 3% the parabola
shaves off is exactly the difference between a line that clears and one that does not.

**This span is no longer inside the parabola's scope, and the library says so.** At
d/L = 0.15 the shallow-sag forms now refuse rather than answer: an audit found the limit
stated in three docstrings and enforced nowhere, and both of the parabola's outputs — the
sag that checks clearance and the peak tension that sizes the anchors — err in the
unconservative direction outside it. So the first entry here is NOT_EVALUATED carrying the
library's own reason and naming the exact form, and the exact catenary supplies the verdict:
FAIL.

For a shallow, taut span (d/L ≤ 0.10) the two agree to about a percent and the parabola is
fine. Deeper than that it systematically *under*-predicts both sag and tension.

Run it directly (``python examples/transmission_line_clearance.py``);
:func:`screen_line_clearance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import catenary_sag, parabolic_cable_sag
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
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
    try:
        parabolic = parabolic_cable_sag(**kw).to("m").magnitude
    except ValueError as refusal:
        parabolic_entry = ScorecardEntry(
            name="parabolic-approximation sag",
            status=CheckStatus.NOT_EVALUATED,
            detail=f"not evaluated — {refusal}",
        )
    else:  # pragma: no cover - this span sits outside the shallow-sag scope
        parabolic_entry = ScorecardEntry.from_safety_factor(
            "parabolic-approximation sag", computed=max_sag / parabolic, required=1.0
        )
    catenary = catenary_sag(**kw).to("m").magnitude
    return Scorecard(
        entries=(
            parabolic_entry,
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
    try:
        print(f"parabolic sag: {parabolic_cable_sag(**kw).to('m').magnitude:.1f} m")
    except ValueError as refusal:
        print(f"parabolic sag: refused — {refusal}")
    print(f"catenary sag:  {catenary_sag(**kw).to('m').magnitude:.1f} m")
    print(f"max allowed:   {MAX_ALLOWED_SAG.to('m').magnitude:.1f} m")
    print(screen_line_clearance().report())


if __name__ == "__main__":
    main()
