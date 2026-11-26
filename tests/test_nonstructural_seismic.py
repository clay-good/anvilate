"""The component seismic design force, against the public tables it was derived from.

Nothing here is a number this library chose. NIST GCR 18-917-43 — the ATC-120 report that
produced the equation ASCE/SEI 7-22 adopted — tabulates Fp/Wp for archetype buildings at
S_DS = 1.0 in its Tables 4-12 and 4-14, and prints the inputs for each archetype in its
§4.8 and Table 4-3. Every cell of one archetype row is replayed here, which pins the whole
of Eq. 13.3-1 at once: the 0.4 constant, H_f with both of its terms, R_μ, the two
tabulated coefficients, and Eq. 13.3-3's floor.

The 2016 form is pinned against the same report's §4.9.2 worked cabinet, whose numbers it
states in prose rather than in a table.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.analysis.nonstructural_seismic import (
    ComponentForce,
    ComponentForceEdition,
    ForceBound,
    LateralLoadCase,
    TabulatedCoefficient,
    component_seismic_design_force_asce_7_16,
    component_seismic_design_force_asce_7_22,
    component_vertical_seismic_force,
    governing_lateral_load_case,
    height_amplification_factor,
    structure_ductility_reduction_factor,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

Q = Quantity.parse

#: A unit weight, so every force below reads directly as the report's Fp/Wp.
_UNIT_WEIGHT = Q("1 kN")

#: Table 4-2's "less likely to be in resonance" row, which is the row the report's
#: unlikely-resonance column uses.
_CAR_UNLIKELY = TabulatedCoefficient(
    symbol="C_AR",
    value=1.0,
    table="NIST GCR 18-917-43 Table 4-2, less likely to be in resonance",
)
#: §4.3.4.4's placeholder reserve-strength factor, which the Provisions kept as R_po.
_RPO = TabulatedCoefficient(
    symbol="R_po",
    value=1.3,
    table="NIST GCR 18-917-43 §4.3.4.4, the component reserve strength margin factor",
)

#: The 4-story steel OCBF archetype: T_a = 0.020 x 56^0.75 = 0.41 s (§4.8), R = 3.25 and
#: Omega_0 = 2 (Table 4-3).
_OCBF_PERIOD = Q("0.41 s")
_OCBF_R = 3.25
_OCBF_OMEGA = 2.0

#: Table 4-12's 4-story-steel-OCBF row, unlikely-resonance column, and Table 4-14's same
#: row after its Omega_0 = 1.5 anchor factor: (z/h, Fp/Wp, Omega_0 x Fp/Wp).
_OCBF_ROW = (
    (1.00, 0.80, 1.20),
    (0.75, 0.65, 0.98),
    (0.50, 0.51, 0.77),
    (0.25, 0.37, 0.56),
    (0.00, 0.30, 0.45),
)
_ANCHOR_OVERSTRENGTH = 1.5


def _force_ratio(height_ratio: float) -> ComponentForce:
    """The archetype row's cell at ``height_ratio``, on the report's own terms.

    The report carries the building's R_mu down to z/h = 0; §13.3.1.2 as enacted sets
    R_mu = 1.0 there. Replaying the report means using the report's reading.
    """
    return component_seismic_design_force_asce_7_22(
        design_spectral_acceleration=1.0,
        component_weight=_UNIT_WEIGHT,
        height_amplification=height_amplification_factor(
            height_ratio=height_ratio, fundamental_period=_OCBF_PERIOD
        ),
        ductility_reduction=structure_ductility_reduction_factor(
            response_modification_factor=_OCBF_R, overstrength_factor=_OCBF_OMEGA
        ),
        resonance_ductility=_CAR_UNLIKELY,
        component_strength=_RPO,
    )


def test_table_4_3_ductility_reduction():
    """Table 4-3 prints R_mu = 1.33 for a steel OCBF with R = 3.25 and Omega_0 = 2.

    sqrt(1.1 x 3.25 / 2) = sqrt(1.7875) = 1.3369, which the report rounds down to 1.33.
    """
    assert structure_ductility_reduction_factor(
        response_modification_factor=_OCBF_R, overstrength_factor=_OCBF_OMEGA
    ) == pytest.approx(1.33697, abs=1e-5)


def test_ductility_reduction_takes_the_floor_of_eq_13_3_6():
    """Eq. 13.3-6 floors R_mu at 1.3, so a low-ductility system gets no credit below it.

    R = 1.5 with Omega_0 = 2.5 gives sqrt(1.1 x 1.5 / 2.5) = sqrt(0.66) = 0.812, which is
    an *amplification* if the floor is not applied — the reported force would have been
    1.6 times too large.
    """
    assert structure_ductility_reduction_factor(
        response_modification_factor=1.5, overstrength_factor=2.5
    ) == pytest.approx(1.3)


@pytest.mark.parametrize(("height_ratio", "published", "with_overstrength"), _OCBF_ROW)
def test_table_4_12_and_4_14_ocbf_row(
    height_ratio: float, published: float, with_overstrength: float
):
    """Every published cell of one archetype row, to the two decimals the report prints."""
    card = _force_ratio(height_ratio)
    ratio = card.force.to("kN").magnitude
    assert round(ratio, 2) == published
    assert round(ratio * _ANCHOR_OVERSTRENGTH, 2) == with_overstrength


def test_the_published_floor_cell_is_the_floor():
    """At z/h = 0 the equation gives 0.23 and Eq. 13.3-3 lifts it to 0.30.

    This is the one cell of the row that exercises the minimum, and the only published
    value anywhere in the report that does, so without it Eq. 13.3-3 is unpinned.
    """
    card = _force_ratio(0.0)
    assert card.governed_by is ForceBound.MINIMUM
    assert card.from_equation.to("kN").magnitude == pytest.approx(0.23014, abs=1e-5)
    assert card.force.to("kN").magnitude == pytest.approx(0.30)
    assert card.minimum.to("kN").magnitude == pytest.approx(0.30)
    assert card.maximum.to("kN").magnitude == pytest.approx(1.60)
    assert "minimum" in str(card)


def test_at_or_below_grade_clears_the_floor_on_the_enacted_reading():
    """R_mu = 1.0 at or below grade (Section 13.3.1.2) gives 0.31, which clears 0.30.

    The report's own 0.30 at z/h = 0 comes from carrying the building's R_mu down to the
    base. The enacted clause does not, and the two readings land on either side of the
    floor — which is why R_mu is the caller's and not computed inside the force.
    """
    card = component_seismic_design_force_asce_7_22(
        design_spectral_acceleration=1.0,
        component_weight=_UNIT_WEIGHT,
        height_amplification=1.0,
        ductility_reduction=1.0,
        resonance_ductility=_CAR_UNLIKELY,
        component_strength=_RPO,
    )
    assert card.governed_by is ForceBound.EQUATION
    assert card.force.to("kN").magnitude == pytest.approx(0.4 / 1.3, abs=1e-9)


def test_the_cap_of_eq_13_3_2_is_1_6_and_not_the_reports_2_0():
    """ATC-120 proposed 2.0 S_DS I_p W_p; the Provisions enacted 1.6, which is applied.

    The report tabulates this case twice over, which is what makes it the useful one.
    Table 4-13 is its uncapped table, and for this archetype's roof with an elastic
    component (Table 4-2's C_AR = 4.0 at a roof or elevated floor) it prints **3.21** —
    reproduced below to its two decimals, so the unbounded equation is pinned on a
    published value and not only on the bounded ones. Tables 4-12 and 4-14 then print
    **2.00** for the same cell, their own proposed cap. The enacted cap is 1.6, which is
    what this returns: a 20% difference, on a cell where the report shows its working.
    """
    elastic = TabulatedCoefficient(
        symbol="C_AR", value=4.0, table="NIST GCR 18-917-43 Table 4-2, roof, elastic"
    )
    card = component_seismic_design_force_asce_7_22(
        design_spectral_acceleration=1.0,
        component_weight=_UNIT_WEIGHT,
        height_amplification=height_amplification_factor(
            height_ratio=1.0, fundamental_period=_OCBF_PERIOD
        ),
        ductility_reduction=structure_ductility_reduction_factor(
            response_modification_factor=_OCBF_R, overstrength_factor=_OCBF_OMEGA
        ),
        resonance_ductility=elastic,
        component_strength=_RPO,
    )
    assert card.governed_by is ForceBound.MAXIMUM
    assert card.force.to("kN").magnitude == pytest.approx(1.6)
    assert round(card.from_equation.to("kN").magnitude, 2) == 3.21
    assert card.from_equation.to("kN").magnitude == pytest.approx(3.21020, abs=1e-5)


def test_height_amplification_terms_of_eq_13_3_4():
    """H_f = 1 + a_1(z/h) + a_2(z/h)^10 for the archetype, term by term.

    a_1 = 1/0.41 = 2.43902 (under the 2.5 cap); a_2 = 1 - (0.4/0.41)^2 = 0.048186.
    At z/h = 1 both terms are whole: H_f = 1 + 2.43902 + 0.048186 = 3.48721.
    At z/h = 0.75 the tenth power is 0.0563135, so the second term is 0.0027135 — the
    whole of what the tenth power contributes anywhere below the roof.
    """
    assert height_amplification_factor(
        height_ratio=1.0, fundamental_period=_OCBF_PERIOD
    ) == pytest.approx(3.48721, abs=1e-5)
    assert height_amplification_factor(
        height_ratio=0.75, fundamental_period=_OCBF_PERIOD
    ) == pytest.approx(2.83198, abs=1e-5)


def test_a1_is_capped_and_a2_is_floored():
    """A stiff structure takes a_1 = 2.5, and one below T_a = 0.4 s takes a_2 = 0.

    At T_a = 0.2 s, 1/T_a is 5.0 and the cap holds a_1 at 2.5, while
    1 - (0.4/0.2)^2 = -3.0 is floored at 0. Without the floor H_f at the roof would be
    1 + 2.5 - 3.0 = 0.5, an *attenuation* with height, which is the wrong sign.
    """
    assert height_amplification_factor(
        height_ratio=1.0, fundamental_period=Q("0.2 s")
    ) == pytest.approx(3.5)


def test_eq_13_3_5_is_the_straight_line_where_the_period_is_unknown():
    """Without T_a, H_f = 1 + 2.5(z/h), which agrees with Eq. 13.3-4 only at the base."""
    assert height_amplification_factor(height_ratio=0.0) == pytest.approx(1.0)
    assert height_amplification_factor(height_ratio=1.0) == pytest.approx(3.5)
    assert height_amplification_factor(height_ratio=0.5) == pytest.approx(2.25)


def test_height_ratio_need_not_exceed_one():
    """Section 13.3.1.1 says z/h need not exceed 1.0, so a larger ratio is taken as 1.0."""
    assert height_amplification_factor(height_ratio=2.5) == height_amplification_factor(
        height_ratio=1.0
    )


def test_the_2016_worked_cabinet_of_section_4_9_2():
    """A floor-mounted cabinet at z/h = 0.75 with a_p = 1 and R_p = 2.5 (Section 4.9.2).

    Fp/Wp = 0.4 x 1.0 x 1 x (1 + 2 x 0.75) / 2.5 = 0.40, and the report's Table 4-10
    prints 0.80 for it after the Omega_0 = 2 the same paragraph applies to the anchors.
    """
    card = component_seismic_design_force_asce_7_16(
        design_spectral_acceleration=1.0,
        component_weight=_UNIT_WEIGHT,
        height_ratio=0.75,
        amplification=TabulatedCoefficient(
            symbol="a_p", value=1.0, table="ASCE/SEI 7-16 Table 13.5-1, per NIST GCR §4.9.2"
        ),
        response_modification=TabulatedCoefficient(
            symbol="R_p", value=2.5, table="ASCE/SEI 7-16 Table 13.5-1, per NIST GCR §4.9.2"
        ),
    )
    assert card.governed_by is ForceBound.EQUATION
    assert card.force.to("kN").magnitude == pytest.approx(0.40)
    assert card.force.to("kN").magnitude * 2.0 == pytest.approx(0.80)
    assert card.edition is ComponentForceEdition.ASCE_7_16
    assert "ASCE/SEI 7-16" in card.method


def test_the_two_editions_disagree_on_the_same_cabinet():
    """The rewrite is not a restatement: the same cabinet moves by a factor of 1.6.

    Section 4.9.2's whole point. The 2016 equation gives 0.40 Fp/Wp for the in-plane
    cabinet; the 2022 equation with an unlikely-resonance component gives 0.65. A force
    reported without its edition is therefore not a number anyone can check, which is why
    both functions name theirs.
    """
    sixteen = component_seismic_design_force_asce_7_16(
        design_spectral_acceleration=1.0,
        component_weight=_UNIT_WEIGHT,
        height_ratio=0.75,
        amplification=TabulatedCoefficient(
            symbol="a_p", value=1.0, table="ASCE/SEI 7-16 Table 13.5-1, per NIST GCR §4.9.2"
        ),
        response_modification=TabulatedCoefficient(
            symbol="R_p", value=2.5, table="ASCE/SEI 7-16 Table 13.5-1, per NIST GCR §4.9.2"
        ),
    )
    twenty_two = _force_ratio(0.75)
    assert sixteen.edition is ComponentForceEdition.ASCE_7_16
    assert twenty_two.edition is ComponentForceEdition.ASCE_7_22
    assert sixteen.method != twenty_two.method
    ratio = twenty_two.force.to("kN").magnitude / sixteen.force.to("kN").magnitude
    assert ratio == pytest.approx(1.6294, abs=1e-4)


def test_the_vertical_force_is_reduced_by_nothing():
    """Section 13.3.1.6's 0.2 S_DS W_p takes no importance factor and no ductility.

    It is the term that lightens the weight resisting overturning, so a reader who assumes
    it scales like the horizontal force gets the anchors wrong in the unsafe direction.
    """
    assert component_vertical_seismic_force(
        design_spectral_acceleration=0.6, component_weight=Q("10 kN")
    ).to("kN").magnitude == pytest.approx(1.2)


def test_a_nonseismic_case_that_exceeds_fp_governs():
    """Section 13.3.1.7: a declared wind case larger than Fp is the one the anchors see."""
    seismic = LateralLoadCase(
        tag="seismic Fp",
        force=Q("3.1 kN"),
        source="Eq. 13.3-1 under the design basis's pinned edition",
    )
    wind = LateralLoadCase(
        tag="rooftop wind",
        force=Q("4.4 kN"),
        source="project wind study, 3-second gust on the unit's projected area",
    )
    assert governing_lateral_load_case((seismic, wind)) is wind
    assert governing_lateral_load_case((wind, seismic)) is wind
    assert governing_lateral_load_case((seismic,)) is seismic


def test_a_tie_goes_to_the_case_declared_first():
    """Equal cases are a stable answer rather than an arbitrary one."""
    first = LateralLoadCase(tag="a", force=Q("2 kN"), source="the declared dynamic force")
    second = LateralLoadCase(tag="b", force=Q("2 kN"), source="the declared impact allowance")
    assert governing_lateral_load_case((first, second)) is first


def test_one_case_passed_bare_is_not_three():
    """A pydantic model iterates over its own fields, so a bare case must be refused."""
    only = LateralLoadCase(tag="a", force=Q("2 kN"), source="the declared dynamic force")
    with pytest.raises((RefusalError, ValidationError, TypeError)):
        governing_lateral_load_case(only)  # type: ignore[arg-type]


def test_no_cases_is_refused_rather_than_answered():
    with pytest.raises(RefusalError, match="at least one case"):
        governing_lateral_load_case(())


def test_a_coefficient_with_no_table_is_refused():
    """The scenario the pack needs: a coefficient nobody can trace is not a coefficient."""
    with pytest.raises((RefusalError, ValidationError)):
        TabulatedCoefficient(symbol="C_AR", value=1.0, table="")


@pytest.mark.parametrize("value", [0.0, -1.0])
def test_a_coefficient_that_is_not_positive_is_refused(value: float):
    """R_po = 0 is a division by zero and C_AR = 0 is a component nothing reaches."""
    with pytest.raises((RefusalError, ValidationError)):
        TabulatedCoefficient(symbol="R_po", value=value, table="Table 13.6-1")


def test_a_negative_height_ratio_names_the_clause_that_covers_it():
    with pytest.raises(RefusalError, match="sets z to 0"):
        height_amplification_factor(height_ratio=-0.1)


def test_a_mass_is_not_an_operating_weight():
    """W_p is a force here; a mass passed in its place is refused by dimension."""
    with pytest.raises(RefusalError, match=r"\[force\]"):
        component_vertical_seismic_force(
            design_spectral_acceleration=1.0, component_weight=Q("2400 kg")
        )


def test_a_nonfinite_spectral_acceleration_cannot_pass_the_positivity_check():
    """NaN fails every comparison, so `if sds <= 0` alone would have let it through."""
    with pytest.raises((RefusalError, ValueError)):
        component_vertical_seismic_force(
            design_spectral_acceleration=float("nan"), component_weight=Q("10 kN")
        )


@pytest.mark.parametrize("poison", [float("nan"), float("inf"), float("-inf")])
def test_no_field_of_a_load_case_takes_a_non_finite_value(poison: float):
    """A case's force, which `governing_lateral_load_case` compares, cannot be poisoned.

    The binder in tests/test_fraction_guards.py cannot construct a sequence of models, so
    that function sits outside the library's non-finite probes and this is the test that
    covers it instead. It matters more here than in most places: the comparison is a
    `max`, and `max` *drops* a NaN candidate rather than propagating it, so an unguarded
    NaN force would have made the governing case silently the wrong one.
    """
    with pytest.raises((RefusalError, ValidationError)):
        LateralLoadCase(
            tag="poisoned", force=Quantity(magnitude=poison, unit="kN"), source="a load study"
        )


@pytest.mark.parametrize("poison", [float("nan"), float("inf"), float("-inf")])
def test_no_field_of_a_tabulated_coefficient_takes_a_non_finite_value(poison: float):
    """A coefficient's value divides or multiplies a force, so a NaN is a NaN force."""
    with pytest.raises((RefusalError, ValidationError)):
        TabulatedCoefficient(symbol="C_AR", value=poison, table="Table 13.6-1")


def test_a_governing_case_is_chosen_even_though_max_drops_a_nan():
    """The guard is on the model, so the comparison never sees one — stated as a test.

    A refusal at construction is only a real guard if nothing can reach the comparison
    another way, and this is the assertion that the only route in is the one guarded.
    """
    cases = (
        LateralLoadCase(tag="seismic", force=Q("1 kN"), source="Eq. 13.3-1"),
        LateralLoadCase(tag="wind", force=Q("2 kN"), source="the project wind study"),
    )
    assert governing_lateral_load_case(cases).tag == "wind"
    with pytest.raises((RefusalError, ValidationError)):
        cases[0].model_copy(update={"force": Quantity(magnitude=float("nan"), unit="kN")})


def test_the_docs_pages_figures_are_the_modules_own():
    """Every number docs/equipment-anchorage.md quotes, against what the code computes.

    A figure that lives only in prose has no gate, and this page's whole purpose is to
    tell a reader which coefficients are theirs — so a count or a cell that has drifted
    from the code is the page misleading exactly the reader it was written for.
    """
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "equipment-anchorage.md").read_text()

    # The two bounds, named as fractions of S_DS I_p W_p.
    assert "1.6·S_DS·I_p·W_p (Eq. 13.3-2)" in page
    assert "0.3·S_DS·I_p·W_p" in page
    unit = component_seismic_design_force_asce_7_22(
        design_spectral_acceleration=1.0,
        component_weight=_UNIT_WEIGHT,
        height_amplification=100.0,
        ductility_reduction=1.0,
        resonance_ductility=_CAR_UNLIKELY,
        component_strength=_RPO,
    )
    assert unit.maximum.to("kN").magnitude == pytest.approx(1.6)
    assert unit.minimum.to("kN").magnitude == pytest.approx(0.3)

    # The archetype row the page lists, in the order it lists it.
    cells = ", ".join(f"{published:.2f}" for _, published, _ in _OCBF_ROW)
    assert cells == "0.80, 0.65, 0.51, 0.37, 0.30"
    assert "0.80, 0.65, 0.51, 0.37 and 0.30" in page
    assert "Ω_0 = 1.5 anchor factor" in page

    # The uncapped Table 4-13 cell, and the cap that is applied instead of the report's.
    elastic = TabulatedCoefficient(
        symbol="C_AR", value=4.0, table="NIST GCR 18-917-43 Table 4-2, roof, elastic"
    )
    uncapped = component_seismic_design_force_asce_7_22(
        design_spectral_acceleration=1.0,
        component_weight=_UNIT_WEIGHT,
        height_amplification=height_amplification_factor(
            height_ratio=1.0, fundamental_period=_OCBF_PERIOD
        ),
        ductility_reduction=structure_ductility_reduction_factor(
            response_modification_factor=_OCBF_R, overstrength_factor=_OCBF_OMEGA
        ),
        resonance_ductility=elastic,
        component_strength=_RPO,
    )
    assert f"gives {round(uncapped.from_equation.to('kN').magnitude, 2)} for that" in page
    assert "recommended a cap of 2.0·S_DS·I_p·W_p; the" in page

    # The example's headline figures, recomputed here rather than quoted.
    import runpy

    figures = runpy.run_path(
        str(Path(__file__).parents[1] / "examples" / "roof_cabinet_component_force_by_edition.py")
    )["roof_cabinet_component_force_by_edition"]()
    assert f"from {figures['force_2016_n']:,.0f} N to {figures['force_2022_n']:,.0f} N" in page
    assert f"**{figures['edition_ratio']:.2f}**" in page
    assert f"H_f at the roof is {figures['height_factor']:.2f}" in page
    assert f"ductility factor of {figures['ductility_factor']:.2f}" in page
    assert f"only {figures['vertical_term_percent']:.1f}% more" in page
    assert f"under {figures['weight_share_percent']:.0f}%" in page


