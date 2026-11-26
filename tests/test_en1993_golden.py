"""Every published figure the Eurocode 3 pack reproduces, in one table.

The three module test files each replay the worked examples their own clauses turn on, with
the narrative that makes each one worth reading. This file is the **index**: one row per
published figure, naming its source section, the value the source prints, and the precision
it prints it to. A reviewer asking "what is this pack actually anchored on?" reads this
table and nothing else.

The rows are deliberately a duplicate of assertions made elsewhere. They serve a different
purpose — the per-module tests say *why* a figure matters, and this says *how many* there
are and *where they came from*, which is the question a reader of the pack's claims asks.
A gate at the bottom holds the corpus to covering all three modules, so a module added
without an anchor cannot pass quietly.

Source throughout: *Eurocodes: Background and Applications — Design of Steel Buildings*
(European Commission, Joint Research Centre; Simões da Silva and Simões), the public
document EN 1993-1-1 itself could not be read from. Its own section numbers are given.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import sqrt

import pytest

from anvilate.analysis.en1993_buckling import (
    EuropeanBucklingCurve,
    buckling_reduction_factor,
    lateral_torsional_buckling_resistance,
    lateral_torsional_curve,
    lateral_torsional_slenderness,
    reference_slenderness,
)
from anvilate.analysis.en1993_classification import (
    PartStress,
    SectionClass,
    en1993_epsilon,
    rolled_i_section_class,
)
from anvilate.analysis.en1993_resistance import (
    bending_resistance,
    compression_resistance,
    reduced_plastic_moment_major,
)
from anvilate.units import Quantity

Q = Quantity.parse

_S355 = Q("355 MPa")
_M = 1.0  # the report's partial factors throughout its worked examples

#: The two sections the report works, as (h, b, t_w, t_f, r) in millimetres.
_HEB_340 = (340.0, 300.0, 12.0, 21.5, 27.0)
_IPE_400 = (400.0, 180.0, 8.6, 13.5, 21.0)


@dataclass(frozen=True)
class Worked:
    """One figure a published worked example prints, and how this pack reaches it."""

    section: str
    quantity: str
    published: float
    #: How many decimal places the source prints this figure to; None if it is exact.
    decimals: int | None
    compute: Callable[[], float]
    module: str

    @property
    def rounding(self) -> float:
        """The tolerance, derived from the printed precision rather than chosen.

        A band cannot be widened here without changing the claim about what the source
        prints, which `test_the_tolerance_is_the_sources_own_precision` then rejects.
        """
        if self.decimals is None:
            return 0.0
        return 0.5 * 10.0**-self.decimals


def _heb_340_classes() -> tuple[SectionClass, SectionClass, SectionClass]:
    h, b, tw, tf, r = _HEB_340
    return rolled_i_section_class(
        height=Q(f"{h} mm"),
        width=Q(f"{b} mm"),
        web_thickness=Q(f"{tw} mm"),
        flange_thickness=Q(f"{tf} mm"),
        root_radius=Q(f"{r} mm"),
        yield_strength=_S355,
        stress=PartStress.COMPRESSION,
    )


def _ipe_400_classes() -> tuple[SectionClass, SectionClass, SectionClass]:
    h, b, tw, tf, r = _IPE_400
    return rolled_i_section_class(
        height=Q(f"{h} mm"),
        width=Q(f"{b} mm"),
        web_thickness=Q(f"{tw} mm"),
        flange_thickness=Q(f"{tf} mm"),
        root_radius=Q(f"{r} mm"),
        yield_strength=_S355,
        stress=PartStress.BENDING,
    )


def _plastic_axial(area_cm2: float) -> float:
    return (
        compression_resistance(
            area=Quantity(magnitude=area_cm2, unit="cm^2"),
            yield_strength=_S355,
            partial_factor_m0=_M,
        )
        .to("kN")
        .magnitude
    )


def _plastic_moment(modulus_mm3: float) -> float:
    return (
        bending_resistance(
            section_class=SectionClass.CLASS_1,
            yield_strength=_S355,
            partial_factor_m0=_M,
            plastic_modulus=Quantity(magnitude=modulus_mm3, unit="mm^3"),
        )
        .to("kN*m")
        .magnitude
    )


def _reduced_major(moment_knm: float, ratio_n: float, area_ratio: float) -> float:
    """M_N,y,Rd on the report's own rounded n and a, which is how it prints its answer."""
    plastic_axial = Q("1000 kN")
    return (
        reduced_plastic_moment_major(
            plastic_moment=Quantity(magnitude=moment_knm, unit="kN*m"),
            axial_force=Quantity(magnitude=ratio_n * 1000.0, unit="kN"),
            plastic_axial_resistance=plastic_axial,
            area_ratio=area_ratio,
        )
        .to("kN*m")
        .magnitude
    )


