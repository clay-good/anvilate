"""Worked example: a masonry wall its gravity check passes but its combined check fails.

A concrete-block wall is designed to TMS 402 allowable-stress rules, and a masonry
compression member is a buckling problem as much as a crushing one: the allowable axial
stress starts at 0.25·f'm but is derated by a slenderness factor on the height-to-radius
ratio h/r, so a slender wall gives away much of it before the block is near its 10 MPa
strength. But gravity is only half the wall's life. Under out-of-plane wind it also bends,
and TMS 402 governs the pair with a unity check f_a/F_a + f_b/F_b ≤ 1, not either stress
alone. This wall's axial utilization is a comfortable 0.52 — a gravity-only look passes it
— yet once the wind bending is added, the combined ratio climbs past 1.0 and the wall
fails. The example runs the axial allowable across three slendernesses to show the derate,
then the combined check that actually sizes the wall.

Run it directly (``python examples/masonry_wall_slenderness.py``);
:func:`wall_check` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    masonry_allowable_axial_stress,
    masonry_allowable_flexural_stress,
    masonry_combined_stress_ratio,
)
from anvilate.units import Quantity

MASONRY_STRENGTH = Quantity.parse("10 MPa")  # f'm, grouted concrete block
SLENDERNESS_CASES = (30.0, 60.0, 90.0)  # h/r: stocky, mid, slender

WALL_SLENDERNESS = 40.0  # h/r of the design wall
AXIAL_STRESS = Quantity.parse("1.2 MPa")  # f_a from dead + live gravity
FLEXURAL_STRESS = Quantity.parse("2.2 MPa")  # f_b, extreme fiber from out-of-plane wind


def wall_check() -> dict[str, float]:
    """Return the allowable stress (MPa) at each slenderness and the design wall's utilizations."""
    out = {
        f"Fa_hr_{int(hr)}_mpa": masonry_allowable_axial_stress(
            masonry_strength=MASONRY_STRENGTH, slenderness_ratio=hr
        )
        .to("MPa")
        .magnitude
        for hr in SLENDERNESS_CASES
    }
    fa_allow = masonry_allowable_axial_stress(
        masonry_strength=MASONRY_STRENGTH, slenderness_ratio=WALL_SLENDERNESS
    )
    fb_allow = masonry_allowable_flexural_stress(masonry_strength=MASONRY_STRENGTH)
    out["axial_utilization"] = AXIAL_STRESS.to("MPa").magnitude / fa_allow.to("MPa").magnitude
    out["combined_unity"] = masonry_combined_stress_ratio(
        axial_stress=AXIAL_STRESS,
        allowable_axial_stress=fa_allow,
        flexural_stress=FLEXURAL_STRESS,
        allowable_flexural_stress=fb_allow,
    )
    return out


def main() -> None:
    a = wall_check()
    stocky = a["Fa_hr_30_mpa"]
    for hr in SLENDERNESS_CASES:
        fa = a[f"Fa_hr_{int(hr)}_mpa"]
        print(f"h/r = {int(hr):>2} : Fa = {fa:.3f} MPa  ({fa / stocky:.0%} of the stocky value)")
    axial = a["axial_utilization"]
    unity = a["combined_unity"]
    print(f"gravity only  : f_a/F_a           = {axial:.2f}  ({'PASS' if axial <= 1 else 'FAIL'})")
    print(f"with wind     : f_a/F_a + f_b/F_b = {unity:.2f}  ({'PASS' if unity <= 1 else 'FAIL'})")


if __name__ == "__main__":
    main()
