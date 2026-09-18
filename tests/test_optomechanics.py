"""A lens kept in focus across temperature: depth of focus, thermal focal shift, defocus."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.analysis.optomechanics import (
    athermal_defocus,
    athermal_focus_scorecard,
    depth_of_focus,
    thermal_focal_shift,
)
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity

q = Quantity.parse

# A 100 mm crown-glass singlet: every property is the caller's, which is the point.
_LENS = {
    "focal_length": q("100 mm"),
    "refractive_index": 1.5168,
    "dn_dt": q("1.6e-6 1/K"),
    "glass_cte": q("7.1e-6 1/K"),
}
_DELTA = q("40 K")


def _um(value: Quantity) -> float:
    return value.to("µm").magnitude


def test_the_depth_of_focus_is_two_lambda_n_squared_either_side() -> None:
    assert _um(depth_of_focus(wavelength=q("550 nm"), f_number=4.0)) == pytest.approx(17.6)
    # Doubling N quadruples it: why a slow lens forgives what a fast one does not.
    slow = depth_of_focus(wavelength=q("550 nm"), f_number=8.0)
    assert _um(slow) == pytest.approx(4 * 17.6)


def test_the_thermal_focal_shift_is_the_glass_thermal_constant_times_f_and_delta_t() -> None:
    # 100 mm × (7.1 − 1.6/0.5168) × 10⁻⁶ /K × 40 K, worked by hand.
    expected = 100e3 * (7.1e-6 - 1.6e-6 / 0.5168) * 40
    assert _um(thermal_focal_shift(**_LENS, temperature_change=_DELTA)) == pytest.approx(expected)
    cooled = thermal_focal_shift(**_LENS, temperature_change=q("-40 K"))
    assert _um(cooled) == pytest.approx(-expected)


def test_a_glass_whose_expansion_cancels_its_index_change_does_not_shift() -> None:
    balanced = {**_LENS, "glass_cte": q(f"{1.6e-6 / 0.5168} 1/K")}
    shift = thermal_focal_shift(**balanced, temperature_change=_DELTA)
    assert _um(shift) == pytest.approx(0.0, abs=1e-9)


def test_a_housing_that_grows_with_the_focus_leaves_no_defocus() -> None:
    shift = thermal_focal_shift(**_LENS, temperature_change=_DELTA)
    # The athermal condition α_h·L = Δf/ΔT, solved for the housing's expansion.
    alpha = shift.to("m").magnitude / (0.1 * 40)
    defocus = athermal_defocus(
        focal_shift=shift,
        housing_cte=q(f"{alpha} 1/K"),
        housing_length=q("100 mm"),
        temperature_change=_DELTA,
    )
    assert _um(defocus) == pytest.approx(0.0, abs=1e-9)


def _screen(housing_cte: str) -> object:
    return athermal_focus_scorecard(
        "lens focus",
        **_LENS,
        f_number=4.0,
        wavelength=q("550 nm"),
        housing_cte=q(housing_cte),
        housing_length=q("100 mm"),
        temperature_change=_DELTA,
    )


def test_an_aluminium_housing_throws_the_image_out_of_focus_and_invar_does_not() -> None:
    aluminium = _screen("23.1e-6 1/K")
    assert aluminium.status is CheckStatus.FAIL
    # 16.02 µm of focal shift against 92.4 µm of housing growth: 76.4 µm out, on ±17.6.
    assert aluminium.detail == "defocus 76.4 µm vs depth of focus 17.6 µm"
    assert aluminium.derivation is not None
    assert aluminium.derivation.result.value.to("µm").magnitude == pytest.approx(-76.384, abs=1e-3)
    invar = _screen("1.2e-6 1/K")
    assert invar.status is CheckStatus.PASS
    assert invar.comparison is not None and invar.comparison.passes()


@pytest.mark.parametrize(
    ("call", "match"),
    [
        (lambda: depth_of_focus(wavelength=q("0 nm"), f_number=4.0), "wavelength must be positive"),
        (lambda: depth_of_focus(wavelength=q("550 nm"), f_number=float("nan")), "f_number"),
        (lambda: depth_of_focus(wavelength=q("550 nm"), f_number=0.0), "f_number must be"),
        (
            lambda: thermal_focal_shift(
                **{**_LENS, "refractive_index": 1.0}, temperature_change=_DELTA
            ),
            "must exceed 1",
        ),
        (
            lambda: thermal_focal_shift(
                **{**_LENS, "dn_dt": q("1.6e-6 1/s")}, temperature_change=_DELTA
            ),
            "dn_dt must be",
        ),
        (
            lambda: athermal_defocus(
                focal_shift=q("16 µm"),
                housing_cte=q("23e-6 1/K"),
                housing_length=q("-1 mm"),
                temperature_change=_DELTA,
            ),
            "housing_length must be positive",
        ),
    ],
)
def test_a_lens_or_housing_outside_the_formula_is_refused(call, match: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match=match):
        call()


def test_miles_equation_is_the_square_root_of_half_pi_fn_q_asd() -> None:
    from math import pi, sqrt

    from anvilate.analysis.optomechanics import miles_random_vibration_grms

    grms = miles_random_vibration_grms(
        natural_frequency=q("200 Hz"), quality_factor=10.0, input_asd=q("0.04 1/Hz")
    )
    assert grms == pytest.approx(sqrt(pi / 2 * 200 * 10 * 0.04))
    # The answer goes as √Q, which is why Q is never defaulted.
    doubled = miles_random_vibration_grms(
        natural_frequency=q("200 Hz"), quality_factor=40.0, input_asd=q("0.04 1/Hz")
    )
    assert doubled == pytest.approx(2 * grms)
    with pytest.raises(ValueError, match="quality_factor must exceed 0.5"):
        miles_random_vibration_grms(
            natural_frequency=q("200 Hz"), quality_factor=0.5, input_asd=q("0.04 1/Hz")
        )


def test_a_retainer_must_press_as_hard_as_the_acceleration_lifts() -> None:
    from anvilate.analysis.optomechanics import retention_preload

    assert retention_preload(mass=q("50 g"), acceleration=20.0).to("N").magnitude == pytest.approx(
        0.05 * 20 * 9.80665
    )
    with pytest.raises(ValueError, match="acceleration must be positive"):
        retention_preload(mass=q("50 g"), acceleration=-1.0)


def test_stress_birefringence_is_k_sigma_t() -> None:
    from anvilate.analysis.optomechanics import stress_birefringence_retardance

    # K = 2.77e-6 mm²/N, 1 MPa over 10 mm of glass: 27.7 nm, by hand.
    opd = stress_birefringence_retardance(
        stress_optic_coefficient=q("2.77e-6 mm**2/N"), stress=q("1 MPa"), path_length=q("10 mm")
    )
    assert opd.to("nm").magnitude == pytest.approx(27.7)


def test_the_marechal_strehl_at_a_fourteenth_of_a_wave_is_about_point_eight() -> None:
    from math import exp, pi

    from anvilate.analysis.optomechanics import marechal_strehl_ratio

    strehl = marechal_strehl_ratio(
        rms_wavefront_error=Quantity(magnitude=550 / 14, unit="nm"), wavelength=q("550 nm")
    )
    assert strehl == pytest.approx(exp(-((2 * pi / 14) ** 2)))
    assert 0.80 < strehl < 0.82
    assert marechal_strehl_ratio(rms_wavefront_error=q("0 nm"), wavelength=q("550 nm")) == 1.0


def test_a_wavefront_budget_is_the_root_sum_square_against_a_declared_strehl() -> None:
    from anvilate.analysis.optomechanics import wavefront_budget_scorecard

    budget = {"figure": q("20 nm"), "mount": q("15 nm"), "alignment": q("25 nm")}
    entry = wavefront_budget_scorecard(
        "wavefront", contributors=budget, wavelength=q("550 nm"), strehl_threshold=0.8
    )
    # √(20² + 15² + 25²) = 35.4 nm against λ/(2π)·√(−ln 0.8) = 41.3 nm.
    assert entry.status is CheckStatus.PASS
    assert entry.detail == "RSS wavefront error 35.4 nm vs RMS error at Strehl 0.8 41.3 nm"
    # One contributor more and the same budget fails: the total is not the largest term.
    grown = {**budget, "thermal": q("25 nm")}
    failed = wavefront_budget_scorecard(
        "wavefront", contributors=grown, wavelength=q("550 nm"), strehl_threshold=0.8
    )
    assert failed.status is CheckStatus.FAIL
    with pytest.raises(ValueError, match="at least one contributor"):
        wavefront_budget_scorecard(
            "wavefront", contributors={}, wavelength=q("550 nm"), strehl_threshold=0.8
        )
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        wavefront_budget_scorecard(
            "wavefront", contributors=budget, wavelength=q("550 nm"), strehl_threshold=1.0
        )


def test_every_figure_the_scope_page_quotes_is_one_the_library_computes() -> None:
    """docs/optomechanics.md argues from numbers; each is recomputed here, not restated."""
    from pathlib import Path

    from anvilate.analysis.optomechanics import (
        marechal_strehl_ratio,
        stress_birefringence_retardance,
    )

    page = (Path(__file__).resolve().parents[1] / "docs" / "optomechanics.md").read_text(
        encoding="utf-8"
    )
    dof = _um(depth_of_focus(wavelength=q("550 nm"), f_number=4.0))
    aluminium = _screen("23.1e-6 1/K").comparison
    titanium = _screen("8.6e-6 1/K").comparison
    assert aluminium is not None and titanium is not None
    retardance = stress_birefringence_retardance(
        stress_optic_coefficient=q("2.77e-6 mm**2/N"), stress=q("1 MPa"), path_length=q("10 mm")
    )
    strehl = marechal_strehl_ratio(
        rms_wavefront_error=Quantity(magnitude=550 / 14, unit="nm"), wavelength=q("550 nm")
    )
    quoted = {
        f"±{dof:.1f} µm": "the f/4 depth of focus",
        f"{aluminium.measured.magnitude:.1f} µm out": "the aluminium defocus",
        f"misses by {titanium.measured.magnitude - titanium.limit.magnitude:.1f} µm": "titanium",
        f"is {retardance.to('nm').magnitude:.1f} nm": "the N-BK7 retardance",
        f"S ≈ {strehl:.1f}": "the Strehl at a fourteenth of a wave",
    }
    missing = {text: what for text, what in quoted.items() if text not in page}
    assert not missing, f"the page no longer states what the library computes: {missing}"


def test_a_sealed_housing_fogs_when_its_coldest_surface_is_below_the_dew_point() -> None:
    from anvilate.analysis.optomechanics import internal_condensation_scorecard

    # Air sealed at 25 °C and 50% relative humidity condenses below 13.9 °C (the Magnus form).
    humid = internal_condensation_scorecard(
        "fogging",
        coldest_surface_temperature=q("253.15 K"),
        fill_temperature=q("298.15 K"),
        fill_relative_humidity=0.5,
    )
    assert humid.status is CheckStatus.FAIL
    assert humid.comparison is not None
    assert humid.comparison.limit.magnitude == pytest.approx(13.86, abs=0.01)
    assert "the optic fogs, 33.9 K short" in humid.detail
    # A dry-nitrogen purge specified to −40 °C holds at the same cold soak.
    purged = internal_condensation_scorecard(
        "fogging", coldest_surface_temperature=q("253.15 K"), internal_dew_point=q("233.15 K")
    )
    assert purged.status is CheckStatus.PASS
    assert "20.0 K clear" in purged.detail


def test_an_unstated_fill_is_not_a_dry_purge() -> None:
    from anvilate.analysis.optomechanics import internal_condensation_scorecard

    entry = internal_condensation_scorecard("fogging", coldest_surface_temperature=q("253.15 K"))
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "an unstated purge is not a dry one" in entry.detail
    # Half a fill condition is still none.
    half = internal_condensation_scorecard(
        "fogging", coldest_surface_temperature=q("253.15 K"), fill_temperature=q("298.15 K")
    )
    assert half.status is CheckStatus.NOT_EVALUATED
    with pytest.raises(ValueError, match="fraction in"):
        internal_condensation_scorecard(
            "fogging",
            coldest_surface_temperature=q("253.15 K"),
            fill_temperature=q("298.15 K"),
            fill_relative_humidity=50.0,
        )


def test_a_mount_decenter_becomes_a_line_of_sight_shift() -> None:
    from anvilate.analysis.optomechanics import decenter_line_of_sight, mount_decenter

    # 50 g at 10 g on 5 N/µm: 0.05 · 10 · 9.80665 / 5e6 m, by hand.
    decenter = mount_decenter(mass=q("50 g"), acceleration=10.0, radial_stiffness=q("5e6 N/m"))
    assert decenter.to("µm").magnitude == pytest.approx(0.05 * 10 * 9.80665 / 5e6 * 1e6)
    shift = decenter_line_of_sight(decenter=decenter, focal_length=q("100 mm"))
    assert shift.to("µrad").magnitude == pytest.approx(decenter.to("m").magnitude / 0.1 * 1e6)
    # A longer lens forgives the same decenter.
    longer = decenter_line_of_sight(decenter=decenter, focal_length=q("400 mm"))
    assert longer.to("µrad").magnitude == pytest.approx(shift.to("µrad").magnitude / 4)


def test_a_mirror_doubles_its_tilt_and_refuses_a_strain_for_an_angle() -> None:
    from math import pi

    from anvilate.analysis.optomechanics import mirror_tilt_line_of_sight

    ten_arcsec = mirror_tilt_line_of_sight(tilt=Quantity(magnitude=10, unit="arcsec"))
    assert ten_arcsec.to("µrad").magnitude == pytest.approx(2 * 10 / 3600 * pi / 180 * 1e6)
    fifty = mirror_tilt_line_of_sight(tilt=Quantity(magnitude=50, unit="µrad"))
    assert fifty.to("µrad").magnitude == pytest.approx(100.0)
    for not_an_angle in ("mm/m", "mm", "dimensionless"):
        with pytest.raises(ValueError, match="must be an angle"):
            mirror_tilt_line_of_sight(tilt=Quantity(magnitude=1, unit=not_an_angle))


def _condition(kind: str, **fields: object):  # type: ignore[no-untyped-def]
    from anvilate.analysis.optomechanics import ThermalCondition, ThermalConditionKind

    return ThermalCondition(kind=ThermalConditionKind(kind), temperature_change=q("40 K"), **fields)


def test_a_soak_screen_refuses_a_gradient_naming_the_kind_it_needs() -> None:
    entry = _screen("1.2e-6 1/K")
    refused = _condition("gradient").qualify(entry)
    assert refused.status is CheckStatus.NOT_EVALUATED
    assert "requires a uniform soak" in refused.detail
    assert _condition("soak").qualify(entry) == entry


def test_a_short_dwell_makes_an_equilibrium_verdict_say_it_is_optimistic() -> None:
    from math import exp

    entry = _screen("1.2e-6 1/K")
    short = _condition("transient", dwell=q("30 min"), time_constant=q("20 min"))
    assert short.equilibrium_fraction == pytest.approx(1 - exp(-1.5))
    qualified = short.qualify(entry)
    assert qualified.status is entry.status
    assert "optimistic: the declared dwell of 30 min" in qualified.detail
    assert "time constant of 20 min" in qualified.detail
    long = _condition("transient", dwell=q("2 h"), time_constant=q("20 min"))
    assert long.qualify(entry) == entry


def test_a_thermal_condition_states_its_kind_and_a_transient_its_durations() -> None:
    from anvilate.analysis.optomechanics import ThermalCondition

    with pytest.raises(ValidationError):
        ThermalCondition(temperature_change=q("40 K"))  # type: ignore[call-arg]
    with pytest.raises(ValidationError, match="needs its dwell"):
        _condition("transient", dwell=q("30 min"))
    with pytest.raises(ValidationError, match="dwell must be positive"):
        _condition("transient", dwell=q("0 min"), time_constant=q("20 min"))


def test_a_gap_clear_at_rest_closes_under_a_declared_shock() -> None:
    from math import pi

    from anvilate.analysis.dynamics import half_sine_shock_amplification
    from anvilate.analysis.optomechanics import dynamic_clearance_scorecard

    shock = {
        "natural_frequency": q("300 Hz"),
        "peak_acceleration": 30.0,
        "pulse_duration": q("11 ms"),
    }
    closed = dynamic_clearance_scorecard("cell gap", gap=q("50 µm"), **shock)
    amplification = half_sine_shock_amplification(
        pulse_duration=q("11 ms"), natural_frequency=q("300 Hz")
    )
    expected = amplification * 30 * 9.80665 / (2 * pi * 300) ** 2 * 1e6
    assert closed.status is CheckStatus.FAIL
    assert closed.comparison is not None
    assert closed.comparison.measured.magnitude == pytest.approx(expected)
    assert closed.detail == f"shock displacement {expected:.1f} µm vs declared gap 50.0 µm"
    # Widen the gap past the displacement and the same shock passes.
    opened = dynamic_clearance_scorecard("cell gap", gap=q("150 µm"), **shock)
    assert opened.status is CheckStatus.PASS
    undeclared = dynamic_clearance_scorecard("cell gap", gap=None, **shock)
    assert undeclared.status is CheckStatus.NOT_EVALUATED
    assert "an undeclared gap is not a generous one" in undeclared.detail


def test_an_athermal_bond_grows_the_bore_as_fast_as_the_glass_and_the_bond() -> None:
    from anvilate.analysis.optomechanics import athermal_bond_thickness

    thickness = (
        athermal_bond_thickness(
            glass_diameter=q("50 mm"),
            glass_cte=q("7.1e-6 1/K"),
            cell_cte=q("23.6e-6 1/K"),
            elastomer_cte=q("250e-6 1/K"),
        )
        .to("mm")
        .magnitude
    )
    assert thickness == pytest.approx(25 * (23.6 - 7.1) / (250 - 23.6))
    assert 1.7 < thickness < 1.9
    # The defining balance, checked directly rather than by restating the formula.
    radius = 25.0
    assert 23.6e-6 * (radius + thickness) == pytest.approx(7.1e-6 * radius + 250e-6 * thickness)
    with pytest.raises(ValueError, match="no positive thickness"):
        athermal_bond_thickness(
            glass_diameter=q("50 mm"),
            glass_cte=q("7.1e-6 1/K"),
            cell_cte=q("5e-6 1/K"),
            elastomer_cte=q("250e-6 1/K"),
        )


def _gland(depth: str, **overrides: object):  # type: ignore[no-untyped-def]
    from anvilate.analysis.optomechanics import seal_gland_extremes_scorecard

    declared: dict[str, object] = {
        "cross_section_diameter": q("2.62 mm"),
        "inner_diameter": q("50 mm"),
        "gland_depth": q(depth),
        "groove_width": q("3.6 mm"),
        "groove_diameter": q("51 mm"),
        "elastomer_cte": q("1.6e-4 1/K"),
        "gland_cte": q("23.6e-6 1/K"),
        "assembly_temperature": q("293.15 K"),
        "cold": q("233.15 K"),
        "hot": q("343.15 K"),
    }
    declared.update(overrides)
    return seal_gland_extremes_scorecard("housing seal", **declared)  # type: ignore[arg-type]


def test_a_gland_in_band_at_assembly_can_lose_its_squeeze_cold() -> None:
    from anvilate.analysis.o_ring import o_ring_squeeze_fraction

    # 15.3 % squeeze at assembly: in band, by the existing function.
    at_assembly = o_ring_squeeze_fraction(
        cross_section_diameter=q("2.62 mm"), gland_depth=q("2.22 mm")
    )
    assert 0.15 < at_assembly < 0.16
    marginal = _gland("2.22 mm")
    assert marginal.status is CheckStatus.FAIL
    assert "out of band at cold" in marginal.detail
    assert "hot:" not in marginal.detail.split("(")[0]
    nominal = _gland("2.0 mm")
    assert nominal.status is CheckStatus.PASS
    assert "cold squeeze 23.0%" in nominal.detail and "hot squeeze 24.2%" in nominal.detail


def test_a_squeeze_that_vanishes_is_reported_as_a_leak_not_raised() -> None:
    leak = _gland("2.6 mm")
    assert leak.status is CheckStatus.FAIL
    assert "no squeeze" in leak.detail and "a leak" in leak.detail


def test_a_glass_record_states_only_what_its_source_does() -> None:
    from anvilate.analysis.optomechanics import N_BK7

    assert (N_BK7.refractive_index, N_BK7.abbe_number) == (1.5168, 64.17)
    assert N_BK7.dn_dt is None and N_BK7.elastic_modulus is None
    assert "refractiveindex.info" in N_BK7.source and "243 K to 343 K" in str(N_BK7)


def test_an_expansion_is_refused_outside_the_range_its_catalogue_states() -> None:
    from anvilate.analysis.optomechanics import N_BK7, OutsideValidRange

    assert N_BK7.cte_over(q("253.15 K"), q("293.15 K")).to("1/K").magnitude == 7.1e-6
    assert N_BK7.cte_over(q("400 K"), q("300 K")).to("1/K").magnitude == 8.3e-6
    with pytest.raises(OutsideValidRange, match="233.15 K to 293.15 K is inside none"):
        N_BK7.cte_over(q("233.15 K"), q("293.15 K"))
    lens = {
        "dn_dt": q("1.6e-6 1/K"),
        "focal_length": q("100 mm"),
        "f_number": 4.0,
        "wavelength": q("550 nm"),
        "housing_cte": q("1.2e-6 1/K"),
        "housing_length": q("100 mm"),
    }
    inside = N_BK7.athermal_focus("focus", **lens, low=q("253.15 K"), high=q("293.15 K"))
    assert inside.status is CheckStatus.PASS
    assert inside.detail == _screen("1.2e-6 1/K").detail
    outside = N_BK7.athermal_focus("focus", **lens, low=q("233.15 K"), high=q("293.15 K"))
    assert outside.status is CheckStatus.NOT_EVALUATED
    assert "stated for 243 K to 343 K" in outside.detail


def test_a_ranged_property_needs_a_range_and_a_source() -> None:
    from anvilate.analysis.optomechanics import RangedProperty

    with pytest.raises(ValidationError, match="runs low to high"):
        RangedProperty(value=q("1e-6 1/K"), low=q("300 K"), high=q("200 K"), source="s")
    with pytest.raises(ValidationError, match="must state where it came from"):
        RangedProperty(value=q("1e-6 1/K"), low=q("200 K"), high=q("300 K"), source=" ")


def _µrad(value: float) -> Quantity:
    return Quantity(magnitude=value, unit="µrad")


def test_common_mode_motion_is_named_and_left_out_of_the_boresight() -> None:
    from anvilate.analysis.optomechanics import boresight_scorecard
    from anvilate.budget import CombinationRule

    direct = {"housing tilt": _µrad(80), "fold mirror": _µrad(30)}
    injected = {"housing tilt": _µrad(80), "combiner mount": _µrad(40)}
    rss = boresight_scorecard(
        "overlay",
        first_path=direct,
        second_path=injected,
        allowance=_µrad(60),
        rule=CombinationRule.RSS,
    )
    # √(30² + 40²): the 80 µrad housing tilt moves both paths and is not overlay error.
    assert rss.status is CheckStatus.PASS
    assert rss.comparison is not None and rss.comparison.measured.magnitude == pytest.approx(50)
    assert "common-mode, excluded: housing tilt" in rss.detail
    assert "combiner mount (second path only)" in rss.detail
    worst = boresight_scorecard(
        "overlay",
        first_path=direct,
        second_path=injected,
        allowance=_µrad(60),
        rule=CombinationRule.WORST_CASE,
    )
    assert worst.status is CheckStatus.FAIL
    assert "by worst case 70.0 µrad" in worst.detail
    # A shared contributor that moves the paths unequally enters as its difference.
    skewed = {**injected, "housing tilt": _µrad(95)}
    unequal = boresight_scorecard(
        "overlay",
        first_path=direct,
        second_path=skewed,
        allowance=_µrad(60),
        rule=CombinationRule.WORST_CASE,
    )
    assert unequal.comparison is not None
    assert unequal.comparison.measured.magnitude == pytest.approx(15 + 30 + 40)


def test_one_path_is_not_a_boresight() -> None:
    from anvilate.analysis.optomechanics import boresight_scorecard
    from anvilate.budget import CombinationRule

    entry = boresight_scorecard(
        "overlay",
        first_path={"housing tilt": _µrad(80)},
        second_path=None,
        allowance=_µrad(60),
        rule=CombinationRule.RSS,
    )
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "the second path is not declared" in entry.detail
    with pytest.raises(ValueError, match="must be an angle"):
        boresight_scorecard(
            "overlay",
            first_path={"tilt": q("80 mm")},
            second_path={"tilt": _µrad(1)},
            allowance=_µrad(60),
            rule=CombinationRule.RSS,
        )


def test_an_internal_source_raises_the_temperature_the_focus_screen_sees() -> None:
    """Task 10.2: the rise is consumed along a chain, not assumed to be ambient."""
    from anvilate.analysis.optomechanics import enclosure_rise_scorecard
    from anvilate.dependency import (
        ChainResult,
        CheckNode,
        Consumes,
        DependencyGraph,
        Output,
        run_chain,
    )

    sources = {"display": q("3 W"), "driver": q("1.5 W")}
    graph = DependencyGraph(
        nodes=(
            CheckNode(
                id="lens focus",
                consumes=(
                    Consumes(
                        upstream="internal rise",
                        output="rise",
                        parameter="temperature_change",
                        dimension="[temperature]",
                    ),
                ),
            ),
            CheckNode(
                id="internal rise", produces=(Output(name="rise", dimension="[temperature]"),)
            ),
        )
    )

    def run_check(check: str, inputs):  # type: ignore[no-untyped-def]
        if check == "internal rise":
            entry = enclosure_rise_scorecard(
                check, dissipations=sources, allowed_rise=q("20 K"), thermal_resistance=q("2.5 K/W")
            )
            assert entry.comparison is not None
            return ChainResult(
                check=check, entry=entry, outputs={"rise": entry.comparison.measured}
            )
        entry = athermal_focus_scorecard(
            check,
            **_LENS,
            f_number=4.0,
            wavelength=q("550 nm"),
            housing_cte=q("23.1e-6 1/K"),
            housing_length=q("100 mm"),
            temperature_change=inputs["temperature_change"],
        )
        return ChainResult(check=check, entry=entry)

    run = run_chain(graph, run_check)
    focus = {entry.name: entry for entry in run.card().entries}["lens focus"]
    # 4.5 W through 2.5 K/W is 11.25 K, and the focus screen was handed exactly that.
    assert "internal rise.rise = 11.25 K" in focus.detail
    direct = _screen("23.1e-6 1/K").comparison
    assert focus.comparison is not None and direct is not None
    assert focus.comparison.measured.magnitude == pytest.approx(
        direct.measured.magnitude * 11.25 / 40
    )


def test_a_sealed_volume_does_not_shed_heat_by_assumption() -> None:
    from anvilate.analysis.optomechanics import enclosure_rise_scorecard

    entry = enclosure_rise_scorecard(
        "rise", dissipations={"display": q("3 W")}, allowed_rise=q("10 K")
    )
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "display 3 W dissipates inside the enclosure and no heat path" in entry.detail
    with pytest.raises(ValueError, match="at least one dissipating source"):
        enclosure_rise_scorecard("rise", dissipations={}, allowed_rise=q("10 K"))


def _shock(shape: str, duration: str = "11 ms"):  # type: ignore[no-untyped-def]
    from anvilate.analysis.optomechanics import ShockEnvironment, ShockPulse

    return ShockEnvironment(
        peak_acceleration=30.0,
        pulse_duration=q(duration),
        shape=ShockPulse(shape),
        axis="optical axis",
    )


@pytest.mark.parametrize("frequency", ["30 Hz", "72.7 Hz", "300 Hz", "2000 Hz"])
def test_a_lightly_damped_half_sine_reproduces_the_closed_form_amplification(
    frequency: str,
) -> None:
    """The numerical response anchored to the exact undamped Duhamel solution."""
    from anvilate.analysis.dynamics import half_sine_shock_amplification

    numerical = _shock("half_sine").amplification(
        natural_frequency=q(frequency), quality_factor=1e6
    )
    exact = half_sine_shock_amplification(pulse_duration=q("11 ms"), natural_frequency=q(frequency))
    assert numerical == pytest.approx(exact, rel=1e-4)


def test_a_long_square_pulse_is_a_step_and_doubles() -> None:
    step = _shock("square", "100 ms").amplification(
        natural_frequency=q("200 Hz"), quality_factor=1e6
    )
    assert step == pytest.approx(2.0, rel=1e-4)


def test_damping_trims_the_peak_and_the_equivalent_static_load_is_a_times_the_peak() -> None:
    shock = _shock("half_sine")
    undamped = shock.amplification(natural_frequency=q("72.7 Hz"), quality_factor=1e6)
    damped = shock.amplification(natural_frequency=q("72.7 Hz"), quality_factor=10.0)
    assert damped < undamped
    assert shock.equivalent_static_acceleration(
        natural_frequency=q("72.7 Hz"), quality_factor=10.0
    ) == pytest.approx(30.0 * damped)
    assert str(shock) == "30 g half sine over 11 ms along optical axis"
    with pytest.raises(ValueError, match="quality_factor must exceed 0.5"):
        shock.amplification(natural_frequency=q("72.7 Hz"), quality_factor=0.5)


def test_a_shock_states_its_shape_and_duration() -> None:
    from anvilate.analysis.optomechanics import ShockEnvironment

    with pytest.raises(ValidationError):
        ShockEnvironment(peak_acceleration=30.0, pulse_duration=q("11 ms"), axis="z")  # type: ignore[call-arg]
    with pytest.raises(ValidationError, match="at least once"):
        ShockEnvironment(
            peak_acceleration=30.0, pulse_duration=q("11 ms"), shape="square", axis="z", cycles=0
        )
    sawtooth = _shock("terminal_peak_sawtooth").amplification(
        natural_frequency=q("300 Hz"), quality_factor=1e6
    )
    assert 0.9 < sawtooth < 1.5


def _prescription(**fields: object):  # type: ignore[no-untyped-def]
    from anvilate.analysis.optomechanics import Prescription, SurfaceDeformation

    declared: dict[str, object] = {
        "tool": "Zemax OpticStudio",
        "tool_version": "2024 R1",
        "effective_focal_length": q("100 mm"),
        "f_number": 4.0,
        "wavelength": q("550 nm"),
        "deformations": (
            SurfaceDeformation(surface="fold mirror", rms=q("8 nm"), reflective=True),
            SurfaceDeformation(
                surface="L1 S1", rms=q("20 nm"), reflective=False, refractive_index=1.5168
            ),
        ),
    }
    declared.update(fields)
    return Prescription(**declared)  # type: ignore[arg-type]


def test_a_surface_deformation_becomes_wavefront_error_by_how_light_meets_it() -> None:
    from anvilate.analysis.optomechanics import SurfaceDeformation

    mirror = SurfaceDeformation(surface="M", rms=q("8 nm"), reflective=True)
    lens = SurfaceDeformation(surface="S", rms=q("20 nm"), reflective=False, refractive_index=1.5)
    assert mirror.wavefront_rms().to("nm").magnitude == pytest.approx(16.0)
    assert lens.wavefront_rms().to("nm").magnitude == pytest.approx(10.0)
    with pytest.raises(ValidationError, match="needs the index across it"):
        SurfaceDeformation(surface="S", rms=q("20 nm"), reflective=False)


def test_a_prescription_feeds_the_screens_and_is_named_in_their_verdicts() -> None:
    prescription = _prescription()
    focus = prescription.athermal_focus(
        "focus",
        refractive_index=1.5168,
        dn_dt=q("1.6e-6 1/K"),
        glass_cte=q("7.1e-6 1/K"),
        housing_cte=q("1.2e-6 1/K"),
        housing_length=q("100 mm"),
        temperature_change=q("40 K"),
    )
    assert focus.detail == (
        "defocus 11.2 µm vs depth of focus 17.6 µm — from Zemax OpticStudio 2024 R1"
    )
    wavefront = prescription.wavefront_budget(
        "wavefront", strehl_threshold=0.8, others={"alignment": q("20 nm")}
    )
    assert wavefront.comparison is not None
    # 2·8, 0.5168·20 and 20 nm, in quadrature.
    expected = (16.0**2 + (0.5168 * 20) ** 2 + 20.0**2) ** 0.5
    assert wavefront.comparison.measured.magnitude == pytest.approx(expected)


def test_an_input_the_export_does_not_carry_is_never_estimated() -> None:
    bare = _prescription(effective_focal_length=None, wavelength=None, deformations=())
    focus = bare.athermal_focus(
        "focus",
        refractive_index=1.5168,
        dn_dt=q("1.6e-6 1/K"),
        glass_cte=q("7.1e-6 1/K"),
        housing_cte=q("1.2e-6 1/K"),
        housing_length=q("100 mm"),
        temperature_change=q("40 K"),
    )
    assert focus.status is CheckStatus.NOT_EVALUATED
    assert "does not carry effective focal length, wavelength" in focus.detail
    wavefront = bare.wavefront_budget("wavefront", strehl_threshold=0.8)
    assert wavefront.status is CheckStatus.NOT_EVALUATED
    assert "surface deformations" in wavefront.detail


def _preload(**changes: str):  # type: ignore[no-untyped-def]
    from anvilate.analysis.optomechanics import preload_temperature_scorecard

    return preload_temperature_scorecard(
        "lens preload",
        preload=q("100 N"),
        axial_stiffness=q("5e7 N/m"),
        edge_thickness=q("5 mm"),
        glass_cte=q("7.1e-6 1/K"),
        cell_cte=q("23.6e-6 1/K"),
        max_preload=q("300 N"),
        cold_change=q(changes.get("cold", "-40 K")),
        hot_change=q(changes.get("hot", "30 K")),
    )


def test_an_aluminium_cell_loses_its_preload_hot_and_gains_it_cold() -> None:
    # k·(α_M − α_G)·t_E = 5e7 · 16.5e-6 · 0.005 = 4.125 N/K, by hand.
    loose = _preload()
    assert loose.status is CheckStatus.FAIL
    assert "hot: preload -23.8 N — the element comes loose" in loose.detail
    assert "cold 265.0 N" in loose.detail
    held = _preload(hot="20 K")
    assert held.status is CheckStatus.PASS
    assert "hot 17.5 N" in held.detail
    crushed = _preload(cold="-60 K", hot="10 K")
    assert crushed.status is CheckStatus.FAIL
    assert "cold: preload 347.5 N above the 300.0 N the seat may carry" in crushed.detail


def _contact(mount_radius: str, allowable: str = "7 MPa"):  # type: ignore[no-untyped-def]
    from anvilate.analysis.optomechanics import glass_contact_stress_scorecard

    return glass_contact_stress_scorecard(
        "retainer contact",
        preload=q("100 N"),
        contact_diameter=q("40 mm"),
        glass_radius=q("50 mm"),
        mount_radius=q(mount_radius),
        glass_modulus=q("82 GPa"),
        glass_poisson=0.206,
        mount_modulus=q("69 GPa"),
        mount_poisson=0.33,
        allowable_tensile_stress=q(allowable),
    )


def test_a_sharp_retainer_edge_overstresses_the_glass_and_a_toroid_does_not() -> None:
    from math import pi, sqrt

    sharp = _contact("0.5 mm")
    # p = 100/(π·0.04); 1/R = 1/0.05 + 1/0.0005; E* from both materials; σ_T = (1 − 2ν)/3·p₀.
    line_load = 100 / (pi * 0.04)
    radius = 1 / (1 / 0.05 + 1 / 0.0005)
    modulus = 1 / ((1 - 0.206**2) / 82e9 + (1 - 0.33**2) / 69e9)
    tensile = (1 - 2 * 0.206) / 3 * sqrt(line_load * modulus / (pi * radius))
    assert sharp.comparison is not None
    assert sharp.comparison.measured.to("Pa").magnitude == pytest.approx(tensile)
    assert sharp.status is CheckStatus.FAIL
    assert "Weibull statistics" in sharp.detail and "not a strength" in sharp.detail
    toroid = _contact("50 mm")
    assert toroid.comparison is not None
    assert toroid.comparison.measured.magnitude < sharp.comparison.measured.magnitude / 5
    assert toroid.status is CheckStatus.PASS


def test_a_concave_seat_flatter_than_the_glass_is_refused() -> None:
    with pytest.raises(ValueError, match="flatter than the glass"):
        _contact("-40 mm")
