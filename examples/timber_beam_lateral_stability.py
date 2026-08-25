"""Worked example: the rafter that passes on bending stress and buckles sideways.

A 2x12 Douglas Fir-Larch rafter, 16 ft span, carrying a snow load. Checked on bending
stress alone it has 42% in hand. Then the lateral bracing question: a 2x12 is 7.5 times
deeper than it is wide, and with the compression edge held only at the supports the
NDS §3.3.3 beam stability factor C_L cuts the adjusted bending value to 40% of itself.
The same rafter fails at 0.57.

**One strut at midspan is not enough.** It takes C_L from 0.402 to 0.683 and the check
from 0.57 to 0.97 — still short. Bracing at the third points takes it to 0.834 and the
rafter passes at 1.18. That gradient is the point: C_L is not a small conservatism to be
skipped, it is what decides how much blocking the roof needs.

Two ways the factor gets away from you, both shown:

1. **F_bE uses 1.20, not the column formula's 0.822.** The two have the same shape and
   the same symbols. Using the column's coefficient here understates the buckling stress
   by a third and drags C_L down with it — conservative, but wrong in a way that reads as
   a design decision, and the same confusion in the other direction is not conservative
   at all.
2. **C_L takes F_b*, not F'_b.** F_b* is the reference value with every adjustment
   *except* C_L. Handing it the fully adjusted number — the one a design summary reports
   — returns 0.830 on the unbraced rafter, against the 0.402 it actually has. More than
   double, in the unconservative direction, and nothing about the number looks wrong.

Run it directly (``python examples/timber_beam_lateral_stability.py``);
:func:`stability_factor`, :func:`screen` and :func:`bracing_study` are exercised in the
test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    nds_adjusted_design_value,
    nds_beam_slenderness_ratio,
    nds_beam_stability_factor,
    nds_bending_buckling_stress,
    nds_bending_scorecard,
)
from anvilate.scorecard import ScorecardEntry
from anvilate.units import Quantity

# A 2x12 DF-L No. 2 rafter: 1.5 in x 11.25 in, 16 ft simple span, ~67 plf of snow.
BREADTH = Quantity.parse("1.5 in")
DEPTH = Quantity.parse("11.25 in")
SPAN = Quantity.parse("16 ft")
# Reference values are the caller's, from the NDS Supplement. F_b* is F_b with every
# adjustment applied except C_L — here C_D = 1.15 for snow on an F_b of 1000 psi.
F_B_STAR = Quantity.parse("1150 psi")
E_MIN = Quantity.parse("690000 psi")
APPLIED_BENDING = Quantity.parse("810 psi")
REQUIRED_SF = 1.0

# NDS Table 3.3.3 converts an unbraced length into an effective length. For a uniformly
# loaded single-span beam at l_u/d >= 7 that is l_e = 1.63*l_u + 3*d. The conversion is
# the caller's: it depends on the loading pattern and on how the compression edge is
# held, and a section knows neither.
_TABLE_333_UNIFORM = (1.63, 3.0)


def effective_length(unbraced_length: Quantity) -> Quantity:
    """NDS Table 3.3.3's l_e for a uniformly loaded single-span beam."""
    a, b = _TABLE_333_UNIFORM
    return Quantity(
        magnitude=a * unbraced_length.to("in").magnitude + b * DEPTH.to("in").magnitude,
        unit="in",
    )


def stability_factor(unbraced_length: Quantity) -> float:
    """C_L for a compression edge held every ``unbraced_length``."""
    r_b = nds_beam_slenderness_ratio(
        effective_length=effective_length(unbraced_length), depth=DEPTH, breadth=BREADTH
    )
    f_be = nds_bending_buckling_stress(min_modulus=E_MIN, slenderness_ratio=r_b)
    return nds_beam_stability_factor(buckling_stress=f_be, reference_bending_value=F_B_STAR)


def screen(name: str, c_l: float | None) -> ScorecardEntry:
    """The bending check with ``c_l`` in the chain, or with no stability factor at all."""
    factors = {} if c_l is None else {"C_L": c_l}
    adjusted = nds_adjusted_design_value(reference_value=F_B_STAR, factors=factors)
    return nds_bending_scorecard(
        name,
        bending_stress=APPLIED_BENDING,
        adjusted_bending_value=adjusted,
        required=REQUIRED_SF,
    )


def bracing_study() -> list[tuple[str, float, ScorecardEntry]]:
    """The same rafter at three bracing intervals, plus the check that skips C_L."""
    out: list[tuple[str, float, ScorecardEntry]] = []
    for label, unbraced in (
        ("supports only", Quantity.parse("16 ft")),
        ("one strut at midspan", Quantity.parse("8 ft")),
        ("struts at the third points", Quantity.parse("5.333 ft")),
    ):
        c_l = stability_factor(unbraced)
        out.append((label, c_l, screen(f"bending, {label}", c_l)))
    return out


def main() -> None:
    print("2x12 DF-L rafter, 16 ft span, ~67 plf snow")
    print(f"  {screen('bending (C_L skipped)', None)}")
    print()
    for label, c_l, entry in bracing_study():
        print(f"  C_L {c_l:.3f}  {label}")
        print(f"      {entry}")

    full = stability_factor(SPAN)
    overstated = nds_beam_stability_factor(
        buckling_stress=nds_bending_buckling_stress(
            min_modulus=E_MIN,
            slenderness_ratio=nds_beam_slenderness_ratio(
                effective_length=effective_length(SPAN), depth=DEPTH, breadth=BREADTH
            ),
        ),
        reference_bending_value=Quantity(magnitude=F_B_STAR.to("psi").magnitude * full, unit="psi"),
    )
    print(f"\n  C_L given F'_b instead of F_b*: {overstated:.3f} against the correct {full:.3f}")
    print("  — larger than the rafter has, which is the unconservative direction")


if __name__ == "__main__":
    main()
