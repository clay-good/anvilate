"""Worked example: where a skid parks on a cantilevered platform decides the screen.

Declares the same 2 m A36 cantilevered platform beam (80 x 120 x 5 mm box)
carrying a 10 N/mm machine skid over a 1 m footprint, first parked against the
wall (an end patch), then rolled out to mid-platform (a centered patch —
``patch_centered``), and screens both placements as one structure. The load is
identical; only the parking spot moves. At the wall the beam screens
comfortably (SF 3.13, tip deflection 3.883 mm). Rolled out to the middle the
patch total acts at twice the moment arm, so the wall moment doubles
(w·a²/2 → w·a·L/2), the stress SF halves to 1.56 — a whisker over the 1.5
bar — and the tip deflection triples to 11.649 mm, past the L/180 limit
(11.111 mm). The same skid that screened green at the wall fails mid-platform;
declaring the placement is how the screen can tell.

Run it directly (``python examples/skid_position_on_platform.py``);
:func:`screen_skid_positions` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import (
    BeamMember,
    LoadType,
    Support,
    screen_structure,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

SKID_LOAD = Quantity.parse("10 N/mm")
FOOTPRINT = Quantity.parse("1 m")
SPAN = Quantity.parse("2 m")
DEFLECTION_LIMIT = Quantity(magnitude=2000 / 180, unit="mm")  # L/180 for a cantilever tip
REQUIRED_SF = 1.5

_PLACEMENTS = (
    ("parked at the wall", False),
    ("parked mid-platform", True),
)


def screen_skid_positions() -> Scorecard:
    """Screen the skid at both parking spots on the platform, as one structure."""
    section = CrossSection.hollow_rectangular(
        width=Quantity.parse("80 mm"),
        height=Quantity.parse("120 mm"),
        wall_thickness=Quantity.parse("5 mm"),
    )
    members = [
        BeamMember(
            name=name,
            section=section,
            length=SPAN,
            support=Support.CANTILEVER,
            load=SKID_LOAD,
            load_type=LoadType.DISTRIBUTED,
            material="ASTM-A36",
            deflection_limit=DEFLECTION_LIMIT,
            loaded_length=FOOTPRINT,
            patch_centered=centered,
        )
        for name, centered in _PLACEMENTS
    ]
    return screen_structure(members, required_safety_factor=REQUIRED_SF)


def main() -> None:
    card = screen_skid_positions()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
