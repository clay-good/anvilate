"""Tests for the T1 analytical checks, against hand-computed worked examples."""

from __future__ import annotations

import pytest

from anvilate.analysis import (
    ColumnEnd,
    bolt_preload_from_torque,
    cantilever_end_load,
    euler_buckling_load,
    polar_second_moment_solid,
    rectangular_second_moment,
    shaft_torsional_stress,
    shaft_twist_angle,
    simply_supported_center_load,
    torque_for_preload,
)
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def test_rectangular_second_moment_matches_bh3_over_12():
    # 20 mm wide x 10 mm tall: I = 20 * 10^3 / 12 = 1666.67 mm^4.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    assert inertia.to("mm**4").magnitude == pytest.approx(1666.6667, rel=1e-4)


def test_cantilever_end_load_matches_worked_example():
    # A 500 mm steel cantilever, 20 x 10 mm rectangular section, 100 N at the tip.
    # By hand: I = 1666.67 mm^4, c = 5 mm, E = 200 GPa.
    #   sigma = M*c/I = (100 N * 500 mm) * 5 mm / 1666.67 mm^4 = 150 MPa
    #   delta = F*L^3/(3*E*I) = 100*500^3 / (3*200000*1666.67) = 12.5 mm
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = cantilever_end_load(
        force=_q("100 N"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(150.0, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(12.5, rel=1e-4)


def test_cantilever_units_carry_through_customary_inputs():
    # The same physics expressed in mixed units resolves identically: the Pint
    # arithmetic converts, so a 0.5 m length gives the same 150 MPa / 12.5 mm.
    inertia = rectangular_second_moment(_q("2 cm"), _q("1 cm"))
    result = cantilever_end_load(
        force=_q("100 N"),
        length=_q("0.5 m"),
        second_moment=inertia,
        extreme_fibre=_q("0.5 cm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(150.0, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(12.5, rel=1e-4)


def test_simply_supported_center_load_matches_worked_example():
    # Same 500 mm, 20 x 10 mm steel beam, 100 N at mid-span, both ends supported.
    # By hand: M = P*L/4 = 12500 N*mm, so sigma = M*c/I = 12500*5/1666.67 = 37.5 MPa;
    #   delta = P*L^3/(48*E*I) = 100*500^3 / (48*200000*1666.67) = 0.78125 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = simply_supported_center_load(
        force=_q("100 N"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(37.5, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.78125, rel=1e-4)


def test_simply_supported_is_stiffer_and_lower_stress_than_cantilever():
    # For the same span, section, and load, a simply-supported beam carries far
    # less stress and deflects far less than a cantilever — a sanity relation.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    ss = simply_supported_center_load(**kw)
    cant = cantilever_end_load(**kw)
    assert ss.max_bending_stress.to("MPa").magnitude < cant.max_bending_stress.to("MPa").magnitude
    assert ss.max_deflection.to("mm").magnitude < cant.max_deflection.to("mm").magnitude


def test_bending_safety_factor_against_yield():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = cantilever_end_load(
        force=_q("100 N"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    # 150 MPa peak stress against 6061-T6's 276 MPa yield → SF ~ 1.84.
    assert result.bending_safety_factor(_q("276 MPa")) == pytest.approx(1.84, rel=1e-3)


def test_euler_buckling_load_matches_worked_example():
    # Pinned-pinned steel column: E=200 GPa, I=1666.67 mm^4, L=500 mm, K=1.
    #   P_cr = pi^2 * E * I / (K*L)^2 = pi^2 * 200000 * 1666.67 / 500^2 ~ 13159 N.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    p_cr = euler_buckling_load(
        elastic_modulus=_q("200 GPa"),
        second_moment=inertia,
        length=_q("500 mm"),
        effective_length_factor=1.0,
    )
    assert p_cr.to("N").magnitude == pytest.approx(13159.5, rel=1e-4)


def test_euler_buckling_scales_with_end_condition():
    # A fixed-free column (K=2) buckles at 1/4 the pinned-pinned load (K squared).
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "elastic_modulus": _q("200 GPa"),
        "second_moment": inertia,
        "length": _q("500 mm"),
    }
    pinned = euler_buckling_load(**kw, effective_length_factor=ColumnEnd.PINNED_PINNED.factor())
    fixed_free = euler_buckling_load(**kw, effective_length_factor=ColumnEnd.FIXED_FREE.factor())
    assert fixed_free.to("N").magnitude == pytest.approx(pinned.to("N").magnitude / 4, rel=1e-6)


def test_column_end_factors():
    assert ColumnEnd.PINNED_PINNED.factor() == 1.0
    assert ColumnEnd.FIXED_FIXED.factor() == 0.5
    assert ColumnEnd.FIXED_FREE.factor() == 2.0


def test_euler_buckling_rejects_bad_inputs():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    with pytest.raises(ValueError, match="elastic_modulus must be a"):
        euler_buckling_load(
            elastic_modulus=_q("200 mm"),  # not a pressure
            second_moment=inertia,
            length=_q("500 mm"),
        )
    with pytest.raises(ValueError, match="effective_length_factor must be positive"):
        euler_buckling_load(
            elastic_modulus=_q("200 GPa"),
            second_moment=inertia,
            length=_q("500 mm"),
            effective_length_factor=0.0,
        )


def test_bolt_preload_from_torque_matches_worked_example():
    # 10 N*m on an M8 (d=8 mm) at the as-received nut factor K=0.2:
    #   F = T/(K*d) = 10 / (0.2 * 0.008) = 6250 N.
    preload = bolt_preload_from_torque(
        torque=_q("10 N*m"),
        nominal_diameter=_q("8 mm"),
    )
    assert preload.to("N").magnitude == pytest.approx(6250.0, rel=1e-6)


def test_torque_preload_round_trips():
    # torque_for_preload inverts bolt_preload_from_torque exactly.
    preload = _q("6250 N")
    torque = torque_for_preload(preload=preload, nominal_diameter=_q("8 mm"))
    assert torque.to("N*m").magnitude == pytest.approx(10.0, rel=1e-6)
    back = bolt_preload_from_torque(torque=torque, nominal_diameter=_q("8 mm"))
    assert back.to("N").magnitude == pytest.approx(6250.0, rel=1e-6)


def test_bolt_torque_tension_rejects_bad_inputs():
    with pytest.raises(ValueError, match="torque must be a"):
        bolt_preload_from_torque(
            torque=_q("10 N"), nominal_diameter=_q("8 mm")
        )  # force, not torque
    with pytest.raises(ValueError, match="nut_factor must be positive"):
        bolt_preload_from_torque(torque=_q("10 N*m"), nominal_diameter=_q("8 mm"), nut_factor=0.0)


def test_polar_second_moment_solid_matches_pi_d4_over_32():
    # d=20 mm: J = pi*20^4/32 = 15708 mm^4.
    j = polar_second_moment_solid(_q("20 mm"))
    assert j.to("mm**4").magnitude == pytest.approx(15707.96, rel=1e-4)


def test_shaft_torsional_stress_matches_worked_example():
    # 50 N*m through a 20 mm solid shaft: tau = 16*T/(pi*d^3)
    #   = 16*50 / (pi*0.02^3) = 31.83 MPa.
    tau = shaft_torsional_stress(torque=_q("50 N*m"), diameter=_q("20 mm"))
    assert tau.to("MPa").magnitude == pytest.approx(31.831, rel=1e-4)


def test_shaft_twist_angle_matches_worked_example():
    # 50 N*m over a 1 m, 20 mm steel shaft, G=77 GPa: theta = T*L/(G*J)
    #   = 50*1 / (77e9 * 1.5708e-8) = 0.04134 rad = 2.368 deg.
    theta = shaft_twist_angle(
        torque=_q("50 N*m"),
        length=_q("1 m"),
        diameter=_q("20 mm"),
        shear_modulus=_q("77 GPa"),
    )
    assert theta.to("degree").magnitude == pytest.approx(2.368, rel=1e-3)


def test_shaft_torsion_rejects_wrong_dimensions():
    with pytest.raises(ValueError, match="torque must be a"):
        shaft_torsional_stress(torque=_q("50 N"), diameter=_q("20 mm"))  # force, not torque


def test_cantilever_rejects_wrong_dimensions():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    # A mass passed as the force is caught by the dimension check.
    with pytest.raises(ValueError, match="force must be a"):
        cantilever_end_load(
            force=_q("100 kg"),
            length=_q("500 mm"),
            second_moment=inertia,
            extreme_fibre=_q("5 mm"),
            elastic_modulus=_q("200 GPa"),
        )
    # A length passed as the modulus (not a pressure) is caught too.
    with pytest.raises(ValueError, match="elastic_modulus must be a"):
        cantilever_end_load(
            force=_q("100 N"),
            length=_q("500 mm"),
            second_moment=inertia,
            extreme_fibre=_q("5 mm"),
            elastic_modulus=_q("200 mm"),
        )
