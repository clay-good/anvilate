"""Worked example: screening a welded lifting padeye with the structural pack.

Declares a lifting padeye — a lug welded to a base plate — that raises a 50 kN
load, and screens the whole assembly in one call. The pack screens the lug's two
limit states (net-section tension and pin bearing, ASME BTH-1) and the attaching
fillet weld's throat shear (AISC J2.4), rolling every result into one scorecard.

Run it directly (``python examples/lifting_padeye.py``); :func:`screen_padeye` is
also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.structural import (
    LiftingLug,
    WeldedConnection,
    screen_structure,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

LIFT_LOAD = Quantity.parse("50 kN")


def screen_padeye() -> Scorecard:
    """Declare and screen the lifting padeye, returning the assembly scorecard."""
    lug = LiftingLug(
        name="padeye",
        width=Quantity.parse("80 mm"),
        hole_diameter=Quantity.parse("25 mm"),
        thickness=Quantity.parse("12 mm"),
        load=LIFT_LOAD,
        material="ASTM-A36",
    )
    weld = WeldedConnection(
        name="padeye_weld",
        leg_size=Quantity.parse("8 mm"),
        weld_length=Quantity.parse("160 mm"),  # both sides of the 80 mm base
        load=LIFT_LOAD,
        electrode_strength=Quantity.parse("483 MPa"),  # E70
    )
    # A rigging safety factor of 2 on the lifted load (ASME BTH-1 design category).
    return screen_structure([lug, weld], required_safety_factor=2.0)


def main() -> None:
    card = screen_padeye()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
