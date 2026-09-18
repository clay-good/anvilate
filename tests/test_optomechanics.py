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
