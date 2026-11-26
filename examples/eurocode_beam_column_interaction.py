"""Worked example: a beam-column is governed by whichever axis you did not look at.

A member carrying compression and bending is not a column with a moment added. EN 1993-1-1
§6.3.3 couples the two through four interaction factors and writes **two** inequalities, one
per buckling axis — and the two worked members below are each governed by a different one.

**The same clause, two different answers.** The report's IPE 360 column closes at
**0.5669** about y and **0.8782** about z: it is governed about z, the weak axis, where the
axial term alone is already 0.1870. The RHS 200x150x8 closes at **0.9039** about y and
**0.7157** about z: governed about y, the other way round. Checking one inequality and
assuming the other follows gets the first member wrong by a third of its margin.

**k_yy's bound is a ceiling and k_zy's is a floor.** This is the one real trap in Method 2,
because the two expressions look alike on the page. On the IPE 360 the unbounded k_zy is
**0.9646** and its floor is **0.9660** — the floor is **0.141%** higher, so the floor wins.
Read as a ceiling it would give 0.9646, and the second inequality would come out
**0.8773** instead of 0.8782: understated by **0.111%**, far too small to look wrong. The
table this example prints sweeps both bounds across slenderness: they coincide at λ̄ = 1.0,
and past it the cap binds k_yy from above while the floor holds k_zy up from below.

**C_my sits on its floor more often than you would think.** The RHS has ψ = −0.50, so
0.60 + 0.4ψ is exactly **0.40**, which is the floor Table B.3 puts under it. Every ψ below
−0.5 — every member in double curvature — returns that same 0.40. The floor is not a corner
case; it is most of the double-curvature range.

**And k_zy = 0 is an allowance, not a simplification.** A rectangular hollow section in
compression and uniaxial major-axis bending may take it, which turns the second inequality
into a pure flexural-buckling check — the RHS's 0.7157 is exactly its axial term and the
67.5 kNm moment changes it by nothing. That is correct for *that* member, and returning zero
for any other one would delete a term from a safety check, so the allowance is a function
with both of its conditions checked rather than a bare constant.

**Which method is a declaration with no default.** Annex A (Method 1) and Annex B (Method 2)
are alternatives developed by different groups, and they disagree — on this same hollow
section the report finds Method 2 the less conservative. Only Method 2 is implemented here,
and asking for Method 1 refuses rather than returning Method 2's numbers under its name.

Run it directly (``python examples/eurocode_beam_column_interaction.py``);
:func:`eurocode_beam_column_interaction` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.en1993_classification import SectionClass
from anvilate.analysis.en1993_interaction import (
    InteractionMethod,
    TorsionalSusceptibility,
    axial_utilisation,
    beam_column_utilisations,
    equivalent_uniform_moment_factor,
    hollow_section_kzy_allowance,
    interaction_factor_kyy,
    interaction_factor_kzy,
)
from anvilate.units import Quantity

Q = Quantity.parse
_METHOD = InteractionMethod.METHOD_2
_CLASS = SectionClass.CLASS_1


def worked_column() -> dict[str, float]:
    """The report's IPE 360, susceptible to torsional deformation (Table B.2)."""
    axial, resistance, gamma = Q("280 kN"), Q("2581.9 kN"), 1.0
    n_y = axial_utilisation(axial_force=axial, reduction=0.90,
                            characteristic_axial_resistance=resistance,
                            partial_factor_m1=gamma)  # fmt: skip
    n_z = axial_utilisation(axial_force=axial, reduction=0.58,
                            characteristic_axial_resistance=resistance,
                            partial_factor_m1=gamma)  # fmt: skip
    c_my = equivalent_uniform_moment_factor(moment_ratio=0.0)
    c_mlt = equivalent_uniform_moment_factor(moment_ratio=0.5)
    k_yy = interaction_factor_kyy(moment_factor=c_my, slenderness=0.53, axial_term=n_y,
                                  section_class=_CLASS, method=_METHOD)  # fmt: skip
    k_zy = interaction_factor_kzy(moment_factor_lt=c_mlt, slenderness=1.04, axial_term=n_z,
                                  section_class=_CLASS,
                                  susceptibility=TorsionalSusceptibility.SUSCEPTIBLE,
                                  method=_METHOD)  # fmt: skip
    about_y, about_z = beam_column_utilisations(
        axial_term_y=n_y, axial_term_z=n_z, major_moment=Q("220 kN*m"),
        characteristic_major_moment=Q("361.7 kN*m"), lateral_torsional_reduction=0.85,
        partial_factor_m1=gamma, factor_kyy=k_yy, factor_kzy=k_zy)  # fmt: skip
    divisor = c_mlt - 0.25
    return {
        "c_my": c_my, "c_mlt": c_mlt, "n_y": n_y, "n_z": n_z,
        "k_yy": k_yy, "k_yy_cap": c_my * (1.0 + 0.8 * n_y),
        "k_zy": k_zy,
        "k_zy_unbounded": 1.0 - (0.1 * 1.04) / divisor * n_z,
        "k_zy_floor": 1.0 - 0.1 / divisor * n_z,
        "about_y": about_y, "about_z": about_z,
        "axial_alone_z": n_z,
    }  # fmt: skip


