"""Worked example: sweeping a hoist trolley along a propped runway beam.

Declares a 10 kN hoist trolley on a 3 m A36 runway beam (50 x 74 mm rectangle)
moment-connected into a column at one end and hung from a tie rod (a prop) at
the other, then screens three parking spots against SF 2.0. On a propped
cantilever the governing wall moment peaks at L/√3 ≈ 58% of the span from the
prop — not at mid-span — so the sweep reads: quarter point passes at SF 2.40,
mid-span passes at 2.03, and the worst spot fails at 1.98. A screen that only
checked mid-span would have called this runway good; the 2.6% it misses is
exactly the margin this beam doesn't have.

Run it directly (``python examples/monorail_trolley_sweep.py``);
:func:`screen_runway_beam` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import BeamMember, LoadType, Support, screen_structure
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

TROLLEY_LOAD = Quantity.parse("10 kN")
SPAN = Quantity.parse("3 m")
WORST_SPOT = Quantity(magnitude=3000 / 3**0.5, unit="mm")  # L/sqrt(3) from the prop


def screen_runway_beam() -> Scorecard:
    """Screen the trolley at three parking spots, returning one card."""
    section = CrossSection.rectangular(
        width=Quantity.parse("50 mm"), height=Quantity.parse("74 mm")
    )
    common = {
        "section": section,
        "length": SPAN,
        "support": Support.FIXED_PINNED,
        "load": TROLLEY_LOAD,
        "load_type": LoadType.POINT,
        "material": "ASTM-A36",
    }
    members = [
        BeamMember(
            name="trolley at quarter point", load_position=Quantity.parse("750 mm"), **common
        ),
        BeamMember(name="trolley at mid-span", load_position=Quantity.parse("1500 mm"), **common),
        BeamMember(name="trolley at worst spot", load_position=WORST_SPOT, **common),
    ]
    return screen_structure(members, required_safety_factor=2.0)


def main() -> None:
    card = screen_runway_beam()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