def _ltb(critical_knm: float) -> tuple[float, float, float]:
    """λ_LT, χ_LT and M_b,Rd for the report's IPE 400 on curve b."""
    modulus = Q("1307e3 mm^3")
    slenderness = lateral_torsional_slenderness(
        section_modulus=modulus,
        yield_strength=_S355,
        critical_moment=Quantity(magnitude=critical_knm, unit="kN*m"),
    )
    reduction = buckling_reduction_factor(slenderness=slenderness, curve=EuropeanBucklingCurve.B)
    resistance = (
        lateral_torsional_buckling_resistance(
            section_modulus=modulus,
            yield_strength=_S355,
            partial_factor_m1=_M,
            reduction=reduction,
        )
        .to("kN*m")
        .magnitude
    )
    return slenderness, reduction, resistance


_CLASSIFICATION = "en1993_classification"
_RESISTANCE = "en1993_resistance"
_BUCKLING = "en1993_buckling"

#: Every published figure, with the section it is printed in.
WORKED_EXAMPLES: tuple[Worked, ...] = (
    # --- Table 5.2's own tabulation of the material factor (§1.2.2.4) ----------------
    *(
        Worked(
            section="§1.2.2.4 Table 1.1",
            quantity=f"epsilon at S{grade}",
            published=value,
            decimals=2,
            compute=lambda g=grade: en1993_epsilon(
                yield_strength=Quantity(magnitude=g, unit="MPa")
            ),
            module=_CLASSIFICATION,
        )
        for grade, value in ((235, 1.00), (275, 0.92), (355, 0.81), (420, 0.75), (460, 0.71))
    ),
    *(
        Worked(
            section="§1.2.2.4 Table 1.3",
            quantity=f"epsilon squared at S{grade}",
            published=value,
            decimals=2,
            compute=lambda g=grade: (
                en1993_epsilon(yield_strength=Quantity(magnitude=g, unit="MPa")) ** 2
            ),
            module=_CLASSIFICATION,
        )
        for grade, value in ((235, 1.00), (275, 0.85), (355, 0.66), (420, 0.56), (460, 0.51))
    ),
    # --- the two worked classifications (§1.3.3.2, §1.3.4.2) -------------------------
    Worked(
        section="§1.3.3.2",
        quantity="HEB 340 web c/t in compression",
        published=20.25,
        decimals=2,
        compute=lambda: (340 - 2 * 21.5 - 2 * 27) / 12,
        module=_CLASSIFICATION,
    ),
    Worked(
        section="§1.3.3.2",
        quantity="HEB 340 flange c/t in compression",
        published=5.44,
        decimals=2,
        compute=lambda: ((300 - 12) / 2 - 27) / 21.5,
        module=_CLASSIFICATION,
    ),
    Worked(
        section="§1.3.3.2",
        quantity="HEB 340 section class in compression",
        published=1.0,
        decimals=None,
        compute=lambda: float(int(_heb_340_classes()[0])),
        module=_CLASSIFICATION,
    ),
    Worked(
        section="§1.3.4.2",
        quantity="IPE 400 web flat width in bending (mm)",
        published=331.0,
        decimals=0,
        compute=lambda: float(400 - 2 * 13.5 - 2 * 21),
        module=_CLASSIFICATION,
    ),
    Worked(
        section="§1.3.4.2",
        quantity="IPE 400 web c/t in bending",
        published=38.49,
        decimals=2,
        compute=lambda: (400 - 2 * 13.5 - 2 * 21) / 8.6,
        module=_CLASSIFICATION,
    ),
    Worked(
        section="§1.3.4.2",
        quantity="IPE 400 flange c/t in bending",
        published=4.79,
        decimals=2,
        compute=lambda: ((180 - 8.6) / 2 - 21) / 13.5,
        module=_CLASSIFICATION,
    ),
    Worked(
        section="§1.3.4.2",
        quantity="IPE 400 section class in bending",
        published=1.0,
        decimals=None,
        compute=lambda: float(int(_ipe_400_classes()[0])),
        module=_CLASSIFICATION,
    ),
    # --- §6.2 resistances (§1.3.3.2, §1.3.5.2) ---------------------------------------
    Worked(
        section="§1.3.3.2",
        quantity="HEB 340 N_c,Rd (kN)",
        published=6067.0,
        decimals=1,
        compute=lambda: _plastic_axial(170.9),
        module=_RESISTANCE,
    ),
    Worked(
        section="§1.3.5.2",
        quantity="beam-column N_pl,Rd (kN)",
        published=5726.2,
        decimals=1,
        compute=lambda: _plastic_axial(161.3),
        module=_RESISTANCE,
    ),
    Worked(
        section="§1.3.5.2",
        quantity="beam-column M_pl,y,Rd (kNm)",
        published=762.9,
        decimals=1,
        compute=lambda: _plastic_moment(2149e3),
        module=_RESISTANCE,
    ),
    Worked(
        section="§1.3.5.2",
        quantity="beam-column area ratio a",
        published=0.24,
        decimals=2,
        compute=lambda: (161.3 - 2 * 30 * 2.05) / 161.3,
        module=_RESISTANCE,
    ),
    Worked(
        section="§1.3.5.2",
        quantity="beam-column M_N,y,Rd on its own rounded n and a (kNm)",
        published=606.9,
        decimals=1,
        compute=lambda: _reduced_major(762.9, 0.30, 0.24),
        module=_RESISTANCE,
    ),
    Worked(
        section="§1.3.5.2 example 6",
        quantity="second column N_pl,Rd (kN)",
        published=1872.6,
        decimals=1,
        compute=lambda: _plastic_axial(52.75),
        module=_RESISTANCE,
    ),
    Worked(
        section="§1.3.5.2 example 6",
        quantity="second column M_pl,y,Rd (kNm)",
        published=127.4,
        decimals=1,
        compute=lambda: _plastic_moment(358.8e3),
        module=_RESISTANCE,
    ),
    Worked(
        section="§1.3.5.2 example 6",
        quantity="second column area ratio before the 0,5 cap",
        published=0.55,
        decimals=2,
        compute=lambda: (52.75 - 2 * 15 * 0.8) / 52.75,
        module=_RESISTANCE,
    ),
    Worked(
        section="§1.3.5.2 example 6",
        quantity="second column M_N,y,Rd with a capped at 0,5 (kNm)",
        published=81.5,
        decimals=1,
        compute=lambda: _reduced_major(127.4, 0.52, 0.55),
        module=_RESISTANCE,
    ),
    # --- §6.3 buckling (§1.3.3.1, §1.3.3.2, §1.3.4.2) --------------------------------
    Worked(
        section="§1.3.3.1",
        quantity="reference slenderness lambda_1 at S235",
        published=93.9,
        decimals=1,
        compute=lambda: reference_slenderness(
            elastic_modulus=Q("210 GPa"), yield_strength=Q("235 MPa")
        ),
        module=_BUCKLING,
    ),
    Worked(
        section="§1.3.3.2",
        quantity="HEB 340 chi on curve c at slenderness 0,75",
        published=0.69,
        decimals=2,
        compute=lambda: buckling_reduction_factor(slenderness=0.75, curve=EuropeanBucklingCurve.C),
        module=_BUCKLING,
    ),
    Worked(
        section="§1.3.3.2",
        quantity="HEB 340 N_b,Rd on the report's rounded chi (kN)",
        published=4186.2,
        decimals=1,
        compute=lambda: 0.69 * 170.9e2 * 355 / 1000,
        module=_BUCKLING,
    ),
    Worked(
        section="§1.3.4.2",
        quantity="IPE 400 lambda_LT at M_cr 164,7 kNm",
        published=1.68,
        decimals=2,
        compute=lambda: _ltb(164.7)[0],
        module=_BUCKLING,
    ),
    Worked(
        section="§1.3.4.2",
        quantity="IPE 400 chi_LT at M_cr 164,7 kNm",
        published=0.28,
        decimals=2,
        compute=lambda: _ltb(164.7)[1],
        module=_BUCKLING,
    ),
    Worked(
        section="§1.3.4.2",
        quantity="IPE 400 lambda_LT at M_cr 1778,8 kNm",
        published=0.51,
        decimals=2,
        compute=lambda: _ltb(1778.8)[0],
        module=_BUCKLING,
    ),
)