def worked_hollow_section() -> dict[str, float]:
    """The report's RHS 200x150x8, not susceptible — and k_zy may be taken as zero."""
    axial, resistance, gamma = Q("965 kN"), Q("1872.6 kN"), 1.0
    n_y = axial_utilisation(axial_force=axial, reduction=0.83,
                            characteristic_axial_resistance=resistance,
                            partial_factor_m1=gamma)  # fmt: skip
    n_z = axial_utilisation(axial_force=axial, reduction=0.72,
                            characteristic_axial_resistance=resistance,
                            partial_factor_m1=gamma)  # fmt: skip
    c_my = equivalent_uniform_moment_factor(moment_ratio=-0.50)
    k_yy = interaction_factor_kyy(moment_factor=c_my, slenderness=0.74, axial_term=n_y,
                                  section_class=_CLASS, method=_METHOD)  # fmt: skip
    k_zy = hollow_section_kzy_allowance(
        susceptibility=TorsionalSusceptibility.NOT_SUSCEPTIBLE, method=_METHOD
    )
    about_y, about_z = beam_column_utilisations(
        axial_term_y=n_y, axial_term_z=n_z, major_moment=Q("67.5 kN*m"),
        characteristic_major_moment=Q("127.4 kN*m"), lateral_torsional_reduction=1.0,
        partial_factor_m1=gamma, factor_kyy=k_yy, factor_kzy=k_zy)  # fmt: skip
    return {"c_my": c_my, "k_yy": k_yy, "k_yy_cap": c_my * (1.0 + 0.8 * n_y),
            "k_zy": k_zy, "about_y": about_y, "about_z": about_z}  # fmt: skip


def which_bound_governs() -> list[dict[str, float]]:
    """k_yy's cap and k_zy's floor across slenderness, which is where the trap lives."""
    c_my = c_mlt = 0.80
    n = 0.35
    rows = []
    for slenderness in (0.5, 0.8, 1.0, 1.5, 2.0):
        k_yy = interaction_factor_kyy(moment_factor=c_my, slenderness=slenderness,
                                      axial_term=n, section_class=_CLASS,
                                      method=_METHOD)  # fmt: skip
        k_zy = interaction_factor_kzy(moment_factor_lt=c_mlt, slenderness=slenderness,
                                      axial_term=n, section_class=_CLASS,
                                      susceptibility=TorsionalSusceptibility.SUSCEPTIBLE,
                                      method=_METHOD)  # fmt: skip
        rows.append({
            "slenderness": slenderness,
            "k_yy": k_yy, "k_yy_line": c_my * (1.0 + (slenderness - 0.2) * n),
            "k_yy_cap": c_my * (1.0 + 0.8 * n),
            "k_zy": k_zy,
            "k_zy_line": 1.0 - (0.1 * slenderness) / (c_mlt - 0.25) * n,
            "k_zy_floor": 1.0 - 0.1 / (c_mlt - 0.25) * n,
        })  # fmt: skip
    return rows


def eurocode_beam_column_interaction() -> dict[str, float]:
    """The figures this example's text quotes."""
    column, hollow = worked_column(), worked_hollow_section()
    # The moment term of each inequality, recovered from the result rather than rebuilt.
    column_moment_term = (column["about_z"] - column["n_z"]) / column["k_zy"]
    read_as_ceiling = column["n_z"] + column["k_zy_unbounded"] * column_moment_term
    return {
        "column_about_y": column["about_y"],
        "column_about_z": column["about_z"],
        "column_k_yy": column["k_yy"],
        "column_k_zy": column["k_zy"],
        "column_k_zy_unbounded": column["k_zy_unbounded"],
        "column_floor_above_line_percent": 100.0
        * (column["k_zy_floor"] / column["k_zy_unbounded"] - 1.0),
        "column_z_if_bound_read_as_ceiling": read_as_ceiling,
        "column_z_understated_percent": 100.0 * (1.0 - read_as_ceiling / column["about_z"]),
        "hollow_about_y": hollow["about_y"],
        "hollow_about_z": hollow["about_z"],
    }


def main() -> None:
    print("--- the worked IPE 360 column, susceptible (Table B.2)")
    col = worked_column()
    print(f"  C_my {col['c_my']:.2f}  C_mLT {col['c_mlt']:.2f}")
    print(f"  n_y {col['n_y']:.4f}  n_z {col['n_z']:.4f}")
    print(f"  k_yy {col['k_yy']:.4f}  (cap {col['k_yy_cap']:.4f}, a CEILING)")
    print(f"  k_zy {col['k_zy']:.4f}  (line {col['k_zy_unbounded']:.4f}, "
          f"floor {col['k_zy_floor']:.4f}, a FLOOR)")  # fmt: skip
    print(f"  eq 6.61 {col['about_y']:.4f}   eq 6.62 {col['about_z']:.4f}")
    print()
    print("--- the worked RHS 200x150x8, not susceptible (Table B.1)")
    rhs = worked_hollow_section()
    print(f"  C_my {rhs['c_my']:.2f} (on its 0.40 floor)")
    print(f"  k_yy {rhs['k_yy']:.4f}  (cap {rhs['k_yy_cap']:.4f})")
    print(f"  k_zy {rhs['k_zy']:.1f}  -> eq 6.62 is a pure flexural-buckling check")
    print(f"  eq 6.61 {rhs['about_y']:.4f}   eq 6.62 {rhs['about_z']:.4f}")
    print()
    print("--- which bound governs, at C_m = 0.80 and n = 0.35")
    for row in which_bound_governs():
        yy = "cap" if row["k_yy"] < row["k_yy_line"] - 1e-12 else "line"
        zy = "floor" if row["k_zy"] > row["k_zy_line"] + 1e-12 else "line"
        print(f"  lambda {row['slenderness']:.1f}: k_yy {row['k_yy']:.4f} ({yy:>5}), "
              f"k_zy {row['k_zy']:.4f} ({zy:>5})")  # fmt: skip
    print()
    for name, value in eurocode_beam_column_interaction().items():
        print(f"{name}: {value:.6g}")


if __name__ == "__main__":
    main()
