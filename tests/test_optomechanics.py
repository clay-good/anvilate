"""A lens kept in focus across temperature: depth of focus, thermal focal shift, defocus."""

from __future__ import annotations

import pytest

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

    # Air sealed at 25 °C and 50% relative humidity condenses below 13.9 °C (ASHRAE).
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
