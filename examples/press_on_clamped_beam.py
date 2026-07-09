"""Worked example: a press off mid-span of a crossbeam clamped into both walls.

Declares a 22 kN press a third of the way along a 3 m A36 crossbeam (50 x 80 mm
rectangle) built into concrete walls at both ends, and screens it twice: once
pretending the load sits at mid-span, and once with the actual ``load_position``
declared. The instructive part is the *opposite* of the simply-supported case:
on a fixed-fixed beam mid-span is not the worst position. The hogging moment at
the nearer wall (M = P·a·b²/L²) peaks at the third point — 4·P·L/27, 18.5% above
the mid-span P·L/8 — so the mid-span shortcut passes at SF 1.62 while the real
third-point screen fails at 1.36. Assuming mid-span on a clamped beam is
unconservative; declaring where the load really sits catches it.

Run it directly (``python examples/press_on_clamped_beam.py``);
:func:`screen_clamped_beam` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import BeamMember, LoadType, Support, screen_structure
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

PRESS_WEIGHT = Quantity.parse("22 kN")
SPAN = Quantity.parse("3 m")
PRESS_POSITION = Quantity.parse("1 m")  # third point — the worst spot on a clamped beam


def screen_clamped_beam() -> Scorecard:
    """Screen the beam under both load-position assumptions, returning one card."""
    section = CrossSection.rectangular(
        width=Quantity.parse("50 mm"), height=Quantity.parse("80 mm")
    )
    common = {
        "section": section,
        "length": SPAN,
        "support": Support.FIXED_FIXED,
        "load": PRESS_WEIGHT,
        "load_type": LoadType.POINT,
        "material": "ASTM-A36",
    }
    assumed_mid_span = BeamMember(name="assumed mid-span", **common)
    at_third_point = BeamMember(name="at third point", load_position=PRESS_POSITION, **common)
    return screen_structure([assumed_mid_span, at_third_point], required_safety_factor=1.5)


def main() -> None:
    card = screen_clamped_beam()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
