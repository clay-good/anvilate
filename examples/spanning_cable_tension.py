"""Worked example: the cable span with no good tension.

An 80 m messenger cable weighing 15 N/m must clear the ground by staying within
1.5 m of midspan sag, and it must not pull harder than the 7.9 kN its anchors and
strength allow. Tension is the only free knob — and the two demands pull it in
opposite directions.

Sag falls as tension rises (d = w·L²/8H), so beating the clearance wants a high
tension: it takes 8 kN of horizontal pull just to hold the sag to 1.5 m. But the
peak tension at the supports is 8.0 kN there — over the 7.9 kN allowable — and
pulling any tighter to gain clearance margin only overloads the cable more. Slack
it off to protect the cable (6 kN) and the sag balloons to 2.0 m and fails the
clearance. Every tension either sags too far or pulls too hard; the window where
both pass is empty.

That is the signal to stop turning the tension knob and change the cable: a lighter
messenger, a stronger one, or an intermediate support to halve the span. The
sag-versus-tension trade-off is fixed by the span and the cable weight, and no
tension setting escapes it. The 7.9 kN allowable is manufacturer's data, declared
inline like any allowable.

Run it directly (``python examples/spanning_cable_tension.py``);
:func:`screen_cable_span` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import parabolic_cable_max_tension, parabolic_cable_sag
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

CABLE_WEIGHT = Quantity.parse("15 N/m")
SPAN = Quantity.parse("80 m")
MAX_SAG = Quantity.parse("1.5 m")
ALLOWABLE_TENSION = Quantity.parse("7900 N")

TENSIONS = {
    "slack (6 kN)": Quantity.parse("6000 N"),
    "balanced (8 kN)": Quantity.parse("8000 N"),
    "taut (12 kN)": Quantity.parse("12000 N"),
}


def screen_cable_span() -> Scorecard:
    """Screen each tension on both demands: sag clearance and cable strength.
    A tension passes overall only if both entries pass -- and none does."""
    max_sag = MAX_SAG.to("m").magnitude
    allowable = ALLOWABLE_TENSION.to("N").magnitude
    entries = []
    for name, tension in TENSIONS.items():
        sag = parabolic_cable_sag(
            weight_per_length=CABLE_WEIGHT, span=SPAN, horizontal_tension=tension
        )
        tmax = parabolic_cable_max_tension(
            weight_per_length=CABLE_WEIGHT, span=SPAN, horizontal_tension=tension
        )
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"{name}: sag clearance",
                computed=max_sag / sag.to("m").magnitude,
                required=1.0,
            )
        )
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"{name}: cable strength",
                computed=allowable / tmax.to("N").magnitude,
                required=1.0,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, tension in TENSIONS.items():
        sag = parabolic_cable_sag(
            weight_per_length=CABLE_WEIGHT, span=SPAN, horizontal_tension=tension
        )
        tmax = parabolic_cable_max_tension(
            weight_per_length=CABLE_WEIGHT, span=SPAN, horizontal_tension=tension
        )
        print(
            f"{name}: sag {sag.to('m').magnitude:.2f} m, "
            f"peak tension {tmax.to('N').magnitude:.0f} N"
        )
    print(screen_cable_span())


if __name__ == "__main__":
    main()
