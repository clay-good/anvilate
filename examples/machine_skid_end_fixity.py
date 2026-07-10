"""Worked example: welding the end a skid parks against is a free stiffness win.

Declares the same 2 m A36 floor beam (80 x 120 x 5 mm box) carrying a 10 N/mm
machine skid over the first 1 m of its span — a half-span end patch — under
three end conditions, and screens all three as one structure. Welding in the
end the skid parks against (propped: welded at the skid end, resting on a post
at the other) cuts the deflection three-fold (1.398 → 0.451 mm) at ZERO stress
cost: for a half-span patch the wall's hogging moment w·a²·(2L−a)²/(8L²) lands
exactly on the pinned case's sagging peak R₁²/(2w) = 9·w·L²/128, so both screen
at SF 5.56. Contrast the tank-baffle example, where the same single weld under
a triangular load RAISED the peak stress — whether partial fixity is free
depends on the load shape, and declaring both is how the screen can tell.
Welding both ends is better still: SF 6.83 and 0.285 mm.

Run it directly (``python examples/machine_skid_end_fixity.py``);
:func:`screen_machine_skid` is also exercised in the test suite.
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
PATCH = Quantity.parse("1 m")  # the skid footprint, parked against one end
SPAN = Quantity.parse("2 m")
DEFLECTION_LIMIT = Quantity(magnitude=2000 / 360, unit="mm")  # L/360
REQUIRED_SF = 1.5

_FIXITIES = (
    ("pinned both ends", Support.SIMPLY_SUPPORTED),
    ("welded at the skid end", Support.FIXED_PINNED),
    ("welded both ends", Support.FIXED_FIXED),
)


def screen_machine_skid() -> Scorecard:
    """Screen the skid-loaded beam under all three end conditions, as one structure."""
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
            support=support,
            load=SKID_LOAD,
            load_type=LoadType.DISTRIBUTED,
            material="ASTM-A36",
            deflection_limit=DEFLECTION_LIMIT,
            loaded_length=PATCH,
        )
        for name, support in _FIXITIES
    ]
    return screen_structure(members, required_safety_factor=REQUIRED_SF)


def main() -> None:
    card = screen_machine_skid()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
