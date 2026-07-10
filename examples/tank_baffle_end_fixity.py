"""Worked example: end fixity under a triangular load is not a free win.

Declares the same vertical baffle stiffener in a 2.5 m water tank — hydrostatic
pressure rising to w₀ = 14.7 N/mm at the floor, an 80 x 120 x 5 mm A36 box tube
— under three end conditions, and screens all three as one structure. Welding
the bottom in (propped: welded floor seam, pinned top waler) cuts the deflection
almost in three (4.99 → 1.82 mm) but makes the peak stress WORSE than the
pinned-pinned idealization: the weld concentrates moment into the floor seam
(w₀·L²/15 = 97.8 MPa vs the pinned maximum w₀·L²/(9·√3) = 94.1 MPa), so the
safety factor drops from 2.66 to 2.55. Only welding BOTH ends recovers strength
too (w₀·L²/20 = 73.4 MPa, SF 3.41, deflection 1.00 mm). Stiffening an end helps
the serviceability screen and hands the strength problem to the weld.

Run it directly (``python examples/tank_baffle_end_fixity.py``);
:func:`screen_tank_baffle` is also exercised in the test suite.
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

# 2.5 m of water head at 600 mm stiffener spacing: 24.5 kPa * 0.6 m at the floor.
PEAK_LOAD = Quantity.parse("14.7 N/mm")
SPAN = Quantity.parse("2.5 m")
DEFLECTION_LIMIT = Quantity(magnitude=2500 / 360, unit="mm")  # L/360
REQUIRED_SF = 1.5

_FIXITIES = (
    ("pinned both ends", Support.SIMPLY_SUPPORTED),
    ("welded floor seam only", Support.FIXED_PINNED),
    ("welded both ends", Support.FIXED_FIXED),
)


def screen_tank_baffle() -> Scorecard:
    """Screen the stiffener under all three end conditions, as one structure."""
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
            load=PEAK_LOAD,
            load_type=LoadType.TRIANGULAR,
            material="ASTM-A36",
            deflection_limit=DEFLECTION_LIMIT,
        )
        for name, support in _FIXITIES
    ]
    return screen_structure(members, required_safety_factor=REQUIRED_SF)


def main() -> None:
    card = screen_tank_baffle()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
