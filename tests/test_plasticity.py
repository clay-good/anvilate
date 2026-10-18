"""Plasticity corrections, anchored to the Ramberg-Osgood definitions they rest on.

NASA TM X-73306 §C2 defines F_0.7 and F_0.85 as the stresses where secant lines of slope
0.7E and 0.85E meet the curve. The curve must pass through both exactly, which is also
what shows the manual's printed strain equation (no 3/7) to be the misprint: it gives a
secant of 0.5E at F_0.7. The tangent modulus is checked against a numerical derivative of
the strain, and each buckling stress against the equation it solves.
"""

from __future__ import annotations

from math import log, pi, sqrt

import pytest

from anvilate.analysis.plasticity import (
    PlateEdge,
    RambergOsgood,
    plastic_column_buckling_stress,
    plastic_plate_buckling_stress,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity


def _mpa(v: float) -> Quantity:
    return Quantity(magnitude=v, unit="MPa")


def _curve() -> RambergOsgood:
    return RambergOsgood.from_secant_points(
        elastic_modulus=_mpa(72_400), f_07=_mpa(320), f_085=_mpa(300)
    )


def test_the_curve_passes_through_both_secant_points():
    curve = _curve()
    assert curve.secant_modulus(320) == pytest.approx(0.70 * 72_400, rel=1e-12)
    assert curve.secant_modulus(300) == pytest.approx(0.85 * 72_400, rel=1e-12)
    # n = 1 + ln(17/7)/ln(320/300) = 1 + 0.887303/0.064539 = 14.7484
    assert curve.n == pytest.approx(1 + log(17 / 7) / log(320 / 300), rel=1e-12)
    assert curve.n == pytest.approx(14.7484, abs=1e-4)


def test_the_printed_equation_without_3_7_misses_its_own_definition():
    # ε = f/E + (f/F_0.7)ⁿ·F_0.7/E at f = F_0.7 gives 2F_0.7/E: a secant of 0.5E, not 0.7E
    printed_secant = 320 / (320 / 72_400 + 320 / 72_400)
    assert printed_secant == pytest.approx(0.5 * 72_400)
    assert _curve().secant_modulus(320) != pytest.approx(printed_secant)


@pytest.mark.parametrize("stress", [100.0, 280.0, 320.0, 340.0])
def test_the_tangent_modulus_is_the_inverse_slope(stress):
    curve, h = _curve(), 1e-4
    slope = (curve.strain(stress + h) - curve.strain(stress - h)) / (2 * h)
    assert curve.tangent_modulus(stress) == pytest.approx(1 / slope, rel=1e-6)


def test_a_slender_column_buckles_at_euler():
    result = plastic_column_buckling_stress(curve=_curve(), slenderness=200)
    # Euler: π² × 72,400/200² = 17.864 MPa, far below F_0.7, where E_t = E to 1e-9
    assert result.elastic_stress == pytest.approx(pi**2 * 72_400 / 40_000, rel=1e-12)
    assert result.reduction == pytest.approx(1.0, abs=1e-9)


def test_a_stocky_column_solves_the_tangent_modulus_equation():
    curve = _curve()
    result = plastic_column_buckling_stress(curve=curve, slenderness=40)
    # Euler 446.6 MPa is above F_0.7; the root satisfies σ = π²E_t(σ)/λ²
    assert result.elastic_stress == pytest.approx(446.60, abs=0.01)
    assert result.stress == pytest.approx(pi**2 * curve.tangent_modulus(result.stress) / 1600,
                                          rel=1e-9)  # fmt: skip
    # below F_0.7 and well below Euler: 271.12 MPa, 0.607 of the elastic stress
    assert result.stress == pytest.approx(271.12, abs=0.01)
    assert result.reduction == pytest.approx(0.6071, abs=1e-4)
    assert "NASA TM X-73306" in str(result)


def test_rotational_restraint_eta_is_one_in_the_elastic_range():
    # E_t = E_s = E: (1/2)(1 + 0.5·√4) = 1
    result = plastic_plate_buckling_stress(
        curve=_curve(), elastic_stress=_mpa(50), edge=PlateEdge.ROTATIONALLY_RESTRAINED,
        poisson=0.33,
    )  # fmt: skip
    assert result.reduction == pytest.approx(1.0, abs=1e-9)
    assert result.poisson_term_taken_as_one and "ν_e taken as ν" in str(result)


@pytest.mark.parametrize("edge", list(PlateEdge))
def test_a_plate_above_the_knee_solves_its_eta_equation(edge):
    curve = _curve()
    result = plastic_plate_buckling_stress(
        curve=curve, elastic_stress=_mpa(500), edge=edge, poisson=0.33, plastic_poisson=0.5
    )
    es, et = curve.secant_modulus(result.stress), curve.tangent_modulus(result.stress)
    term = (1 - 0.25) / (1 - 0.33**2)
    if edge is PlateEdge.ROTATIONALLY_RESTRAINED:
        eta = es / (2 * 72_400) * (1 + 0.5 * sqrt(1 + 3 * et / es)) * term
    else:
        eta = es / 72_400 * term
    assert result.stress == pytest.approx(eta * 500, rel=1e-9)
    assert not result.poisson_term_taken_as_one


def test_restrained_plates_lose_more_than_hinged_flanges():
    # (1/2)(1 + 0.5√(1 + 3E_t/E_s)) ≤ 1 because E_t ≤ E_s, so the restrained η carries a
    # tangent-modulus penalty the hinged flange's E_s/E does not
    args = {"curve": _curve(), "elastic_stress": _mpa(500), "poisson": 0.33}
    hinged = plastic_plate_buckling_stress(**args, edge=PlateEdge.HINGED_FLANGE)
    restrained = plastic_plate_buckling_stress(**args, edge=PlateEdge.ROTATIONALLY_RESTRAINED)
    assert restrained.stress < hinged.stress


def test_f085_must_be_below_f07():
    with pytest.raises(RefusalError, match="F_0.85"):
        RambergOsgood.from_secant_points(
            elastic_modulus=_mpa(72_400), f_07=_mpa(300), f_085=_mpa(320)
        )


@pytest.mark.parametrize("value", [0.0, -10.0, float("nan"), float("inf")])
def test_slenderness_must_be_positive_and_finite(value):
    with pytest.raises(ValueError, match="slenderness"):
        plastic_column_buckling_stress(curve=_curve(), slenderness=value)


@pytest.mark.parametrize(("field", "value"), [("poisson", 0.6), ("plastic_poisson", -0.1)])
def test_a_poisson_ratio_out_of_range_is_refused(field, value):
    args = {"curve": _curve(), "elastic_stress": _mpa(500), "edge": PlateEdge.HINGED_FLANGE,
            "poisson": 0.33} | {field: value}  # fmt: skip
    with pytest.raises(RefusalError, match=field):
        plastic_plate_buckling_stress(**args)


def test_a_curve_copy_cannot_lose_its_hardening():
    with pytest.raises(ValueError):
        _curve().model_copy(update={"n": 0.5})


def test_the_hand_methods_page_states_the_misprint_as_the_code_measures_it():
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "structural-hand-methods.md").read_text()
    assert "the secant modulus at F_0.7 is 0.5E, not 0.7E" in page
