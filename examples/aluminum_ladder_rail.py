"""Worked example: why an aluminum strut buckles where a steel one would not.

Aluminum's elastic modulus is about a third of steel's, so an aluminum member of the
same slenderness reaches its elastic buckling stress at roughly a third of the steel
value — the reason aluminum design is so buckling-driven. This example takes a 6061-T6
extruded strut (a ladder side rail, a light-frame member) at a slenderness of kL/r = 80
and reads its compressive strength off the Aluminum Design Manual curve, then contrasts
it with the pure yield strength the material could reach if buckling never intervened.

With the ADM buckling constants for 6061-T6 (B = 267 MPa, D = 1.63 MPa, C = 66) and
E = 69.6 GPa, the strut at kL/r = 80 is past the intersection C, so it buckles
elastically at only about 107 MPa — well under the 240 MPa yield. The same section as a
short tension member, by contrast, develops the full material strength (240 MPa, since
its ultimate over the tension coefficient still clears yield).

The example composes the ADM buckling stress and the ADM tension stress.

Run it directly (``python examples/aluminum_ladder_rail.py``);
:func:`rail_strengths` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import aluminum_buckling_stress, aluminum_tension_stress
from anvilate.units import Quantity

SLENDERNESS = 80.0  # kL/r of the strut
INTERCEPT = Quantity.parse("267 MPa")  # ADM B_c for 6061-T6
SLOPE = Quantity.parse("1.63 MPa")  # ADM D_c
INTERSECTION = 66.0  # ADM C_c
MODULUS = Quantity.parse("69600 MPa")

YIELD = Quantity.parse("240 MPa")  # F_ty, 6061-T6
ULTIMATE = Quantity.parse("260 MPa")  # F_tu
TENSION_COEFFICIENT = 1.0  # k_t


def rail_strengths() -> dict[str, float]:
    """Return the ADM compressive buckling stress and the tension stress of the rail."""
    buckling = aluminum_buckling_stress(
        slenderness=SLENDERNESS,
        intercept=INTERCEPT,
        slope=SLOPE,
        intersection_slenderness=INTERSECTION,
        elastic_modulus=MODULUS,
    )
    tension = aluminum_tension_stress(
        yield_strength=YIELD,
        ultimate_strength=ULTIMATE,
        tension_coefficient=TENSION_COEFFICIENT,
    )
    return {
        "buckling_stress_mpa": buckling.to("MPa").magnitude,
        "tension_stress_mpa": tension.to("MPa").magnitude,
    }


def main() -> None:
    r = rail_strengths()
    b = r["buckling_stress_mpa"]
    t = r["tension_stress_mpa"]
    print(f"compression at kL/r = 80 (ADM buckling): {b:.0f} MPa")
    print(f"tension (min of yield and rupture)      : {t:.0f} MPa")
    print(f"buckling gives away {100 * (1 - b / t):.0f}% of the material strength")


if __name__ == "__main__":
    main()
