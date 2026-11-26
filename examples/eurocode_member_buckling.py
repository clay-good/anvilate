"""Worked example: the curve is the design decision, not the paperwork.

A Eurocode member check is a slenderness, a curve, and a reduction off that curve. The
slenderness comes from the geometry and the curve from a table — and the table is where the
engineering judgement sits, because the five curves are far apart.

**How far apart.** At a non-dimensional slenderness of 1.0, curve a₀ keeps **0.7253** of the
squash load and curve d keeps **0.4671** — curve a₀ is worth **55.3%** more capacity on the
same member. A curve chosen one row off is not a rounding.

**The worked column.** The report's HEB 340 on curve c at λ̄ = 0.75: Φ = 0.92, χ = **0.6935**,
and N_b,Rd = **4207.6 kN** against the cross-section's 6066.9 kN — buckling has taken
**30.6%** off. The report prints 4186.2 kN because it carries its rounded χ = 0.69 forward;
the gap is **0.51%** and all of it that rounding.

**The worked beam, twice.** The same IPE 400 on curve b at two very different critical
moments. At M_cr = 164.7 kNm the slenderness is **1.6784** and χ_LT is **0.2841**, giving
M_b,Rd = **131.8 kNm**; at M_cr = 1778.8 kNm it is **0.5107** and **0.8794**, giving
**408.0 kNm**. One is governed by buckling and the other barely at all, and nothing about
the section changed — only how far it is braced.

**The two methods disagree about the same steel.** A rolled I with h/b ≤ 2 takes curve a
under the general method of §6.3.2.2 and curve b under the alternative of §6.3.2.3. The
alternative method is the more generous of the two in its working range — this example
prints both at three slendernesses — but it carries a second cap, χ_LT ≤ 1/λ̄_LT², which the
general method has no equivalent of. At λ̄_LT = 2.0 that cap is what binds.

So which method a design uses has to be declared, and the output below shows the two giving
different curves from identical geometry.

Run it directly (``python examples/eurocode_member_buckling.py``);
:func:`eurocode_member_buckling` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.en1993_buckling import (
    EuropeanBucklingCurve,
    buckling_reduction_factor,
    curve_imperfection_factor,
    flexural_buckling_resistance,
    lateral_torsional_buckling_resistance,
    lateral_torsional_curve,
    lateral_torsional_reduction_rolled,
    lateral_torsional_slenderness,
)
from anvilate.analysis.en1993_resistance import compression_resistance
from anvilate.units import Quantity

Q = Quantity.parse

S355 = Q("355 MPa")
GAMMA_M1 = 1.0
#: The report's HEB 340 column.
COLUMN_AREA = Q("170.9 cm^2")
COLUMN_SLENDERNESS = 0.75
COLUMN_CURVE = EuropeanBucklingCurve.C
#: Its IPE 400 beam, worked at two critical moments.
BEAM_MODULUS = Q("1307e3 mm^3")
BEAM_CRITICAL_MOMENTS = (164.7, 1778.8)
#: A rolled I with h/b <= 2, where the two methods part company.
STOCKY = {"height": Q("300 mm"), "width": Q("300 mm"), "rolled": True}
#: The source's recommended National Annex values for the alternative method.
SLENDERNESS_LIMIT = 0.4
BETA = 0.75


def curve_spread() -> dict[str, float]:
    """What the five curves keep at a slenderness of 1.0."""
    kept = {
        curve.value: buckling_reduction_factor(slenderness=1.0, curve=curve)
        for curve in EuropeanBucklingCurve
    }
    return {**kept, "a0_over_d_percent": 100.0 * (kept["a0"] / kept["d"] - 1.0)}


def column() -> dict[str, float]:
    """The worked HEB 340: its cross-section resistance, and what buckling leaves."""
    cross_section = compression_resistance(
        area=COLUMN_AREA, yield_strength=S355, partial_factor_m0=1.0
    )
    chi = buckling_reduction_factor(slenderness=COLUMN_SLENDERNESS, curve=COLUMN_CURVE)
    buckling = flexural_buckling_resistance(
        area=COLUMN_AREA,
        yield_strength=S355,
        partial_factor_m1=GAMMA_M1,
        slenderness=COLUMN_SLENDERNESS,
        curve=COLUMN_CURVE,
    )
    alpha = curve_imperfection_factor(COLUMN_CURVE)
    return {
        "cross_section_kn": cross_section.to("kN").magnitude,
        "phi": 0.5 * (1 + alpha * (COLUMN_SLENDERNESS - 0.2) + COLUMN_SLENDERNESS**2),
        "chi": chi,
        "buckling_kn": buckling.to("kN").magnitude,
        "taken_off_percent": 100.0
        * (1.0 - buckling.to("kN").magnitude / cross_section.to("kN").magnitude),
        "rounding_gap_percent": 100.0 * (buckling.to("kN").magnitude / 4186.2 - 1.0),
    }


def beam_cases() -> list[dict[str, float]]:
    """The IPE 400 at both critical moments, on curve b."""
    out = []
    for critical in BEAM_CRITICAL_MOMENTS:
        slenderness = lateral_torsional_slenderness(
            section_modulus=BEAM_MODULUS,
            yield_strength=S355,
            critical_moment=Quantity(magnitude=critical, unit="kN*m"),
        )
        chi = buckling_reduction_factor(slenderness=slenderness, curve=EuropeanBucklingCurve.B)
        resistance = lateral_torsional_buckling_resistance(
            section_modulus=BEAM_MODULUS,
            yield_strength=S355,
            partial_factor_m1=GAMMA_M1,
            reduction=chi,
        )
        out.append(
            {
                "critical_knm": critical,
                "slenderness": slenderness,
                "chi": chi,
                "resistance_knm": resistance.to("kN*m").magnitude,
            }
        )
    return out


def methods_disagree() -> dict[str, str]:
    """The same geometry, two methods, two curves."""
    return {
        "general": lateral_torsional_curve(**STOCKY).value,
        "alternative": lateral_torsional_curve(alternative_method=True, **STOCKY).value,
    }


def method_comparison() -> list[dict[str, float]]:
    """The general and alternative reductions across the range, on curve b each."""
    rows = []
    for slenderness in (0.6, 0.8, 1.0, 1.5, 2.0):
        general = buckling_reduction_factor(slenderness=slenderness, curve=EuropeanBucklingCurve.B)
        alternative = lateral_torsional_reduction_rolled(
            slenderness=slenderness,
            curve=EuropeanBucklingCurve.B,
            slenderness_limit=SLENDERNESS_LIMIT,
            beta=BETA,
        )
        rows.append(
            {
                "slenderness": slenderness,
                "general": general,
                "alternative": alternative,
                "second_cap": 1.0 / slenderness**2,
            }
        )
    return rows


def eurocode_member_buckling() -> dict[str, float]:
    """The figures this example's prose turns on."""
    spread = curve_spread()
    col = column()
    beams = beam_cases()
    return {
        "curve_a0_at_one": spread["a0"],
        "curve_d_at_one": spread["d"],
        "a0_over_d_percent": spread["a0_over_d_percent"],
        "column_cross_section_kn": col["cross_section_kn"],
        "column_phi": col["phi"],
        "column_chi": col["chi"],
        "column_buckling_kn": col["buckling_kn"],
        "column_taken_off_percent": col["taken_off_percent"],
        "column_rounding_gap_percent": col["rounding_gap_percent"],
        "beam_short_slenderness": beams[0]["slenderness"],
        "beam_short_chi": beams[0]["chi"],
        "beam_short_resistance_knm": beams[0]["resistance_knm"],
        "beam_long_slenderness": beams[1]["slenderness"],
        "beam_long_chi": beams[1]["chi"],
        "beam_long_resistance_knm": beams[1]["resistance_knm"],
    }