@pytest.mark.parametrize(
    "call",
    [
        lambda w: component_vertical_seismic_force(
            design_spectral_acceleration=1.0, component_weight=w
        ),
        lambda w: component_seismic_design_force_asce_7_22(
            design_spectral_acceleration=1.0,
            component_weight=w,
            height_amplification=1.0,
            ductility_reduction=1.0,
            resonance_ductility=_CAR_UNLIKELY,
            component_strength=_RPO,
        ),
        lambda w: component_seismic_design_force_asce_7_16(
            design_spectral_acceleration=1.0,
            component_weight=w,
            height_ratio=0.5,
            amplification=TabulatedCoefficient(symbol="a_p", value=1.0, table="Table 13.6-1"),
            response_modification=TabulatedCoefficient(
                symbol="R_p", value=2.5, table="Table 13.6-1"
            ),
        ),
    ],
    ids=["vertical", "asce_7_22", "asce_7_16"],
)
def test_no_force_takes_a_negative_operating_weight(call):
    """A negative weight comes back as a negative force, which reads as a hold-down.

    All three forces share one operating-weight check so none of them can be the one that
    forgot. The vertical force was the one that had: it checked the dimension and the
    finiteness and not the sign, and -10 kN of equipment gave -2 kN of vertical seismic,
    which the anchorage statics add to the resisting weight instead of taking off it.
    """
    with pytest.raises(RefusalError, match="magnitude"):
        call(Q("-10 kN"))


