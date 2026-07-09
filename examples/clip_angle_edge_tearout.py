"""Worked example: a clip-angle bolt relocated toward the plate edge.

Declares an M10 bolt (annealed 4140) carrying 12 kN of shear through an 8 mm
A36 clip angle and screens it twice: once as detailed, 25 mm from the plate
edge, and once relocated to 9 mm — the kind of shift a field clash with a weld
or an adjacent bolt forces. The instructive part: bolt shear (SF 1.57) and
plate bearing (SF 1.67) never see the edge distance, so both positions clear
the 1.5 requirement identically. Only the AISC §J3.10 bolt-hole tear-out check
catches the move — the clear distance l_c drops from 20 mm to 4 mm and the
tear-out safety factor falls from 6.4 to 1.28. A screen that never declares the
edge distance goes silently green on a connection that would tear out.

Run it directly (``python examples/clip_angle_edge_tearout.py``);
:func:`screen_clip_bolt` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.structural import BoltedConnection, screen_structure
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

SHEAR_LOAD = Quantity.parse("12 kN")  # gravity, carried in single shear
DETAILED_EDGE = Quantity.parse("25 mm")  # as drawn
RELOCATED_EDGE = Quantity.parse("9 mm")  # shifted to clear the fillet weld


def screen_clip_bolt() -> Scorecard:
    """Screen the bolt at both edge distances, returning one card."""
    common = {
        "bolt_diameter": Quantity.parse("10 mm"),
        "plate_thickness": Quantity.parse("8 mm"),
        "load": SHEAR_LOAD,
        "bolt_material": "AISI-4140",
        "plate_material": "ASTM-A36",
    }
    as_detailed = BoltedConnection(name="as detailed", edge_distance=DETAILED_EDGE, **common)
    relocated = BoltedConnection(name="relocated", edge_distance=RELOCATED_EDGE, **common)
    return screen_structure([as_detailed, relocated], required_safety_factor=1.5)


def main() -> None:
    card = screen_clip_bolt()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
