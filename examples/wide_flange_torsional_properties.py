"""Worked example: the two torsional properties of a wide-flange beam, checked against the Manual.

A wide-flange beam resists twist two ways, and lateral-torsional buckling depends on both. Saint-
Venant torsion, captured by the constant J, is the shear the thin walls carry; warping torsion,
captured by the constant C_w, is the in-plane bending of the flanges as the section twists non-
uniformly. This example computes both for a W18×50 from its plate dimensions — J as the sum of each
leg's b·t³/3, and C_w = I_y·h²/4 — and compares them to the published AISC Manual values. The J from
thin-wall theory runs a little low because it ignores the rolled fillets, while C_w lands almost
exact; together they are the pair every unbraced-beam buckling check consumes.

Run it directly (``python examples/wide_flange_torsional_properties.py``);
:func:`w18x50_torsion` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import open_section_torsion_constant, warping_constant_doubly_symmetric
from anvilate.units import Quantity

# W18x50 plate dimensions and the tabulated weak-axis inertia.
FLANGE_WIDTH = Quantity.parse("7.495 in")
FLANGE_THICKNESS = Quantity.parse("0.57 in")
WEB_CLEAR_HEIGHT = Quantity.parse("16.86 in")  # d - 2*t_f
WEB_THICKNESS = Quantity.parse("0.355 in")
WEAK_AXIS_INERTIA = Quantity.parse("40.1 in**4")
FLANGE_CENTROID_DISTANCE = Quantity.parse("17.43 in")  # d - t_f

MANUAL_J = 1.24  # in^4, AISC Manual
MANUAL_CW = 3040.0  # in^6, AISC Manual


def w18x50_torsion() -> dict[str, float]:
    """Return the computed J and C_w (imperial) for a W18x50."""
    j = open_section_torsion_constant(
        rectangles=[
            (FLANGE_WIDTH, FLANGE_THICKNESS),
            (FLANGE_WIDTH, FLANGE_THICKNESS),
            (WEB_CLEAR_HEIGHT, WEB_THICKNESS),
        ]
    )
    cw = warping_constant_doubly_symmetric(
        weak_axis_moment_of_inertia=WEAK_AXIS_INERTIA,
        flange_centroid_distance=FLANGE_CENTROID_DISTANCE,
    )
    return {
        "j_in4": j.to("in**4").magnitude,
        "cw_in6": cw.to("in**6").magnitude,
    }


def main() -> None:
    t = w18x50_torsion()
    print(f"J  (St-Venant) : {t['j_in4']:.2f} in⁴ (Manual {MANUAL_J:.2f} — thin-wall runs low)")
    print(f"C_w (warping)  : {t['cw_in6']:.0f} in⁶ (Manual {MANUAL_CW:.0f})")
    print("  -> J and C_w are the torsional pair every lateral-torsional-buckling check consumes")


if __name__ == "__main__":
    main()
