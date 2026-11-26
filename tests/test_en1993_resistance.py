"""EN 1993-1-1 §6.2 cross-section resistance, against the JRC report's worked results.

Four published results are replayed: an HEB 340's compression resistance, and two complete
axial-plus-bending reductions, the second of which exercises the a ≤ 0,5 cap.

The report rounds its intermediates — it prints n = 0,30 for 0,29758 and a = 0,24 for
0,23745 — so each worked example is replayed twice: once fed the report's own rounded
figures, which reproduces its printed answer exactly, and once with the unrounded ones,
whose small difference is asserted rather than hidden. A test that only did the second
would look like a 1 kNm disagreement with the source.
"""

from __future__ import annotations

import pytest

from anvilate.analysis.en1993_classification import SectionClass
from anvilate.analysis.en1993_resistance import (
    TensionGoverned,
    axial_reduction_negligible,
    bending_resistance,
    bending_resistance_with_shear,
    biaxial_bending_utilisation,
    compression_resistance,
    reduced_plastic_moment_major,
    reduced_plastic_moment_minor,
    shear_buckling_check_needed,
    shear_reduction_rho,
    shear_resistance,
    tension_resistance,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

Q = Quantity.parse

_S355 = Q("355 MPa")
_M0 = 1.0  # the report's γ_M0 throughout


def _kn(force: Quantity) -> float:
    return force.to("kN").magnitude


def _knm(moment: Quantity) -> float:
    return moment.to("kN*m").magnitude


# --- §6.2.4, the worked HEB 340 ---------------------------------------------------------


def test_the_worked_heb_340_compression_resistance():
    """JRC §1.3.3.2: A = 170,9 cm², S355, γ_M0 = 1,00 gives N_c,Rd = 6067,0 kN."""
    resistance = compression_resistance(
        area=Q("170.9 cm^2"), yield_strength=_S355, partial_factor_m0=_M0
    )
    # Compared unrounded: 170,9 cm² x 355 MPa is 6066,95 kN, which the report prints as
    # 6067,0. Rounding here first and then allowing a tolerance would pass either way.
    assert _kn(resistance) == pytest.approx(6066.95, abs=0.01)
    # Within the 0,1 kN the report prints to. (Not asserted through `round` or an f-string:
    # 6066,95 is just under 6066.95 as a float, so both round it DOWN to 6066,9.)
    assert abs(_kn(resistance) - 6067.0) < 0.1


def test_a_larger_partial_factor_lowers_the_resistance():
    """γ_M0 divides, so a National Annex raising it is a real reduction, not a formality."""
    at_one = compression_resistance(
        area=Q("170.9 cm^2"), yield_strength=_S355, partial_factor_m0=1.0
    )
    at_one_ten = compression_resistance(
        area=Q("170.9 cm^2"), yield_strength=_S355, partial_factor_m0=1.1
    )
    assert _kn(at_one_ten) == pytest.approx(_kn(at_one) / 1.1)


# --- §6.2.9.1, the two worked axial-plus-bending reductions ------------------------------


def test_the_first_worked_reduction_on_the_reports_own_rounded_figures():
    """JRC §1.3.5.2: M_pl,y,Rd 762,9 kNm, n = 0,30, a = 0,24 gives M_N,y,Rd 606,9 kNm."""
    plastic_axial = Q("5726.2 kN")
    reduced = reduced_plastic_moment_major(
        plastic_moment=Q("762.9 kN*m"),
        # n = 0,30 exactly, which is the figure the report carries forward.
        axial_force=Quantity(magnitude=0.30 * _kn(plastic_axial), unit="kN"),
        plastic_axial_resistance=plastic_axial,
        area_ratio=0.24,
    )
    assert round(_knm(reduced), 1) == pytest.approx(606.9, abs=0.05)


def test_the_first_worked_reduction_end_to_end_differs_only_by_that_rounding():
    """From the section's own dimensions: 608,1 kNm against the report's printed 606,9.

    A = 161,3 cm², b = 300 mm, t_f = 20,5 mm, W_pl,y = 2149·10³ mm³, N_Ed = 1704,0 kN.
    Unrounded n is 0,29758 and a is 0,23745; the report prints 0,30 and 0,24 and carries
    those forward, which is the whole of the 1,2 kNm.
    """
    area = Q("161.3 cm^2")
    plastic_axial = compression_resistance(area=area, yield_strength=_S355, partial_factor_m0=_M0)
    assert round(_kn(plastic_axial), 1) == pytest.approx(5726.2, abs=0.1)
    plastic_moment = bending_resistance(
        section_class=SectionClass.CLASS_1,
        yield_strength=_S355,
        partial_factor_m0=_M0,
        plastic_modulus=Q("2149e3 mm^3"),
    )
    assert round(_knm(plastic_moment), 1) == pytest.approx(762.9, abs=0.05)
    area_ratio = (161.3 - 2 * 30 * 2.05) / 161.3
    assert round(area_ratio, 2) == 0.24
    axial = Q("1704 kN")
    assert round(_kn(axial) / _kn(plastic_axial), 2) == 0.30
    reduced = reduced_plastic_moment_major(
        plastic_moment=plastic_moment,
        axial_force=axial,
        plastic_axial_resistance=plastic_axial,
        area_ratio=area_ratio,
    )
    assert round(_knm(reduced), 1) == pytest.approx(608.1, abs=0.05)
    assert _knm(reduced) - 606.9 == pytest.approx(1.2, abs=0.05)


def test_the_second_worked_reduction_exercises_the_area_ratio_cap():
    """JRC §1.3.5.2 example 6: a_w comes out 0,55 and clause 6.2.9.1(5) uses 0,5.

    A = 52,75 cm², b = 150 mm, t = 8 mm, W_pl,y = 358,8·10³ mm³, N_Ed = 965,0 kN. The cap is
    the branch a reader is most likely to leave out, and leaving it out is unconservative:
    0,55 uncapped gives a larger (1 − 0,5a) divisor... no — a larger a gives a SMALLER
    divisor and a LARGER moment, so an uncapped 0,55 reports more resistance than the clause
    allows. That is asserted below.
    """
    plastic_axial = compression_resistance(
        area=Q("52.75 cm^2"), yield_strength=_S355, partial_factor_m0=_M0
    )
    assert round(_kn(plastic_axial), 1) == pytest.approx(1872.6, abs=0.1)
    plastic_moment = bending_resistance(
        section_class=SectionClass.CLASS_1,
        yield_strength=_S355,
        partial_factor_m0=_M0,
        plastic_modulus=Q("358.8e3 mm^3"),
    )
    assert round(_knm(plastic_moment), 1) == pytest.approx(127.4, abs=0.05)
    raw_ratio = (52.75 - 2 * 15 * 0.8) / 52.75
    assert round(raw_ratio, 2) == 0.55
    # The report's own rounded n = 0,52 with the capped a reproduces its 81,5 kNm.
    on_the_reports_figures = reduced_plastic_moment_major(
        plastic_moment=Q("127.4 kN*m"),
        axial_force=Quantity(magnitude=0.52 * _kn(plastic_axial), unit="kN"),
        plastic_axial_resistance=plastic_axial,
        area_ratio=raw_ratio,
    )
    assert round(_knm(on_the_reports_figures), 1) == pytest.approx(81.5, abs=0.05)
    # And the cap is what did it: 0,5 and 0,55 do not give the same answer.
    capped = reduced_plastic_moment_major(
        plastic_moment=Q("127.4 kN*m"),
        axial_force=Quantity(magnitude=0.52 * _kn(plastic_axial), unit="kN"),
        plastic_axial_resistance=plastic_axial,
        area_ratio=0.5,
    )
    assert _knm(capped) == pytest.approx(_knm(on_the_reports_figures))
    uncapped = 127.4 * (1 - 0.52) / (1 - 0.5 * 0.55)
    assert uncapped > _knm(capped), "an uncapped ratio reports more than the clause allows"


def test_the_major_axis_reduction_is_capped_at_the_unreduced_moment():
    """A small axial force must not be allowed to increase the moment resistance.

    At n = 0 and a = 0,5 the factor (1−n)/(1−0,5a) is 1/0,75 = 1,33, so without the clause's
    own `but M_N,y,Rd ≤ M_pl,y,Rd` a lightly loaded column would report a third more bending
    resistance than the section has.
    """
    plastic = Q("100 kN*m")
    reduced = reduced_plastic_moment_major(
        plastic_moment=plastic,
        axial_force=Q("0.001 kN"),
        plastic_axial_resistance=Q("1000 kN"),
        area_ratio=0.5,
    )
    assert _knm(reduced) == pytest.approx(100.0, abs=0.01)
    assert 1.0 / 0.75 == pytest.approx(1.3333, abs=0.0001)


def test_the_minor_axis_is_untouched_until_the_axial_force_consumes_the_web():
    """Eq. 1.63 while n ≤ a, Eq. 1.64 above it, and zero when the section is squashed."""
    plastic = Q("50 kN*m")
    common = {"plastic_moment": plastic, "plastic_axial_resistance": Q("1000 kN")}
    below = reduced_plastic_moment_minor(axial_force=Q("200 kN"), area_ratio=0.3, **common)
    assert _knm(below) == pytest.approx(50.0), "n = 0,20 <= a = 0,30, so unchanged"
    at = reduced_plastic_moment_minor(axial_force=Q("300 kN"), area_ratio=0.3, **common)
    assert _knm(at) == pytest.approx(50.0), "n = a exactly is still Eq. 1.63"
    above = reduced_plastic_moment_minor(axial_force=Q("650 kN"), area_ratio=0.3, **common)
    # 1 - ((0,65 - 0,3)/0,7)^2 = 1 - 0,25 = 0,75
    assert _knm(above) == pytest.approx(37.5, abs=0.01)
    squashed = reduced_plastic_moment_minor(axial_force=Q("1000 kN"), area_ratio=0.5, **common)
    assert _knm(squashed) == pytest.approx(0.0, abs=1e-9)


def test_an_axial_force_beyond_the_plastic_resistance_is_refused():
    with pytest.raises(RefusalError, match="no moment left to reduce"):
        reduced_plastic_moment_major(
            plastic_moment=Q("50 kN*m"),
            axial_force=Q("1100 kN"),
            plastic_axial_resistance=Q("1000 kN"),
            area_ratio=0.3,
        )


def test_the_negligible_axial_threshold_is_the_one_the_source_works():
    """Clause 6.2.9.1(4): N_Ed ≤ 0,25·N_pl,Rd. The report computes 1431,5 kN and 1704,0 > it."""
    plastic_axial = Q("5726.2 kN")
    assert 0.25 * 5726.2 == pytest.approx(1431.55, abs=0.01)
    assert not axial_reduction_negligible(
        axial_force=Q("1704 kN"), plastic_axial_resistance=plastic_axial
    )
    assert axial_reduction_negligible(
        axial_force=Q("1431.5 kN"), plastic_axial_resistance=plastic_axial
    )


# --- §6.2.3 tension, and the source's own typo -------------------------------------------


def test_tension_without_holes_is_the_gross_section_alone():
    result = tension_resistance(area=Q("100 cm^2"), yield_strength=_S355, partial_factor_m0=_M0)
    assert result.net_section is None
    assert result.governed_by is TensionGoverned.GROSS_SECTION
    assert _kn(result.resistance) == pytest.approx(3550.0)
    assert "no holes declared" in str(result)


def test_the_net_section_can_govern_and_says_so():
    """0,9·A_net·f_u/γ_M2 against A·f_y/γ_M0, and N_t,Rd is the smaller.

    S355 with f_u = 490 MPa, γ_M2 = 1,25: the gross section gives 3550 kN and a net section
    20% smaller gives 0,9 x 80 cm² x 490 / 1,25 = 2822,4 kN, so the holes govern.
    """
    result = tension_resistance(
        area=Q("100 cm^2"),
        yield_strength=_S355,
        partial_factor_m0=_M0,
        net_area=Q("80 cm^2"),
        ultimate_strength=Q("490 MPa"),
        partial_factor_m2=1.25,
    )
    assert _kn(result.gross_section) == pytest.approx(3550.0)
    assert _kn(result.net_section) == pytest.approx(0.9 * 8000.0 * 490.0 / 1.25 / 1000.0)
    assert _kn(result.net_section) == pytest.approx(2822.4, abs=0.1)
    assert result.governed_by is TensionGoverned.NET_SECTION
    assert _kn(result.resistance) == pytest.approx(2822.4, abs=0.1)
    assert "net section" in str(result)


def test_the_net_section_formula_satisfies_the_sources_own_inequality():
    """The report's Eq. (1.27) is a typo — it reprints Eq. (1.26) — and Eq. (1.28) fixes it.

    Eq. (1.28) says N_u,Rd > N_pl,Rd exactly when A_net/A > (f_y/0,9f_u)(γ_M2/γ_M0). Only
    N_u,Rd = 0,9·A_net·f_u/γ_M2 makes that identity true, which is how the implemented form
    was recovered. This test is that identity, swept across the boundary it defines.
    """
    # S235 with f_u = 360 MPa, where the boundary share is 0,907 and so reachable. At S355
    # with f_u = 490 it comes out 1,006 — above 1 — which says something worth knowing: with
    # gamma_M2 = 1,25 an S355 member can never satisfy clause 6.2.3(3), because 0,9 f_u/1,25
    # is 352,8 MPa against f_y/1,00 of 355. The sweep below therefore uses S235.
    fy, fu, m0, m2 = 235.0, 360.0, 1.0, 1.25
    boundary = (fy / (0.9 * fu)) * (m2 / m0)
    gross_area = Q("100 cm^2")
    for offset in (-0.05, -0.01, 0.01, 0.05):
        share = boundary + offset
        result = tension_resistance(
            area=gross_area,
            yield_strength=Q(f"{fy} MPa"),
            partial_factor_m0=m0,
            net_area=Quantity(magnitude=share * 10000.0, unit="mm^2"),
            ultimate_strength=Q(f"{fu} MPa"),
            partial_factor_m2=m2,
        )
        assert result.dissipative_capable is (offset > 0), (share, boundary)


def test_the_three_net_section_inputs_are_all_or_nothing():
    """Two of three would silently report the gross section as the member's resistance."""
    with pytest.raises(RefusalError, match="declared together or not"):
        tension_resistance(
            area=Q("100 cm^2"),
            yield_strength=_S355,
            partial_factor_m0=_M0,
            net_area=Q("80 cm^2"),
        )


def test_a_net_area_larger_than_the_gross_is_refused():
    with pytest.raises(RefusalError, match="exceeds the gross area"):
        tension_resistance(
            area=Q("100 cm^2"),
            yield_strength=_S355,
            partial_factor_m0=_M0,
            net_area=Q("120 cm^2"),
            ultimate_strength=Q("490 MPa"),
            partial_factor_m2=1.25,
        )


# --- §6.2.5 bending: the class chooses the modulus ----------------------------------------


@pytest.mark.parametrize(
    ("section_class", "field"),
    [
        (SectionClass.CLASS_1, "plastic_modulus"),
        (SectionClass.CLASS_2, "plastic_modulus"),
        (SectionClass.CLASS_3, "elastic_modulus"),
        (SectionClass.CLASS_4, "effective_modulus"),
    ],
)
def test_each_class_bends_on_its_own_modulus(section_class, field):
    """Clause 6.2.5(2) maps class to modulus, and that mapping is the function."""
    resistance = bending_resistance(
        section_class=section_class,
        yield_strength=_S355,
        partial_factor_m0=_M0,
        **{field: Q("1000e3 mm^3")},
    )
    assert _knm(resistance) == pytest.approx(355.0)


def test_the_wrong_modulus_for_the_class_is_refused():
    """W_pl for a class 3 section reports a plastic moment it cannot reach."""
    with pytest.raises(RefusalError, match="elastic_modulus is required|W_el,min"):
        bending_resistance(
            section_class=SectionClass.CLASS_3,
            yield_strength=_S355,
            partial_factor_m0=_M0,
            plastic_modulus=Q("1000e3 mm^3"),
        )


def test_two_moduli_at_once_are_refused():
    """Which one was used would otherwise be left to the reader."""
    with pytest.raises(RefusalError, match="was given as well"):
        bending_resistance(
            section_class=SectionClass.CLASS_1,
            yield_strength=_S355,
            partial_factor_m0=_M0,
            plastic_modulus=Q("1000e3 mm^3"),
            elastic_modulus=Q("900e3 mm^3"),
        )


def test_a_section_class_from_somewhere_else_is_refused():
    with pytest.raises(RefusalError, match="must be a SectionClass"):
        bending_resistance(
            section_class=1,  # type: ignore[arg-type]
            yield_strength=_S355,
            partial_factor_m0=_M0,
            plastic_modulus=Q("1000e3 mm^3"),
        )


# --- §6.2.6 and §6.2.8 shear ---------------------------------------------------------------


def test_the_shear_resistance_carries_the_von_mises_divisor():
    """V_pl,Rd = A_v(f_y/√3)/γ_M0: the √3 is the whole difference from a tension area."""
    resistance = shear_resistance(
        shear_area=Q("5000 mm^2"), yield_strength=_S355, partial_factor_m0=_M0
    )
    assert _kn(resistance) == pytest.approx(5000 * 355 / 3**0.5 / 1000, rel=1e-9)
    assert _kn(resistance) == pytest.approx(1024.8, abs=0.1)


def test_the_shear_buckling_trigger_is_72_epsilon_over_eta():
    """h_w/t_w > 72ε/η, with η = 1,0 the conservative default the source names."""
    assert not shear_buckling_check_needed(
        web_depth=Q("500 mm"), web_thickness=Q("10 mm"), epsilon=1.0
    )
    assert shear_buckling_check_needed(web_depth=Q("730 mm"), web_thickness=Q("10 mm"), epsilon=1.0)
    # eta DIVIDES, so a larger eta lowers the threshold and asks for the check sooner:
    # 72/1,2 = 60, and this web's 73 is past it either way. The direction is the thing to
    # get right — 1,0 is the source's conservative value for eta's role in the EN 1993-1-5
    # resistance, and the permissive end of this trigger.
    assert shear_buckling_check_needed(
        web_depth=Q("730 mm"), web_thickness=Q("10 mm"), epsilon=1.0, eta=1.2
    )
    assert not shear_buckling_check_needed(
        web_depth=Q("610 mm"), web_thickness=Q("10 mm"), epsilon=1.0, eta=1.0
    )
    assert shear_buckling_check_needed(
        web_depth=Q("610 mm"), web_thickness=Q("10 mm"), epsilon=1.0, eta=1.2
    )


def test_rho_is_zero_below_half_the_shear_resistance_and_one_at_it():
    """§6.2.8's threshold, from both sides, and the formula's own continuity at it."""
    capacity = Q("1000 kN")
    assert shear_reduction_rho(shear_force=Q("400 kN"), shear_capacity=capacity) == 0.0
    assert shear_reduction_rho(shear_force=Q("500 kN"), shear_capacity=capacity) == 0.0
    assert shear_reduction_rho(shear_force=Q("750 kN"), shear_capacity=capacity) == pytest.approx(
        0.25
    )
    assert shear_reduction_rho(shear_force=Q("1000 kN"), shear_capacity=capacity) == pytest.approx(
        1.0
    )
    with pytest.raises(RefusalError, match="fails in shear"):
        shear_reduction_rho(shear_force=Q("1100 kN"), shear_capacity=capacity)


def test_low_shear_leaves_the_bending_resistance_exactly_alone():
    """At ρ = 0 Eq. 1.54 collapses to M_y,c,Rd, which is the clause's own first bullet."""
    common = {
        "plastic_modulus": Q("2149e3 mm^3"),
        "web_area": Q("3000 mm^2"),
        "web_thickness": Q("12 mm"),
        "yield_strength": _S355,
        "partial_factor_m0": _M0,
        "shear_capacity": Q("1000 kN"),
    }
    plain = bending_resistance(
        section_class=SectionClass.CLASS_1,
        yield_strength=_S355,
        partial_factor_m0=_M0,
        plastic_modulus=Q("2149e3 mm^3"),
    )
    low = bending_resistance_with_shear(shear_force=Q("400 kN"), **common)
    assert _knm(low) == pytest.approx(_knm(plain))
    high = bending_resistance_with_shear(shear_force=Q("900 kN"), **common)
    assert _knm(high) < _knm(plain)
    # ρ = (2 x 0,9 - 1)^2 = 0,64; the web term is 0,64 x 3000^2/(4 x 12) = 120 000 mm^3.
    assert _knm(high) == pytest.approx((2149e3 - 0.64 * 3000**2 / 48) * 355 / 1e6, rel=1e-9)


def test_the_shear_reduced_moment_never_exceeds_the_unreduced_one():
    """Eq. 1.54's own `but`, which binds where the web term would come out negative."""
    reduced = bending_resistance_with_shear(
        plastic_modulus=Q("100e3 mm^3"),
        web_area=Q("100 mm^2"),
        web_thickness=Q("5 mm"),
        yield_strength=_S355,
        partial_factor_m0=_M0,
        shear_force=Q("100 kN"),
        shear_capacity=Q("1000 kN"),
    )
    plain = bending_resistance(
        section_class=SectionClass.CLASS_1,
        yield_strength=_S355,
        partial_factor_m0=_M0,
        plastic_modulus=Q("100e3 mm^3"),
    )
    assert _knm(reduced) == pytest.approx(_knm(plain))


# --- §6.2.9 biaxial bending ----------------------------------------------------------------


def test_the_biaxial_exponents_are_what_make_it_worth_a_function():
    """With α = 2 a section at 70% of its major-axis resistance has spent 49%, not 70%."""
    common = {
        "moment_y": Q("70 kN*m"),
        "resistance_y": Q("100 kN*m"),
        "moment_z": Q("0 kN*m"),
        "resistance_z": Q("40 kN*m"),
    }
    assert biaxial_bending_utilisation(**common) == pytest.approx(0.70)
    assert biaxial_bending_utilisation(alpha=2.0, beta=1.0, **common) == pytest.approx(0.49)


def test_the_conservative_default_is_one_and_one():
    """Clause 6.2.9(6) permits 1,0 for both, and that is the safe reading, so it is default.

    A linear sum is always at least as large as the shape-specific one for ratios below 1,
    so defaulting to 1,0 can only over-report the utilisation, never under-report it.
    """
    ratios = (0.6, 0.3)
    linear = biaxial_bending_utilisation(
        moment_y=Quantity(magnitude=ratios[0] * 100, unit="kN*m"),
        resistance_y=Q("100 kN*m"),
        moment_z=Quantity(magnitude=ratios[1] * 40, unit="kN*m"),
        resistance_z=Q("40 kN*m"),
    )
    shaped = biaxial_bending_utilisation(
        moment_y=Quantity(magnitude=ratios[0] * 100, unit="kN*m"),
        resistance_y=Q("100 kN*m"),
        moment_z=Quantity(magnitude=ratios[1] * 40, unit="kN*m"),
        resistance_z=Q("40 kN*m"),
        alpha=2.0,
        beta=1.0,
    )
    assert linear == pytest.approx(0.9)
    assert shaped < linear


def test_a_negative_moment_is_refused_rather_than_subtracted():
    """Eq. (1.50) sums utilisations; a signed moment would relieve the other axis."""
    with pytest.raises(RefusalError, match="magnitude here"):
        biaxial_bending_utilisation(
            moment_y=Q("-70 kN*m"),
            resistance_y=Q("100 kN*m"),
            moment_z=Q("10 kN*m"),
            resistance_z=Q("40 kN*m"),
        )


# --- refusals shared across the module ------------------------------------------------------


@pytest.mark.parametrize("factor", [0.9, 0.0, -1.0])
def test_a_partial_factor_below_one_is_refused(factor: float):
    """It divides a resistance; below 1 it would report more than the characteristic value."""
    with pytest.raises(RefusalError, match="at least 1"):
        compression_resistance(area=Q("100 cm^2"), yield_strength=_S355, partial_factor_m0=factor)


@pytest.mark.parametrize("bad", [Q("0 cm^2"), Q("-10 cm^2"), Q("100 mm")])
def test_an_area_that_is_not_a_positive_area_is_refused(bad):
    with pytest.raises(RefusalError, match="area"):
        compression_resistance(area=bad, yield_strength=_S355, partial_factor_m0=_M0)


def test_a_non_finite_partial_factor_cannot_pass_the_comparison():
    with pytest.raises((RefusalError, ValueError)):
        compression_resistance(
            area=Q("100 cm^2"), yield_strength=_S355, partial_factor_m0=float("nan")
        )


def test_a_non_finite_area_cannot_pass_the_positivity_check():
    with pytest.raises((RefusalError, ValueError)):
        compression_resistance(
            area=Quantity(magnitude=float("nan"), unit="mm^2"),
            yield_strength=_S355,
            partial_factor_m0=_M0,
        )


@pytest.mark.parametrize("poison", [float("nan"), float("inf"), float("-inf")])
def test_no_input_of_the_bending_resistance_takes_a_non_finite_value(poison: float):
    """`bending_resistance` sits outside the library's non-finite probes, so this covers it.

    The binder in tests/test_fraction_guards.py cannot build a call for it: the modulus a
    class needs is a defaulted parameter, so a bound call arrives with every modulus None
    and is refused before any value is examined. Each of its three inputs is therefore
    refused non-finite here by name.
    """
    with pytest.raises((RefusalError, ValueError)):
        bending_resistance(
            section_class=SectionClass.CLASS_1,
            yield_strength=_S355,
            partial_factor_m0=_M0,
            plastic_modulus=Quantity(magnitude=poison, unit="mm^3"),
        )
    with pytest.raises((RefusalError, ValueError)):
        bending_resistance(
            section_class=SectionClass.CLASS_1,
            yield_strength=Quantity(magnitude=poison, unit="MPa"),
            partial_factor_m0=_M0,
            plastic_modulus=Q("1000e3 mm^3"),
        )
    with pytest.raises((RefusalError, ValueError)):
        bending_resistance(
            section_class=SectionClass.CLASS_1,
            yield_strength=_S355,
            partial_factor_m0=poison,
            plastic_modulus=Q("1000e3 mm^3"),
        )


def test_a_bound_call_with_no_modulus_is_refused_rather_than_answered():
    """Why the binder cannot reach it, asserted rather than only described above."""
    with pytest.raises(RefusalError, match="plastic_modulus"):
        bending_resistance(
            section_class=SectionClass.CLASS_1, yield_strength=_S355, partial_factor_m0=_M0
        )
