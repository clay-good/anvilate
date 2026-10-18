"""Gerard's crippling method, anchored to NACA TN 3784's own restatements of it.

TN 3784 works no complete numerical example, but it states three of its general forms a
second time for a specific section, which the general form must reproduce: the formed
angle (eq. 54, β 0.665 against Table 13's 0.66), the square tube (eq. 51, β 1.42 against
Table 15's 1.4), and the two-corner cutoff (A8, 2(t/b_w)^(1/3) from A7 at β = 3.6).
Everything else is a hand calculation with its intermediates stated.
"""

from __future__ import annotations

import pytest

from anvilate.analysis.crippling import CripplingSection, gerard_crippling_stress
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

_E = Quantity(magnitude=72_000.0, unit="MPa")
_FCY = Quantity(magnitude=345.0, unit="MPa")


def _mm(v: float) -> Quantity:
    return Quantity(magnitude=v, unit="mm")


def _mm2(v: float) -> Quantity:
    return Quantity(magnitude=v, unit="mm**2")


def test_a_formed_angle_matches_eq_54_within_its_beta():
    # An equal angle of legs b = 30, t = 1.6: A = 2bt = 96, f = 2, so f t²/A = t/b.
    result = gerard_crippling_stress(
        section=CripplingSection.FORMED_ANGLE, thickness=_mm(1.6), area=_mm2(96.0),
        compressive_yield=_FCY, elastic_modulus=_E, count=2, corner_yield_ratio=1.3,
    )  # fmt: skip
    eq54 = 0.665 * ((1.6 / 30) * (72_000 / 345) ** 0.5) ** 0.85
    assert result.beta == 0.66
    assert result.ratio == pytest.approx(eq54 * 0.66 / 0.665, rel=1e-12)
    assert result.ratio == pytest.approx(eq54, rel=0.008)
    assert result.cutoff == 0.92


def test_a_square_tube_matches_eq_51_within_its_beta():
    # b = 50, t = 1.2, four corners: A = 4bt = 240, c t²/A = t/b
    result = gerard_crippling_stress(
        section=CripplingSection.EXTRUDED_SQUARE_TUBE, thickness=_mm(1.2), area=_mm2(240.0),
        compressive_yield=_FCY, elastic_modulus=_E, count=4,
    )  # fmt: skip
    eq51 = 1.42 * ((1.2 / 50) * (72_000 / 345) ** 0.5) ** 0.85
    assert result.ratio == pytest.approx(eq51 * 1.4 / 1.42, rel=1e-12)
    assert result.ratio == pytest.approx(eq51, rel=0.015)
    assert result.cutoff == 0.7


def test_the_two_corner_cutoff_reduces_to_a8_at_beta_3_6():
    result = gerard_crippling_stress(
        section=CripplingSection.EXTRUDED_TWO_CORNER, thickness=_mm(1.6), area=_mm2(200.0),
        compressive_yield=_FCY, elastic_modulus=_E, count=2, web_width=_mm(40.0),
    )  # fmt: skip
    assert result.cutoff == pytest.approx(2 * (1.6 / 40) ** (1 / 3), rel=2e-3)


def test_a_formed_z_by_hand():
    # t 1.6, A 200, E/σcy = 208.70: t²/A × (E/σcy)^(1/3) = 0.0128 × 5.9319 = 0.075928;
    # ^0.75 = 0.14464; × β 3.3 = 0.47731; σ̄f = 164.67 MPa
    result = gerard_crippling_stress(
        section=CripplingSection.FORMED_TWO_CORNER, thickness=_mm(1.6), area=_mm2(200.0),
        compressive_yield=_FCY, elastic_modulus=_E, count=2, web_width=_mm(40.0),
    )  # fmt: skip
    assert result.ratio == pytest.approx(0.47731, abs=2e-5)
    assert result.stress == pytest.approx(164.67, abs=0.01)
    # (3.3/2.14 × 0.04^0.25)^(4/3) = 0.689625^(4/3) = 0.60928
    assert result.cutoff == pytest.approx(0.60928, abs=1e-5)
    assert "NACA TN 3784 Table 14" in str(result)


@pytest.mark.parametrize(("declared", "beta"), [(1.0, 3.3), (1.15, 3.5), (1.2, 3.8), (2.0, 4.0)])
def test_beta_is_the_listed_row_at_or_below_the_declared_corner_yield(declared, beta):
    result = gerard_crippling_stress(
        section=CripplingSection.FORMED_TWO_CORNER, thickness=_mm(1.0), area=_mm2(200.0),
        compressive_yield=_FCY, elastic_modulus=_E, count=2, corner_yield_ratio=declared,
        web_width=_mm(40.0),
    )  # fmt: skip
    assert result.beta == beta


def test_above_the_cutoff_is_refused_naming_eq_73():
    with pytest.raises(RefusalError, match="eq. 73"):
        gerard_crippling_stress(
            section=CripplingSection.EXTRUDED_SQUARE_TUBE, thickness=_mm(4.0),
            area=_mm2(320.0), compressive_yield=_FCY, elastic_modulus=_E, count=4,
        )  # fmt: skip


def test_a_two_corner_section_needs_its_web():
    with pytest.raises(RefusalError, match="web_width"):
        gerard_crippling_stress(
            section=CripplingSection.FORMED_TWO_CORNER, thickness=_mm(1.6), area=_mm2(200.0),
            compressive_yield=_FCY, elastic_modulus=_E, count=2,
        )  # fmt: skip


@pytest.mark.parametrize(
    ("field", "value"),
    [("thickness", _mm(0.0)), ("area", _mm2(float("nan"))), ("compressive_yield", _mm(1.0)),
     ("corner_yield_ratio", 0.9), ("count", 0), ("count", True)],
)  # fmt: skip
def test_bad_inputs_are_refused_by_name(field, value):
    args = {
        "section": CripplingSection.FORMED_ANGLE, "thickness": _mm(1.6), "area": _mm2(96.0),
        "compressive_yield": _FCY, "elastic_modulus": _E, "count": 2,
    } | {field: value}  # fmt: skip
    with pytest.raises(ValueError, match=field):
        gerard_crippling_stress(**args)


def test_a_thick_section_is_not_a_crippling_case():
    with pytest.raises(RefusalError, match="not thin-walled"):
        gerard_crippling_stress(
            section=CripplingSection.FORMED_ANGLE, thickness=_mm(10.0), area=_mm2(150.0),
            compressive_yield=_FCY, elastic_modulus=_E, count=2,
        )  # fmt: skip