@pytest.mark.parametrize("worked", WORKED_EXAMPLES, ids=lambda w: f"{w.section} {w.quantity}")
def test_every_published_figure_is_reproduced(worked: Worked):
    """Each row against the value its source prints, to the precision it prints it."""
    computed = worked.compute()
    assert abs(computed - worked.published) <= worked.rounding * (1 + 1e-9), (
        f"{worked.section} prints {worked.quantity} as {worked.published} and this pack "
        f"computes {computed!r}"
    )


def test_the_corpus_covers_every_module_of_the_pack():
    """A module added without an anchor cannot pass quietly.

    The pack's claim is that it is read from a public document and checked against that
    document's own worked answers. A module with no row here has the first half and not the
    second.
    """
    covered = {worked.module for worked in WORKED_EXAMPLES}
    assert covered == {_CLASSIFICATION, _RESISTANCE, _BUCKLING}, sorted(covered)
    for module in covered:
        rows = [w for w in WORKED_EXAMPLES if w.module == module]
        assert len(rows) >= 5, (module, len(rows))


def test_the_corpus_is_an_index_and_not_a_rewording():
    """Every row names a section of the source, and no two rows claim the same figure."""
    assert len(WORKED_EXAMPLES) >= 20
    for worked in WORKED_EXAMPLES:
        assert worked.section.startswith("§") or "§" in worked.section, worked.quantity
        assert worked.quantity.strip()
        assert worked.rounding >= 0
    quantities = [w.quantity for w in WORKED_EXAMPLES]
    assert len(set(quantities)) == len(quantities), "two rows claim the same figure"


