"""Worked example: the pallet on the dock edge lifts the middle of the deck.

A 3 m simply-supported deck beam (80 x 120 x 4 mm A36 box) runs 450 mm past
its end support as a dock edge, and a 10 kN pallet lands on the tip. The
declared overhang member screens bending comfortably (|M| = F·c at the inner
support, SF 2.86) — but the governing deflection is NOT the edge dipping:
at c = 0.15·L the back span bows UPWARD by more than the tip drops
(4.20 mm of mid-span uplift vs 3.77 mm of tip drop), because the tip load
levers the whole back span about the inner support. Against a 3 mm deck
flatness limit the screen FAILs on movement in the direction nobody
instinctively checks — cracked screeds and tripping thresholds mid-deck, not
at the edge.

Run it directly (``python examples/dock_edge_overhang.py``);
:func:`screen_dock_edge` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import BeamMember, LoadType, Support, screen_beam_member
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

BACK_SPAN = Quantity.parse("3 m")
OVERHANG = Quantity.parse("450 mm")  # 0.15 of the back span — a short edge
PALLET = Quantity.parse("10 kN")
FLATNESS_LIMIT = Quantity.parse("3 mm")
REQUIRED_SF = 1.5


def screen_dock_edge() -> Scorecard:
    """Screen the dock-edge beam under the tip pallet load."""
    member = BeamMember(
        name="dock edge",
        section=CrossSection.hollow_rectangular(
            width=Quantity.parse("80 mm"),
            height=Quantity.parse("120 mm"),
            wall_thickness=Quantity.parse("4 mm"),
        ),
        length=BACK_SPAN,
        support=Support.OVERHANG,
        load=PALLET,
        load_type=LoadType.POINT,
        material="ASTM-A36",
        overhang_length=OVERHANG,
        deflection_limit=FLATNESS_LIMIT,
    )
    return screen_beam_member(member, required_safety_factor=REQUIRED_SF)


def main() -> None:
    card = screen_dock_edge()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
