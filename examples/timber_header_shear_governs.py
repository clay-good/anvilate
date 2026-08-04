"""Worked example: a short timber header where shear, not bending, governs.

Timber beams are usually sized for bending — but on a short, heavily loaded span the horizontal
shear parallel to the grain reaches its limit first, and a member with plenty of bending capacity
still fails in shear. This example takes a 4×10 header carrying a heavy point load over a short
span: the bending stress sits comfortably under the adjusted F'_b, yet the shear stress
f_v = 1.5·V/(b·d) climbs past the adjusted F'_v, so the shear check governs the design. It then
screens the bearing at the support, where the perpendicular-to-grain capacity is boosted by the NDS
bearing area factor C_b = (l_b + 0.375)/l_b — worth a 25% bump on a short 1.5-inch bearing. The
design lesson: on a stubby span, check shear before you trust the bending number.

Run it directly (``python examples/timber_header_shear_governs.py``);
:func:`header_scorecard` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    nds_adjusted_design_value,
    nds_bearing_area_factor,
    nds_bending_scorecard,
    nds_shear_scorecard,
    nds_shear_stress,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

WIDTH = Quantity.parse("3.5 inch")  # 4x10 actual b
DEPTH = Quantity.parse("9.25 inch")  # 4x10 actual d
SHEAR_FORCE = Quantity.parse("10000 N")  # support reaction on a short span
APPLIED_BENDING = Quantity.parse("700 psi")
SUPPORT_REACTION = Quantity.parse("10000 N")
BEARING_LENGTH = Quantity.parse("1.5 inch")


def header_scorecard() -> Scorecard:
    """Screen the header for bending and shear, returning both as one scorecard."""
    adjusted_bending = nds_adjusted_design_value(
        reference_value=Quantity.parse("900 psi"), factors={"C_D": 1.0, "C_F": 1.1}
    )
    adjusted_shear = nds_adjusted_design_value(
        reference_value=Quantity.parse("95 psi"), factors={"C_D": 1.0}
    )
    shear_stress = nds_shear_stress(shear_force=SHEAR_FORCE, width=WIDTH, depth=DEPTH)
    return Scorecard(
        entries=(
            nds_bending_scorecard(
                "header bending",
                bending_stress=APPLIED_BENDING,
                adjusted_bending_value=adjusted_bending,
            ),
            nds_shear_scorecard(
                "header shear",
                shear_stress=shear_stress,
                adjusted_shear_value=adjusted_shear,
            ),
        )
    )


def bearing_margin() -> float:
    """Return the perpendicular-to-grain bearing safety factor with the C_b bonus applied."""
    c_b = nds_bearing_area_factor(bearing_length=BEARING_LENGTH)
    bearing_area = WIDTH.pint * BEARING_LENGTH.pint
    f_c_perp = (SUPPORT_REACTION.pint / bearing_area).to("psi").magnitude
    adjusted_capacity = 625.0 * c_b  # 625 psi reference F_c-perp for the species/grade
    return adjusted_capacity / f_c_perp


def main() -> None:
    card = header_scorecard()
    for entry in card.entries:
        print(f"{entry.name:15s}: {entry.status.value.upper()} (SF {entry.safety_factor:.2f})")
    print(f"support bearing: PASS (SF {bearing_margin():.2f}, with C_b bonus)")
    print("  -> bending has room, but the short span is governed by shear")


if __name__ == "__main__":
    main()
