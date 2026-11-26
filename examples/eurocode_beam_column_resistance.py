"""Worked example: a Eurocode beam-column, from its class to its reduced moment.

Classification is not the answer, it is the branch. This carries the JRC report's worked
beam-column all the way through: classify the section, take the resistance its class
entitles it to, then reduce the bending resistance for the axial force that is already
there.

The section is the report's: A = 161.3 cm², W_pl,y = 2149·10³ mm³, b = 300 mm,
t_f = 20.5 mm, steel S355, γ_M0 = 1.00, carrying N_Ed = 1704 kN and M_y,Ed = 24.8 kNm.

**The chain.** Compression resistance N_pl,Rd comes out **5726.2 kN** and the section is
good for the axial force alone. Plastic bending resistance M_pl,y,Rd is **762.9 kNm**. But
N_Ed is **1704.0 kN** against the **1431.5 kN** that is a quarter of N_pl,Rd, so clause
6.2.9.1(4) does not excuse the reduction: with n = **0.2976** and a = **0.2374** the
available moment is M_N,y,Rd = **608.06 kNm**, a **20.3%** cut. The applied 24.8 kNm sits
far inside it, which is the honest answer — this member is governed by stability, not by its
cross-section.

**Where the report and this disagree, and why.** The report prints 606.9 kNm. It rounds n
to 0.30 and a to 0.24 and carries those forward; unrounded they are 0.2976 and 0.2374, worth
**1.21 kNm**. Fed the report's own rounded figures this module reproduces 606.9 exactly, and
the example prints both so the difference is visible rather than a mystery.

**The cap that is easy to miss.** Clause 6.2.9.1(5) caps a at 0.5. The report's second
beam-column has an area ratio of **0.5450**, and using it uncapped gives a *larger* moment
resistance than the clause allows — **84.04 kNm** against the capped **81.52 kNm**, which is
**3.1%** of unearned capacity. The cap is the branch to get right, and the example shows both
numbers.

**And the class decides the modulus.** A class 3 section bends on W_el,min, not W_pl, and
asking this module for a class 3 resistance while handing it W_pl is refused rather than
answered — the last lines of the output are that refusal in its own words.

Run it directly (``python examples/eurocode_beam_column_resistance.py``);
:func:`eurocode_beam_column_resistance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.en1993_classification import SectionClass
from anvilate.analysis.en1993_resistance import (
    axial_reduction_negligible,
    bending_resistance,
    compression_resistance,
    reduced_plastic_moment_major,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

Q = Quantity.parse

#: The report's worked beam-column.
AREA = Q("161.3 cm^2")
PLASTIC_MODULUS = Q("2149e3 mm^3")
FLANGE_WIDTH_CM = 30.0
FLANGE_THICKNESS_CM = 2.05
AXIAL = Q("1704 kN")
MOMENT = Q("24.8 kN*m")
S355 = Q("355 MPa")
GAMMA_M0 = 1.0

#: Its second beam-column, whose area ratio is over the cap.
SECOND_AREA_CM2 = 52.75
SECOND_WIDTH_CM = 15.0
SECOND_THICKNESS_CM = 0.8
SECOND_PLASTIC_MODULUS = Q("358.8e3 mm^3")
SECOND_AXIAL_RATIO = 0.52  # the report's own rounded n


def plastic_axial() -> Quantity:
    """N_pl,Rd of the worked section."""
    return compression_resistance(area=AREA, yield_strength=S355, partial_factor_m0=GAMMA_M0)


def plastic_moment() -> Quantity:
    """M_pl,y,Rd, which a class 1 section is entitled to."""
    return bending_resistance(
        section_class=SectionClass.CLASS_1,
        yield_strength=S355,
        partial_factor_m0=GAMMA_M0,
        plastic_modulus=PLASTIC_MODULUS,
    )


def area_ratio() -> float:
    """a = (A − 2·b·t_f)/A, before the clause's cap."""
    return (161.3 - 2 * FLANGE_WIDTH_CM * FLANGE_THICKNESS_CM) / 161.3


def reduced_moment() -> Quantity:
    """M_N,y,Rd from the section's own unrounded figures."""
    return reduced_plastic_moment_major(
        plastic_moment=plastic_moment(),
        axial_force=AXIAL,
        plastic_axial_resistance=plastic_axial(),
        area_ratio=area_ratio(),
    )


def reduced_moment_on_the_reports_rounding() -> Quantity:
    """The same, fed the n = 0.30 and a = 0.24 the report carries forward."""
    rounded_axial = Quantity(magnitude=0.30 * plastic_axial().to("kN").magnitude, unit="kN")
    return reduced_plastic_moment_major(
        plastic_moment=Q("762.9 kN*m"),
        axial_force=rounded_axial,
        plastic_axial_resistance=plastic_axial(),
        area_ratio=0.24,
    )


