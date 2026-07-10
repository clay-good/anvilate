"""Worked example: which end of a propped stiffener gets the weld.

Declares the same vertical stiffener on a 1.5 m water barrier — a 60 x 10 mm
A36 flat bar at 500 mm centers, water to the brim, so the load is a hydrostatic
triangle peaking at w₀ = 7.36 N/mm at the sill — welded at one end and propped
at the other, and screens both weld ends as one structure. Welding the sill
puts the pressure peak at the wall (M = w₀·L²/15): the bar is stiff
(2.469 mm, inside the L/500 = 3 mm seal limit) but overstressed (SF 1.36,
FAIL at 1.5). Mirroring the fixity — weld at the top waler, prop at the sill
(``triangle_mirrored``) — trims the wall moment to 7·w₀·L²/120 and the
strength screen passes (SF 1.55), but the load now bears on the softer
mid-span and the deflection grows 28% to 3.155 mm, past the seal limit. The
two orientations fail OPPOSITE criteria: mirroring the weld trades strength
for serviceability, so the fix is a deeper bar, not a different weld end.

Run it directly (``python examples/stiffener_weld_end.py``);
:func:`screen_weld_ends` is also exercised in the test suite.
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

# 1.5 m of water head at 500 mm stiffener spacing: 14.7 kPa * 0.5 m.
PEAK_LOAD = Quantity.parse("7.36 N/mm")
SPAN = Quantity.parse("1.5 m")
DEFLECTION_LIMIT = Quantity(magnitude=1500 / 500, unit="mm")  # L/500 keeps the face seal
REQUIRED_SF = 1.5

_WELD_ENDS = (
    ("welded at the sill (peak at the wall)", False),
    ("welded at the waler (peak at the prop)", True),
)


def screen_weld_ends() -> Scorecard:
    """Screen the stiffener with the weld at either end, as one structure."""
    section = CrossSection.rectangular(
        width=Quantity.parse("10 mm"), height=Quantity.parse("60 mm")
    )
    members = [
        BeamMember(
            name=name,
            section=section,
            length=SPAN,
            support=Support.FIXED_PINNED,
            load=PEAK_LOAD,
            load_type=LoadType.TRIANGULAR,
            material="ASTM-A36",
            deflection_limit=DEFLECTION_LIMIT,
            triangle_mirrored=peak_at_prop,
        )
        for name, peak_at_prop in _WELD_ENDS
    ]
    return screen_structure(members, required_safety_factor=REQUIRED_SF)


def main() -> None:
    card = screen_weld_ends()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
