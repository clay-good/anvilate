"""Worked example: the short timber header that crushes at its support, not in its span.

Sizing a wood beam by bending alone is a habit picked up from long spans, where the
moment does grow faster than anything else. Shorten the span and the arithmetic
inverts. Bending demand falls with L², shear with L, and the bearing stress at the
support does not fall at all — the reaction still has to pass through the same little
contact patch. Wood is also far weaker across the grain than along it, so the patch
is where a short, heavily loaded member gives out first.

A 4x10 sawn header (3.5 x 9.25 in actual) spans 3.5 ft under 1,950 lb/ft and lands
1.5 in onto a stud-wall plate at each end. Screened against the same species/grade
reference values — F_b = 900 psi, F_v = 180 psi, F_c⊥ = 625 psi — the beam itself is
fine: bending runs at a safety factor of 1.25 and horizontal shear at 1.14. The
bearing does not. The 3,412 lb reaction spread over 3.5 x 1.5 in is 650 psi across
the grain against a 625 psi allowable, and the header fails at a detail no bending
check can see.

The fix is not a bigger beam. Landing the same header on a 3.5 in post instead of the
edge of a plate more than doubles the bearing area and takes the check to a safety
factor of 2.24, with bending and shear untouched. That is the useful thing about
running all three: the failing check names the bearing length, so the repair is a
$20 post rather than a deeper member.

One NDS subtlety shows up here. The bearing area factor C_b = (l_b + 0.375 in)/l_b
rewards a short bearing for the fibres just past its ends that help carry the load —
but only when the bearing sits at least 3 in from the member end. A header stopping
flush at its support has no fibre past the end to recruit, so C_b is 1.0 and the
bonus is not available. Run the whole thing directly
(``python examples/timber_header_bearing_governs.py``); :func:`screen_header` is
exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    CrossSection,
    LoadDuration,
    nds_adjusted_design_value,
    nds_bearing_area_factor,
    nds_bearing_scorecard,
    nds_bearing_stress,
    nds_bending_scorecard,
    nds_load_duration_factor,
    nds_shear_scorecard,
    nds_shear_stress,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

# A 4x10 sawn header: 3.5 x 9.25 in actual, spanning 3.5 ft.
WIDTH = Quantity.parse("3.5 inch")
DEPTH = Quantity.parse("9.25 inch")
SPAN = Quantity.parse("42 inch")
LINE_LOAD = Quantity.parse("1950 lbf/ft")

# Reference design values for the species and grade — the caller's, from the NDS tables.
REFERENCE_BENDING = Quantity.parse("900 psi")  # F_b
REFERENCE_SHEAR = Quantity.parse("180 psi")  # F_v
REFERENCE_BEARING = Quantity.parse("625 psi")  # F_c-perpendicular

# The header sits flush on its supports, so there is no fibre past the bearing to recruit.
END_DISTANCE = Quantity.parse("0 inch")

# Occupancy load duration (NDS Table 2.3.2). C_D scales bending and shear; NDS 2.3.2 does
# not apply it to compression perpendicular to grain, so the bearing chain omits it.
_C_D = nds_load_duration_factor(LoadDuration.TEN_YEAR)


def _reaction() -> Quantity:
    """The end reaction of the uniformly loaded simple span, R = wL/2."""
    w = LINE_LOAD.to("lbf/inch").magnitude
    return Quantity(magnitude=w * SPAN.to("inch").magnitude / 2, unit="lbf")


def _bending_stress() -> Quantity:
    """The maximum bending stress f_b = M/S, with M = wL²/8."""
    w = LINE_LOAD.to("lbf/inch").magnitude
    moment = w * SPAN.to("inch").magnitude ** 2 / 8  # lbf*inch
    section = CrossSection.rectangular(width=WIDTH, height=DEPTH)
    return Quantity(magnitude=moment / section.section_modulus.to("inch**3").magnitude, unit="psi")


def screen_header(bearing_length: Quantity) -> Scorecard:
    """Screen the header for bending, horizontal shear, and bearing at a given bearing length."""
    reaction = _reaction()
    bearing_chain = {
        "C_b": nds_bearing_area_factor(bearing_length=bearing_length, end_distance=END_DISTANCE)
    }
    return Scorecard(
        entries=(
            nds_bending_scorecard(
                "header bending",
                bending_stress=_bending_stress(),
                adjusted_bending_value=nds_adjusted_design_value(
                    reference_value=REFERENCE_BENDING, factors={"C_D": _C_D}
                ),
            ),
            nds_shear_scorecard(
                "horizontal shear",
                shear_stress=nds_shear_stress(shear_force=reaction, width=WIDTH, depth=DEPTH),
                adjusted_shear_value=nds_adjusted_design_value(
                    reference_value=REFERENCE_SHEAR, factors={"C_D": _C_D}
                ),
            ),
            nds_bearing_scorecard(
                "end bearing",
                bearing_stress=nds_bearing_stress(
                    bearing_force=reaction, width=WIDTH, bearing_length=bearing_length
                ),
                adjusted_bearing_value=nds_adjusted_design_value(
                    reference_value=REFERENCE_BEARING, factors=bearing_chain
                ),
            ),
        )
    )


def screen_on_wall_plate() -> Scorecard:
    """Bearing 1.5 in on a stud-wall plate: bending and shear pass, the bearing crushes."""
    return screen_header(Quantity.parse("1.5 inch"))


def screen_on_post() -> Scorecard:
    """The same header on a 3.5 in post: the bearing check clears with room to spare."""
    return screen_header(Quantity.parse("3.5 inch"))


def main() -> None:
    reaction = _reaction()
    print(f"reaction at each support: {reaction.to('lbf').magnitude:.0f} lbf")
    for label, card in (
        ("1.5 in on a wall plate", screen_on_wall_plate()),
        ("3.5 in on a post", screen_on_post()),
    ):
        print(f"\n{label}:")
        for entry in card.entries:
            print(f"  {entry}")
        print(f"  {card}")


if __name__ == "__main__":
    main()