def test_a_coefficient_renders_every_field_it_carries():
    """All three fields, and a rendering that cannot drop the one that matters.

    The whole point of this model is that a coefficient travels with the table it was read
    from. A `__str__` that printed the symbol and the value would read as complete and
    would have thrown away the only field a reviewer can act on — so two coefficients that
    differ *only* in their table must not render alike.
    """
    read = TabulatedCoefficient(symbol="C_AR", value=2.2, table="Table 13.6-1 row 4")
    assert str(read) == "C_AR = 2.2 (Table 13.6-1 row 4)"
    elsewhere = read.model_copy(update={"table": "Table 13.5-1 row 9"})
    assert str(read) != str(elsewhere)
    renamed = read.model_copy(update={"symbol": "R_po"})
    assert str(read) != str(renamed)
    revalued = read.model_copy(update={"value": 1.8})
    assert str(read) != str(revalued)


def test_a_load_case_renders_its_tag_its_force_and_its_source():
    """The three fields, with the force in the unit a person writes rather than the machine.

    `governing_lateral_load_case` returns the case and not the magnitude precisely so the
    answer says *which* load governs; a rendering that dropped the tag would undo that.
    """
    case = LateralLoadCase(
        tag="rooftop wind",
        force=Q("4.4 kN"),
        source="project wind study, 3-second gust on the projected area",
    )
    rendered = str(case)
    assert rendered.startswith("rooftop wind: ")
    # The renderer carries significant figures, not fixed decimals, so this is 4.40.
    assert "4.40 kN" in rendered
    assert "project wind study, 3-second gust on the projected area" in rendered
    for update in (
        {"tag": "machine dynamic force"},
        {"force": Q("4.5 kN")},
        {"source": "the equipment schedule's declared dynamic force"},
    ):
        assert str(case.model_copy(update=update)) != rendered


