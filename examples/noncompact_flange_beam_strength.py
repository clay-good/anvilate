"""Worked example: what a noncompact flange costs a beam's bending strength (AISC §F3).

A compact beam reaches its full plastic moment M_p, but a beam with a noncompact compression flange
buckles that flange locally before the section fully yields, so AISC §F3 knocks the strength down
between the plastic and noncompact slenderness limits. This example takes a welded A992 I-shape with
a wide, relatively thin flange — a flange slenderness of 15, which the §B4.1 limits put in the
noncompact range (between 9.15 and 24.08). It first confirms the flange is noncompact, then applies
the §F3.2 interpolation to find the reduced nominal moment: the plastic moment of 10,000 kip·in
falls to about 8,400 kip·in, a 16% penalty the designer pays for the slender flange. The two steps
chain directly — the compactness limits that classify the flange are the same limits the strength
equation interpolates between.

Run it directly (``python examples/noncompact_flange_beam_strength.py``);
:func:`flange_governed_strength` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    aisc_flange_local_buckling_moment,
    classify_flexural_element,
    flexural_flange_slenderness_limits,
)
from anvilate.units import Quantity

ELASTIC_MODULUS = Quantity.parse("29000 ksi")
YIELD_STRENGTH = Quantity.parse("50 ksi")  # A992
FLANGE_SLENDERNESS = 15.0  # b_f/(2*t_f) — a wide thin flange
PLASTIC_MOMENT = Quantity.parse("10000 kip*inch")  # F_y * Z
RESIDUAL_YIELD_MOMENT = Quantity.parse("5950 kip*inch")  # 0.7 * F_y * S_x


def flange_governed_strength() -> dict[str, object]:
    """Return the flange class and the §F3 nominal moment against the plastic moment."""
    plastic_limit, noncompact_limit = flexural_flange_slenderness_limits(
        elastic_modulus=ELASTIC_MODULUS, yield_strength=YIELD_STRENGTH
    )
    flange_class = classify_flexural_element(
        slenderness=FLANGE_SLENDERNESS,
        plastic_limit=plastic_limit,
        noncompact_limit=noncompact_limit,
    )
    nominal = aisc_flange_local_buckling_moment(
        plastic_moment=PLASTIC_MOMENT,
        residual_yield_moment=RESIDUAL_YIELD_MOMENT,
        flange_slenderness=FLANGE_SLENDERNESS,
        plastic_limit=plastic_limit,
        noncompact_limit=noncompact_limit,
    )
    mp = PLASTIC_MOMENT.to("kip*inch").magnitude
    mn = nominal.to("kip*inch").magnitude
    return {
        "flange_class": flange_class.value,
        "plastic_moment_kip_in": mp,
        "nominal_moment_kip_in": mn,
        "reduction_percent": (1 - mn / mp) * 100.0,
    }


def main() -> None:
    r = flange_governed_strength()
    print(f"flange class      : {r['flange_class'].upper()}")
    print(f"plastic moment M_p: {r['plastic_moment_kip_in']:.0f} kip·in")
    print(
        f"§F3 nominal M_n   : {r['nominal_moment_kip_in']:.0f} kip·in "
        f"({r['reduction_percent']:.0f}% below M_p)"
    )
    print("  -> the noncompact flange buckles before full yield; §F3 interpolates the penalty")


if __name__ == "__main__":
    main()
