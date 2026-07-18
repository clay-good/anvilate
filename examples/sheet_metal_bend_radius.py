"""Worked example: the bend a bigger press cannot save.

A 2 mm bracket in 5052-H32 aluminium is bent 90 degrees to make an L. The shop reads
off two numbers before cutting the blank. The press-brake tonnage is comfortable: air
bending a 1.2 m long, 2 mm sheet of 260 MPa alloy over a 16 mm V-die takes about 104 kN
(11 tonnes), and a 400 kN brake covers it nearly four times over. So the part looks easy
to make.

It is not, because of the second number. The drawing calls a 2 mm inner bend radius --
a "1t" bend, radius equal to thickness, the tightest a designer instinctively reaches
for. But the minimum bend radius is set by the *material's ductility*, not the press:
5052-H32 has a tensile reduction of area around 20 %, so R_min = t*(50/20 - 1) = 3 mm.
The 2 mm radius stretches the outer fibre past what the temper can take and the bend
cracks -- a safety factor of 0.67 on a limit a bigger machine does nothing to move.

The lesson is that a sheet-metal bend has two independent gates and the forgiving one
hides the strict one. Tonnage scales with strength and thickness and is almost always
easy on a modern brake; the minimum bend radius scales with *ductility* and is what
actually governs a tight bend. The fix is never a bigger press -- it is a larger bend
radius (open the tool to 3 mm), a softer temper (5052-O bends far tighter), or bending
across the grain. The bracket also carries a flat-blank length of 104.5 mm, the two
40/60 mm tangent-line flanges plus the bend allowance; cutting it to the 100 mm flange
sum would leave every downstream hole 4.5 mm out of place.

Run it directly (``python examples/sheet_metal_bend_radius.py``);
:func:`screen_bend` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import sheetmetal as sm
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

THICKNESS = Quantity.parse("2 mm")
INNER_RADIUS = Quantity.parse("2 mm")  # a 1t bend
BEND_ANGLE = 90.0
DIE_OPENING = Quantity.parse("16 mm")
BEND_LENGTH = Quantity.parse("1.2 m")
ULTIMATE_TENSILE = Quantity.parse("260 MPa")  # 5052-H32
REDUCTION_OF_AREA_PERCENT = 20.0  # 5052-H32 ductility
PRESS_CAPACITY = Quantity.parse("400 kN")
K_FACTOR = 0.44
FLANGES = (Quantity.parse("40 mm"), Quantity.parse("60 mm"))


def screen_bend() -> Scorecard:
    """Screen the bend on minimum bend radius and press-brake tonnage."""
    r_min = sm.minimum_bend_radius(
        thickness=THICKNESS, reduction_of_area_percent=REDUCTION_OF_AREA_PERCENT
    )
    force = sm.air_bending_force(
        ultimate_tensile_strength=ULTIMATE_TENSILE,
        bend_length=BEND_LENGTH,
        thickness=THICKNESS,
        die_opening=DIE_OPENING,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "bend radius vs ductility limit",
                computed=INNER_RADIUS.to("mm").magnitude / r_min.to("mm").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "press-brake tonnage",
                computed=PRESS_CAPACITY.to("kN").magnitude / force.to("kN").magnitude,
                required=1.0,
            ),
        )
    )


def flat_blank_length() -> Quantity:
    """The developed blank length (tangent-line flanges plus the bend allowance)."""
    return sm.flat_pattern_length(
        flange_lengths=FLANGES,
        bend_angle=BEND_ANGLE,
        inner_radius=INNER_RADIUS,
        thickness=THICKNESS,
        k_factor=K_FACTOR,
    )


def main() -> None:
    print(screen_bend())
    print(f"flat blank length: {flat_blank_length().to('mm').magnitude:.1f} mm")


if __name__ == "__main__":
    main()