def test_a_component_force_renders_which_of_the_three_produced_it():
    """Each of Eq. 13.3-1, its cap and its floor reads differently, and says the figure.

    A card that printed only the applied force would hide the fact that a bound is doing
    the work, which on this archetype's roof is the difference between 7,520 N and the
    8,298 N the equation asked for.
    """
    at_equation = _force_ratio(0.75)
    at_floor = _force_ratio(0.0)
    assert str(at_equation) == "Fp = 0.652 kN, between its bounds"
    assert str(at_floor).startswith("Fp = 0.300 kN, the minimum (")
    assert "rather than 0.230 kN" in str(at_floor)
    elastic = TabulatedCoefficient(
        symbol="C_AR", value=4.0, table="NIST GCR 18-917-43 Table 4-2, roof, elastic"
    )
    at_cap = component_seismic_design_force_asce_7_22(
        design_spectral_acceleration=1.0,
        component_weight=_UNIT_WEIGHT,
        height_amplification=height_amplification_factor(
            height_ratio=1.0, fundamental_period=_OCBF_PERIOD
        ),
        ductility_reduction=structure_ductility_reduction_factor(
            response_modification_factor=_OCBF_R, overstrength_factor=_OCBF_OMEGA
        ),
        resonance_ductility=elastic,
        component_strength=_RPO,
    )
    assert "the maximum (1.60 kN) rather than 3.21 kN" in str(at_cap)
    assert len({str(at_equation), str(at_floor), str(at_cap)}) == 3
