"""Worked example: why a masonry wall's slenderness, not its strength, sets its allowable.

A concrete-block wall is designed to TMS 402 allowable-stress rules, and a masonry
compression member is a buckling problem as much as a crushing one. The allowable axial
stress starts at 0.25·f'm but is derated by a factor that falls with the height-to-radius
ratio h/r: a stocky pier (h/r = 30) keeps most of it, but a slender wall (h/r = 90) has
given away nearly half before the block is anywhere near its 10 MPa strength. The example
runs the same wall at three slendernesses to show how much capacity slenderness alone
removes, then sizes a short reinforced pier where four bars add a steel term the plain
wall never had.

Run it directly (``python examples/masonry_wall_slenderness.py``);
:func:`wall_allowables` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    masonry_allowable_axial_stress,
    masonry_column_axial_capacity,
)
from anvilate.units import Quantity

MASONRY_STRENGTH = Quantity.parse("10 MPa")  # f'm, grouted concrete block
SLENDERNESS_CASES = (30.0, 60.0, 90.0)  # h/r: stocky, mid, slender

PIER_NET_AREA = Quantity.parse("1e5 mm**2")  # net (grouted) cross-section
PIER_SLENDERNESS = 40.0
PIER_STEEL_AREA = Quantity.parse("800 mm**2")  # four #16 bars
PIER_STEEL_STRESS = Quantity.parse("165 MPa")  # F_s = 0.6*f_y, code cap


def wall_allowables() -> dict[str, float]:
    """Return the allowable stress (MPa) at each slenderness and the reinforced pier P_a (kN)."""
    out = {
        f"Fa_hr_{int(hr)}_mpa": masonry_allowable_axial_stress(
            masonry_strength=MASONRY_STRENGTH, slenderness_ratio=hr
        )
        .to("MPa")
        .magnitude
        for hr in SLENDERNESS_CASES
    }
    out["pier_reinforced_kn"] = (
        masonry_column_axial_capacity(
            masonry_strength=MASONRY_STRENGTH,
            net_area=PIER_NET_AREA,
            slenderness_ratio=PIER_SLENDERNESS,
            steel_area=PIER_STEEL_AREA,
            steel_allowable_stress=PIER_STEEL_STRESS,
        )
        .to("kN")
        .magnitude
    )
    out["pier_plain_kn"] = (
        masonry_column_axial_capacity(
            masonry_strength=MASONRY_STRENGTH,
            net_area=PIER_NET_AREA,
            slenderness_ratio=PIER_SLENDERNESS,
        )
        .to("kN")
        .magnitude
    )
    return out


def main() -> None:
    a = wall_allowables()
    stocky = a["Fa_hr_30_mpa"]
    for hr in SLENDERNESS_CASES:
        fa = a[f"Fa_hr_{int(hr)}_mpa"]
        print(f"h/r = {int(hr):>2} : Fa = {fa:.3f} MPa  ({fa / stocky:.0%} of the stocky value)")
    plain = a["pier_plain_kn"]
    reinf = a["pier_reinforced_kn"]
    print(f"pier  plain : P_a = {plain:.0f} kN")
    print(f"pier  4 bars: P_a = {reinf:.0f} kN  (+{reinf - plain:.0f} kN from the steel)")


if __name__ == "__main__":
    main()
