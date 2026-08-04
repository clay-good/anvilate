"""Worked example: the wet-service factor that flips a timber verdict.

An NDS timber check never screens the raw tabulated strength — it screens the
*adjusted* design value, the reference value multiplied by a chain of factors for
the real service conditions. Most of the time the chain nudges the number a little.
But one factor can decide the design outright: the wet-service factor C_M, which
derates a member that will run above 19% moisture content.

A floor joist of a species/grade with a 900 psi reference bending value carries a
1000 psi applied bending stress. Adjusted for the occupancy load duration (C_D = 1.0
from NDS Table 2.3.2), the repetitive-member factor (C_r = 1.15, joists sharing the
load), and the size factor (C_F = 1.1), the *dry* adjusted value is 1138 psi and the
joist passes with a little room. Put the same joist in a damp crawlspace and the
wet-service factor C_M = 0.85 drops the adjusted value to 968 psi — below the applied
stress — and the identical member now fails.

The point of the factor chain is that it is visible: the verdict flipped on one
factor, and the record shows which. Anvilate composes the chain and screens the
stress; the reference design value is the caller's, from the copyrighted NDS
species/grade tables. Run it directly
(``python examples/floor_joist_wet_service.py``); :func:`screen_joist` is exercised
in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    LoadDuration,
    nds_adjusted_design_value,
    nds_bending_scorecard,
    nds_load_duration_factor,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

REFERENCE_BENDING = Quantity.parse("900 psi")  # F_b for the species/grade (user-supplied)
APPLIED_BENDING = Quantity.parse("1000 psi")  # f_b = M/S from the load

# The factor chain common to both cases: occupancy load duration, size, repetitive use.
_BASE_FACTORS = {
    "C_D": nds_load_duration_factor(LoadDuration.TEN_YEAR),
    "C_F": 1.1,  # size factor (from the NDS tables for this depth)
    "C_r": 1.15,  # repetitive-member factor (joists at ≤ 24 in. sharing the load)
}


def screen_joist(wet_service_factor: float) -> Scorecard:
    """Screen the joist's bending with a given wet-service factor C_M."""
    adjusted = nds_adjusted_design_value(
        reference_value=REFERENCE_BENDING,
        factors={**_BASE_FACTORS, "C_M": wet_service_factor},
    )
    return Scorecard(
        entries=(
            nds_bending_scorecard(
                "joist bending",
                bending_stress=APPLIED_BENDING,
                adjusted_bending_value=adjusted,
            ),
        )
    )


def screen_dry() -> Scorecard:
    """Dry service (C_M = 1.0): the joist passes."""
    return screen_joist(1.0)


def screen_wet() -> Scorecard:
    """Wet service (C_M = 0.85 for bending): the same joist fails."""
    return screen_joist(0.85)


def main() -> None:
    for label, c_m in (("dry (C_M = 1.0)", 1.0), ("wet (C_M = 0.85)", 0.85)):
        adjusted = nds_adjusted_design_value(
            reference_value=REFERENCE_BENDING, factors={**_BASE_FACTORS, "C_M": c_m}
        )
        print(f"{label}: adjusted F'_b = {adjusted.to('psi').magnitude:.0f} psi")
        print(f"  {screen_joist(c_m).entries[0]}")


if __name__ == "__main__":
    main()