def second_column_cap() -> dict[str, float]:
    """The second beam-column, capped and uncapped, in kNm."""
    axial_resistance = compression_resistance(
        area=Quantity(magnitude=SECOND_AREA_CM2, unit="cm^2"),
        yield_strength=S355,
        partial_factor_m0=GAMMA_M0,
    )
    moment = bending_resistance(
        section_class=SectionClass.CLASS_1,
        yield_strength=S355,
        partial_factor_m0=GAMMA_M0,
        plastic_modulus=SECOND_PLASTIC_MODULUS,
    )
    raw = (SECOND_AREA_CM2 - 2 * SECOND_WIDTH_CM * SECOND_THICKNESS_CM) / SECOND_AREA_CM2
    applied = Quantity(
        magnitude=SECOND_AXIAL_RATIO * axial_resistance.to("kN").magnitude, unit="kN"
    )
    capped = reduced_plastic_moment_major(
        plastic_moment=moment,
        axial_force=applied,
        plastic_axial_resistance=axial_resistance,
        area_ratio=raw,
    )
    uncapped = moment.to("kN*m").magnitude * (1 - SECOND_AXIAL_RATIO) / (1 - 0.5 * raw)
    return {
        "raw_ratio": raw,
        "capped_knm": capped.to("kN*m").magnitude,
        "uncapped_knm": uncapped,
        "unearned_percent": 100.0 * (uncapped / capped.to("kN*m").magnitude - 1.0),
    }


def class_three_refusal() -> str:
    """What asking for a class 3 resistance with W_pl gets."""
    try:
        bending_resistance(
            section_class=SectionClass.CLASS_3,
            yield_strength=S355,
            partial_factor_m0=GAMMA_M0,
            plastic_modulus=PLASTIC_MODULUS,
        )
    except RefusalError as refused:
        return str(refused)
    raise AssertionError("a class 3 section must not bend on W_pl")


def eurocode_beam_column_resistance() -> dict[str, float]:
    """The figures this example's prose turns on."""
    npl = plastic_axial().to("kN").magnitude
    mpl = plastic_moment().to("kN*m").magnitude
    mn = reduced_moment().to("kN*m").magnitude
    second = second_column_cap()
    return {
        "plastic_axial_kn": npl,
        "quarter_of_it_kn": 0.25 * npl,
        "applied_axial_kn": AXIAL.to("kN").magnitude,
        "plastic_moment_knm": mpl,
        "axial_ratio_n": AXIAL.to("kN").magnitude / npl,
        "area_ratio_a": area_ratio(),
        "reduced_moment_knm": mn,
        "reduction_percent": 100.0 * (1.0 - mn / mpl),
        "on_the_reports_rounding_knm": reduced_moment_on_the_reports_rounding()
        .to("kN*m")
        .magnitude,
        "rounding_gap_knm": mn - reduced_moment_on_the_reports_rounding().to("kN*m").magnitude,
        "second_raw_ratio": second["raw_ratio"],
        "second_capped_knm": second["capped_knm"],
        "second_uncapped_knm": second["uncapped_knm"],
        "second_unearned_percent": second["unearned_percent"],
    }


def main() -> None:
    npl, mpl = plastic_axial(), plastic_moment()
    print("--- the worked beam-column, S355, gamma_M0 = 1.00")
    print(f"  N_pl,Rd   = {npl.to('kN').magnitude:.1f} kN"
          f"   (applied {AXIAL.to('kN').magnitude:.1f} kN)")  # fmt: skip
    print(f"  M_pl,y,Rd = {mpl.to('kN*m').magnitude:.1f} kNm"
          f"  (applied {MOMENT.to('kN*m').magnitude:.1f} kNm)")  # fmt: skip
    print()
    print("--- does the axial force reduce the moment resistance?")
    negligible = axial_reduction_negligible(axial_force=AXIAL, plastic_axial_resistance=npl)
    quarter = 0.25 * npl.to("kN").magnitude
    print(f"  clause 6.2.9.1(4): a quarter of N_pl,Rd is {quarter:.1f} kN")
    print(f"  applied {AXIAL.to('kN').magnitude:.1f} kN -> negligible: {negligible}")
    print()
    print("--- the reduction")
    mn = reduced_moment()
    print(f"  n = {AXIAL.to('kN').magnitude / npl.to('kN').magnitude:.4f}, "
          f"a = {area_ratio():.4f}")  # fmt: skip
    print(f"  M_N,y,Rd = {mn.to('kN*m').magnitude:.2f} kNm")
    rounded = reduced_moment_on_the_reports_rounding()
    print(f"  on the report's rounded n = 0.30 and a = 0.24: "
          f"{rounded.to('kN*m').magnitude:.2f} kNm")  # fmt: skip
    print()
    print("--- the second beam-column, where the area ratio is over the cap")
    second = second_column_cap()
    print(f"  a = {second['raw_ratio']:.4f} -> capped at 0.5")
    print(f"  capped   M_N,y,Rd = {second['capped_knm']:.2f} kNm")
    print(f"  uncapped          = {second['uncapped_knm']:.2f} kNm  (not the clause's)")
    print()
    print("--- and what a class 3 section is told")
    print(f"  {class_three_refusal()}")
    print()
    for name, value in eurocode_beam_column_resistance().items():
        print(f"{name}: {value:.6g}")


if __name__ == "__main__":
    main()
