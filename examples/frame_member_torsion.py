"""Worked example: the weld someone deleted to save a pass.

A machine subframe cross-member carries a 1.2 kN·m torque from an off-centre
load. Detailed as a closed 100 x 60 x 5 mm box tube (RHS) the wall shear is a
comfortable ~23 MPa against a 100 MPa allowable — SF 4.3. Then a shop drawing
"simplification" leaves the section open: the same 5 mm wall, same developed
300 mm perimeter, but the longitudinal seam is left unwelded to skip a weld
pass. Nothing about the load changes, and the bending/axial screens do not
move — but torsionally the two members are not even close. A closed thin tube
runs a uniform shear flow all the way around (Bredt); an open one has no closed
loop, so the whole torque is resisted across the thin wall alone: tau =
3T/(b·t^2) instead of T/(2·A_m·t). The open seam multiplies the wall shear by
about 20x to ~480 MPa — well past yield — and the member also twists roughly
(b/t)^2 more. The fix is the deleted weld, not a heavier wall: closing the
section is the whole point of a torque tube.

Run it directly (``python examples/frame_member_torsion.py``);
:func:`screen_frame_member_torsion` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    rectangular_tube_torsional_stress,
    strength_scorecard,
    thin_open_strip_torsional_stress,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

TORQUE = Quantity.parse("1200 N*m")  # from the off-centre load
WIDTH = Quantity.parse("100 mm")  # box outer width
HEIGHT = Quantity.parse("60 mm")  # box outer height
WALL = Quantity.parse("5 mm")
# Slit open, the same wall unrolls to its median perimeter 2*[(W-t)+(H-t)].
DEVELOPED_WIDTH = Quantity.parse("300 mm")
SHEAR_ALLOWABLE = Quantity.parse("100 MPa")  # ~0.4*Sy for A36 steel, torsional
REQUIRED_SF = 1.5


def screen_frame_member_torsion() -> Scorecard:
    """Screen the wall shear of the cross-member both ways: seam open vs welded
    closed, same torque and same wall."""
    open_stress = thin_open_strip_torsional_stress(
        torque=TORQUE, width=DEVELOPED_WIDTH, thickness=WALL
    )
    closed_stress = rectangular_tube_torsional_stress(
        torque=TORQUE, width=WIDTH, height=HEIGHT, wall_thickness=WALL
    )
    return Scorecard(
        entries=(
            strength_scorecard(
                "open seam wall shear",
                stress=open_stress,
                allowable=SHEAR_ALLOWABLE,
                required=REQUIRED_SF,
            ),
            strength_scorecard(
                "closed box wall shear",
                stress=closed_stress,
                allowable=SHEAR_ALLOWABLE,
                required=REQUIRED_SF,
            ),
        )
    )


def main() -> None:
    card = screen_frame_member_torsion()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
