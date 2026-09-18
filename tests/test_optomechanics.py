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