def test_the_tolerance_is_the_sources_own_precision():
    """A row that passed on a wide tolerance would be a test of nothing.

    This is the way a golden corpus quietly stops being one: a figure fails by a little, the
    band is widened a little, and the row goes on passing while proving less. So the band is
    not written down at all — it is derived from `decimals`, the number of places the source
    prints, and this asserts that the published value really is printed to that many. A row
    that claimed fewer places than it has, to buy room, is caught here: `round(0.24, 0)` is
    `0.0`, not `0.24`.

    A relative check would be the wrong instrument, and was the first thing tried: 0,24
    printed to two decimals carries a 2% band by arithmetic, not by looseness, and holding it
    to 1% would reject the source's own precision.
    """
    for worked in WORKED_EXAMPLES:
        if worked.decimals is None:
            assert worked.published == int(worked.published), worked.quantity
            assert worked.rounding == 0.0
            continue
        assert worked.decimals >= 0, worked.quantity
        assert round(worked.published, worked.decimals) == pytest.approx(
            worked.published, abs=0.0
        ), (
            f"{worked.quantity} claims {worked.decimals} decimals, which would buy it a "
            f"wider band than {worked.section} prints"
        )
        assert worked.rounding == 0.5 * 10.0**-worked.decimals


def test_a_widened_band_would_be_caught():
    """The premise of the test above, exercised rather than asserted.

    Claiming one fewer decimal doubles the band. Every row whose published value uses its
    last decimal must fail the printed-precision check under that claim, which is what makes
    the check an instrument and not a restatement.
    """
    widened = [
        w
        for w in WORKED_EXAMPLES
        if w.decimals and round(w.published, w.decimals - 1) != pytest.approx(w.published, abs=0.0)
    ]
    assert len(widened) >= 15, (
        "too few rows use their last printed decimal for this check to mean anything: "
        f"{len(widened)}"
    )
    for worked in widened:
        loosened = Worked(
            section=worked.section,
            quantity=worked.quantity,
            published=worked.published,
            decimals=worked.decimals - 1 if worked.decimals else 0,
            compute=worked.compute,
            module=worked.module,
        )
        assert loosened.rounding > worked.rounding