def main() -> None:
    print("--- the five curves at a slenderness of 1.0")
    for curve in EuropeanBucklingCurve:
        chi = buckling_reduction_factor(slenderness=1.0, curve=curve)
        print(f"  curve {curve.value:<2} (alpha {curve_imperfection_factor(curve):.2f}):"
              f" chi = {chi:.4f}")  # fmt: skip
    print()
    print("--- the worked HEB 340 column, curve c, slenderness 0.75")
    col = column()
    print(f"  cross-section N_c,Rd = {col['cross_section_kn']:.1f} kN")
    print(f"  Phi = {col['phi']:.4f}, chi = {col['chi']:.4f}"
          f" -> N_b,Rd = {col['buckling_kn']:.1f} kN")  # fmt: skip
    print(f"  buckling takes off {col['taken_off_percent']:.1f}%")
    print()
    print("--- the worked IPE 400 beam, curve b, at two critical moments")
    for case in beam_cases():
        print(f"  M_cr = {case['critical_knm']:>6.1f} kNm -> "
              f"lambda_LT = {case['slenderness']:.4f}, chi_LT = {case['chi']:.4f}, "
              f"M_b,Rd = {case['resistance_knm']:.1f} kNm")  # fmt: skip
    print()
    print("--- the same rolled I (h/b = 1.0), two methods")
    for method, curve in methods_disagree().items():
        print(f"  {method:<12} -> curve {curve}")
    print()
    print("--- general against alternative, curve b")
    for row in method_comparison():
        capped = row["alternative"] <= row["second_cap"] + 1e-12 and row["second_cap"] < 1.0
        binds = " (second cap binds)" if capped else ""
        print(f"  lambda_LT {row['slenderness']:.1f}: general {row['general']:.4f}, "
              f"alternative {row['alternative']:.4f}{binds}")  # fmt: skip
    print()
    for name, value in eurocode_member_buckling().items():
        print(f"{name}: {value:.6g}")


if __name__ == "__main__":
    main()
