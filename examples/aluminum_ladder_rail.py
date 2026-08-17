"""Worked example: why an aluminum strut buckles where a steel one would not.

Aluminum's elastic modulus is about a third of steel's, so an aluminum member of the
same slenderness reaches its elastic buckling stress at roughly a third of the steel
value — the reason aluminum design is so buckling-driven. This example takes a 6061-T6
extruded strut (a ladder side rail, a light-frame member) at a slenderness of kL/r = 80
and reads its compressive strength off the Aluminum Design Manual §E.3 curve, then
contrasts it with the pure yield strength the material could reach if buckling never
intervened.

The ADM §B.4 buckling constants come out of the alloy's own F_cy = 240 MPa and
E = 69.6 GPa as B_c = 269.9 MPa, D_c = 1.68 MPa, C_c = 65.8 — no table is consulted. At
kL/r = 80 the strut is past C_c, so it is on the elastic branch and carries only 91 MPa,
against the 240 MPa it develops in tension: buckling gives away 62% of the material.

That elastic branch is 0.85·pi^2·E/lambda^2, not pi^2·E/lambda^2. The 0.85 is the ADM's
allowance for the out-of-straightness a real column is fabricated with, and dropping it
overstates this strut by 17.6% — which is exactly what happens if the generic
:func:`anvilate.analysis.aluminum_buckling_stress` is used with column constants instead
of the §E.3 screen. That function is a straight-line/Euler evaluator for a caller who
already has B, D and C; it is not the column curve.

Run it directly (``python examples/aluminum_ladder_rail.py``);
:func:`rail_strengths` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    aluminum_buckling_constants,
    aluminum_member_buckling_stress,
    aluminum_tension_stress,
)
from anvilate.units import Quantity

SLENDERNESS = 80.0  # kL/r of the strut
COMPRESSIVE_YIELD = Quantity.parse("240 MPa")  # F_cy, 6061-T6
MODULUS = Quantity.parse("69600 MPa")

YIELD = Quantity.parse("240 MPa")  # F_ty, 6061-T6
ULTIMATE = Quantity.parse("260 MPa")  # F_tu
TENSION_COEFFICIENT = 1.0  # k_t


def rail_strengths() -> dict[str, float]:
    """Return the ADM §E.3 compressive buckling stress and the tension stress."""
    constants = aluminum_buckling_constants(
        compressive_yield=COMPRESSIVE_YIELD, elastic_modulus=MODULUS
    )
    buckling = aluminum_member_buckling_stress(
        slenderness=SLENDERNESS,
        compressive_yield=COMPRESSIVE_YIELD,
        elastic_modulus=MODULUS,
        constants=constants,
    )
    tension = aluminum_tension_stress(
        yield_strength=YIELD,
        ultimate_strength=ULTIMATE,
        tension_coefficient=TENSION_COEFFICIENT,
    )
    return {
        "buckling_stress_mpa": buckling.to("MPa").magnitude,
        "tension_stress_mpa": tension.to("MPa").magnitude,
        "intersection_slenderness": constants.intersection_member,
    }


def main() -> None:
    r = rail_strengths()
    b = r["buckling_stress_mpa"]
    t = r["tension_stress_mpa"]
    print(f"ADM C_c for this alloy                  : {r['intersection_slenderness']:.1f}")
    print(f"compression at kL/r = 80 (ADM \u00a7E.3)      : {b:.0f} MPa")
    print(f"tension (min of yield and rupture)      : {t:.0f} MPa")
    print(f"buckling gives away {100 * (1 - b / t):.0f}% of the material strength")


if __name__ == "__main__":
    main()