def test_the_two_lateral_torsional_curve_tables_are_anchored_too():
    """Not a number, so not a row above — but it is a published table and it is checked."""
    stocky = {"height": Q("300 mm"), "width": Q("300 mm"), "rolled": True}
    slender = {"height": Q("400 mm"), "width": Q("180 mm"), "rolled": True}
    assert lateral_torsional_curve(**stocky) is EuropeanBucklingCurve.A
    assert lateral_torsional_curve(**slender) is EuropeanBucklingCurve.B
    assert lateral_torsional_curve(alternative_method=True, **stocky) is EuropeanBucklingCurve.B
    assert lateral_torsional_curve(alternative_method=True, **slender) is EuropeanBucklingCurve.C
    # Welded, both methods, h/b > 2.
    welded = {"height": Q("400 mm"), "width": Q("180 mm"), "rolled": False}
    assert lateral_torsional_curve(**welded) is EuropeanBucklingCurve.D
    assert sqrt(4.0) == 2.0  # the h/b limit the tables turn on, as a number


def test_the_worked_chi_rows_cannot_pin_the_imperfection_table_by_themselves():
    """What this corpus does *not* prove, measured rather than claimed.

    A worked example prints χ to two decimals. Two decimals of χ cannot resolve the
    imperfection factor α to the two decimals the curve table publishes it to: shifting
    curve C's α from 0,49 to 0,50 leaves the printed 0,69 untouched, so a corpus of worked
    answers alone would accept a wrong table. Found by mutating the table and watching every
    row here go on passing.

    That is not a hole, because the table is pinned by value in
    `tests/test_en1993_buckling.py` — the five factors asserted directly against the
    published Table 6.1. The two tests do different jobs: that one says the constants are
    right, and this one says the chain built on them reaches the source's own answers. This
    test exists so the division is recorded where someone reading the corpus will see it,
    and so it stays true — if a future row *did* become sharp enough to pin α, the assertion
    below fails and the note needs rewriting.
    """
    from anvilate.analysis import en1993_buckling

    curve = EuropeanBucklingCurve.C
    published, band = 0.69, 0.005
    original = en1993_buckling._IMPERFECTION_FACTORS[curve]
    assert original == 0.49

    def leaves_the_band(alpha: float) -> bool:
        en1993_buckling._IMPERFECTION_FACTORS[curve] = alpha
        try:
            return abs(buckling_reduction_factor(slenderness=0.75, curve=curve) - published) > band
        finally:
            en1993_buckling._IMPERFECTION_FACTORS[curve] = original

    # A shift of the last place the table publishes, upward, is invisible to the worked row.
    assert not leaves_the_band(0.50), (
        "a worked χ row has become sharp enough to pin α; rewrite this test's note"
    )
    # Downward it is visible, because the computed value sits near the top of the band.
    # That asymmetry is exactly why a corpus of worked answers is not a test of a table.
    assert leaves_the_band(0.48)
    assert en1993_buckling._IMPERFECTION_FACTORS[curve] == original


def test_the_curve_table_is_pinned_somewhere_else():
    """The other half of the division above, asserted so it cannot quietly go away."""
    from anvilate.analysis.en1993_buckling import curve_imperfection_factor

    published = {
        EuropeanBucklingCurve.A0: 0.13,
        EuropeanBucklingCurve.A: 0.21,
        EuropeanBucklingCurve.B: 0.34,
        EuropeanBucklingCurve.C: 0.49,
        EuropeanBucklingCurve.D: 0.76,
    }
    for curve, alpha in published.items():
        assert curve_imperfection_factor(curve) == alpha, curve
    assert len(published) == len(EuropeanBucklingCurve), "a curve was added without a factor"


#: Which rows above reach their figure through this package, and which only check that the
#: source's own printed numbers are arithmetically consistent with each other. The second
#: kind is worth having — a misread figure is caught before it anchors anything — but it is
#: not evidence about the pack, and a corpus that blurred the two would overstate itself.
_SOURCE_ARITHMETIC_ONLY = frozenset(
    {
        "HEB 340 web c/t in compression",
        "HEB 340 flange c/t in compression",
        "IPE 400 web flat width in bending (mm)",
        "IPE 400 web c/t in bending",
        "IPE 400 flange c/t in bending",
        "beam-column area ratio a",
        "second column area ratio before the 0,5 cap",
        "HEB 340 N_b,Rd on the report's rounded chi (kN)",
    }
)


def test_the_corpus_says_which_rows_are_evidence_about_this_package():
    """Most rows call into the pack; eight do the source's arithmetic by hand.

    Those eight are figures the pack computes internally and does not return — the flat width
    of a web, the ratio c/t, the area ratio a. Their rows multiply the published dimensions
    out and compare, which checks that the report's own numbers agree with each other and
    says nothing about `rolled_i_section_class`. That is a real but much weaker claim, so it
    is named here rather than left to look like the rest.

    `test_the_packs_own_measurement_of_c_matches_the_published_ratios` is the strong version
    for the ratios that matter, reached by solving for the boundary instead of by reading a
    value the function does not expose.
    """
    quantities = {worked.quantity for worked in WORKED_EXAMPLES}
    unknown = sorted(_SOURCE_ARITHMETIC_ONLY - quantities)
    assert not unknown, f"these name no row: {unknown}"
    through_the_pack = quantities - _SOURCE_ARITHMETIC_ONLY
    assert len(through_the_pack) >= 20, (
        f"only {len(through_the_pack)} rows reach their figure through the package"
    )
    assert len(_SOURCE_ARITHMETIC_ONLY) == 8


@pytest.mark.parametrize(
    ("label", "section", "stress", "element", "ratio", "class_1_limit"),
    [
        # The limit multipliers are Table 5.2's own: 33ε for an internal part in uniform
        # compression, 9ε for an outstand flange, 72ε for an internal part in bending.
        ("HEB 340 web", _HEB_340, PartStress.COMPRESSION, 1, 20.25, 33.0),
        ("HEB 340 flange", _HEB_340, PartStress.COMPRESSION, 2, 5.4419, 9.0),
        ("IPE 400 web", _IPE_400, PartStress.BENDING, 1, 38.4884, 72.0),
        ("IPE 400 flange", _IPE_400, PartStress.BENDING, 2, 4.7926, 9.0),
    ],
)
def test_the_packs_own_measurement_of_c_matches_the_published_ratios(
    label, section, stress, element, ratio, class_1_limit
):
    """The published c/t, pinned through the pack rather than recomputed beside it.

    `rolled_i_section_class` measures each element's flat width and divides, and returns only
    the classes — so the ratio cannot be read back out, and the rows above that quote it are
    doing the source's arithmetic rather than the pack's.

    It can still be pinned exactly. A part is class 1 while ``c/t ≤ limit·ε``, so there is one
    yield strength at which the published ratio sits exactly on that boundary:
    ``f_y = 235 / (c/t ÷ limit)²``. Just below it the pack must say class 1 and just above it
    class 2. Both sides are asserted, because only one side is a test of where the boundary is
    — a function that answered class 1 always would pass the first half.

    This reaches the root radius too, which is the part Table 5.2 gives only as a figure.
    Dropping it from the web's c moves the class 1 boundary from 624 to 418 MPa on the
    HEB 340 and from 822 to 648 on the IPE 400 — a third and a fifth — and both assertions
    fail, with a message naming the ratio the pack must be measuring instead. That was
    checked by making the change, not predicted.

    The ratios are the source's figures carried to the precision its own dimensions give,
    not the two decimals it prints. A boundary solved from a rounded ratio sits a little away
    from the real one, and with a probe this tight it can land on the wrong side of it: the
    HEB 340 flange is printed 5,44 and is 5,4419, which moves the boundary from 642,8 to
    643,2 MPa. Table 5.2's own limit multipliers — 33, 9 and 72 — are exact.
    """
    epsilon_at_boundary = ratio / class_1_limit
    yield_at_boundary = 235.0 / epsilon_at_boundary**2
    height, width, web_t, flange_t, radius = section

    def classify(yield_mpa: float) -> SectionClass:
        return rolled_i_section_class(
            height=Q(f"{height} mm"),
            width=Q(f"{width} mm"),
            web_thickness=Q(f"{web_t} mm"),
            flange_thickness=Q(f"{flange_t} mm"),
            root_radius=Q(f"{radius} mm"),
            yield_strength=Quantity(magnitude=yield_mpa, unit="MPa"),
            stress=stress,
        )[element]

    assert classify(yield_at_boundary * 0.999) is SectionClass.CLASS_1, (
        f"{label}: the pack puts the class 1 boundary above f_y = "
        f"{yield_at_boundary:.1f} MPa, so it does not measure c/t as {ratio}"
    )
    assert classify(yield_at_boundary * 1.001) is SectionClass.CLASS_2, (
        f"{label}: the pack still says class 1 past f_y = {yield_at_boundary:.1f} MPa, so it "
        f"measures a smaller c/t than {ratio}"
    )
