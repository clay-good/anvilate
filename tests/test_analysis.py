"""Tests for the T1 analytical checks, against hand-computed worked examples."""

from __future__ import annotations

import pytest

from anvilate.analysis import (
    SHEAR_FORM_CIRCULAR,
    SHEAR_FORM_RECTANGULAR,
    ColumnEnd,
    axial_stress,
    bearing_stress,
    bolt_preload_from_torque,
    bolt_shear_stress,
    cantilever_end_load,
    cantilever_uniform_load,
    circular_area,
    circular_second_moment,
    combine_axial_bending,
    deflection_scorecard,
    euler_buckling_load,
    euler_critical_stress,
    goodman_safety_factor,
    goodman_scorecard,
    hollow_circular_second_moment,
    hollow_shaft_torsional_stress,
    max_transverse_shear_stress,
    polar_second_moment_hollow,
    polar_second_moment_solid,
    radius_of_gyration,
    rectangular_second_moment,
    shaft_torsional_stress,
    shaft_twist_angle,
    simply_supported_center_load,
    simply_supported_uniform_load,
    slenderness_ratio,
    strength_scorecard,
    thin_wall_cylinder,
    torque_for_preload,
    von_mises_bending_torsion,
    von_mises_plane_stress,
    yield_safety_factor,
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


def test_cantilever_uniform_load_matches_worked_example():
    # 1 N/mm UDL over a 500 mm, 20x10 mm steel cantilever:
    #   M_max = w*L^2/2 = 125000 N*mm -> sigma = M*c/I = 125000*5/1666.67 = 375 MPa;
    #   delta = w*L^4/(8*E*I) = 1*500^4/(8*200000*1666.67) = 23.44 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = cantilever_uniform_load(
        distributed_load=_q("1 N/mm"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(375.0, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(23.4375, rel=1e-4)
    # A cantilever under the same UDL is far more stressed than a simply-supported
    # span (M = wL^2/2 vs wL^2/8 -> 4x).
    ss = simply_supported_uniform_load(
        distributed_load=_q("1 N/mm"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(
        4 * ss.max_bending_stress.to("MPa").magnitude, rel=1e-6
    )


def test_simply_supported_uniform_load_matches_worked_example():
    # 1 N/mm UDL over a 500 mm, 20x10 mm steel beam:
    #   M_max = w*L^2/8 = 31250 N*mm -> sigma = M*c/I = 31250*5/1666.67 = 93.75 MPa;
    #   delta = 5*w*L^4/(384*E*I) = 5*1*500^4/(384*200000*1666.67) = 2.441 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = simply_supported_uniform_load(
        distributed_load=_q("1 N/mm"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(93.75, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(2.4414, rel=1e-4)


def test_simply_supported_uniform_load_rejects_point_load_units():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    with pytest.raises(ValueError, match="distributed_load must be a"):
        simply_supported_uniform_load(
            distributed_load=_q("100 N"),  # a force, not force-per-length
            length=_q("500 mm"),
            second_moment=inertia,
            extreme_fibre=_q("5 mm"),
            elastic_modulus=_q("200 GPa"),
        )


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


def test_circular_second_moments_solid_and_hollow():
    # Solid d=20 mm: I = pi*20^4/64 = 7854 mm^4 (half the polar J = 15708).
    solid = circular_second_moment(_q("20 mm"))
    assert solid.to("mm**4").magnitude == pytest.approx(7853.98, rel=1e-4)
    # Hollow D=20, d=10: I = pi*(20^4-10^4)/64 = 7363 mm^4, less than solid.
    hollow = hollow_circular_second_moment(outer_diameter=_q("20 mm"), inner_diameter=_q("10 mm"))
    assert hollow.to("mm**4").magnitude == pytest.approx(7363.1, rel=1e-4)
    assert hollow.to("mm**4").magnitude < solid.to("mm**4").magnitude


def test_circular_second_moment_feeds_a_bending_check():
    # A round-bar cantilever: I from the circular helper, c = radius = 10 mm.
    inertia = circular_second_moment(_q("20 mm"))
    result = cantilever_end_load(
        force=_q("100 N"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("10 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    # sigma = M*c/I = (100*500)*10 / 7853.98 = 63.66 MPa.
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(63.662, rel=1e-4)


def test_max_transverse_shear_stress_rectangular_and_circular():
    # 10 kN shear over a 200 mm^2 section: average V/A = 50 MPa; peak is 1.5x
    # (rectangular) = 75 MPa or 4/3x (circular) = 66.67 MPa.
    rect = max_transverse_shear_stress(
        shear_force=_q("10 kN"), area=_q("200 mm**2"), form_factor=SHEAR_FORM_RECTANGULAR
    )
    assert rect.to("MPa").magnitude == pytest.approx(75.0, rel=1e-6)
    circ = max_transverse_shear_stress(
        shear_force=_q("10 kN"), area=_q("200 mm**2"), form_factor=SHEAR_FORM_CIRCULAR
    )
    assert circ.to("MPa").magnitude == pytest.approx(66.667, rel=1e-4)
    # The rectangular default matches the explicit rectangular form factor.
    assert max_transverse_shear_stress(shear_force=_q("10 kN"), area=_q("200 mm**2")).to(
        "MPa"
    ).magnitude == pytest.approx(75.0, rel=1e-6)


def test_max_transverse_shear_rejects_bad_inputs():
    with pytest.raises(ValueError, match="form_factor must be positive"):
        max_transverse_shear_stress(shear_force=_q("10 kN"), area=_q("200 mm**2"), form_factor=0.0)


def test_deflection_scorecard_pass_fail_and_not_evaluated():
    from anvilate.scorecard import CheckStatus

    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = cantilever_end_load(
        force=_q("100 N"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )  # 12.5 mm tip deflection
    ok = deflection_scorecard("tip", deflection=result.max_deflection, limit=_q("15 mm"))
    assert ok.status is CheckStatus.PASS
    bad = deflection_scorecard("tip", deflection=result.max_deflection, limit=_q("10 mm"))
    assert bad.status is CheckStatus.FAIL
    # No silent green: no limit set -> NOT_EVALUATED, not a pass.
    none = deflection_scorecard("tip", deflection=result.max_deflection, limit=None)
    assert none.status is CheckStatus.NOT_EVALUATED
    assert not none.passed


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


def test_radius_of_gyration_and_slenderness():
    # 20 x 10 mm section: A = 200 mm^2, I = 1666.67 mm^4, r = sqrt(I/A) = 2.887 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    r = radius_of_gyration(second_moment=inertia, area=_q("200 mm**2"))
    assert r.to("mm").magnitude == pytest.approx(2.88675, rel=1e-4)
    # A 500 mm pinned column: lambda = K*L/r = 500/2.887 = 173.2.
    lam = slenderness_ratio(effective_length=_q("500 mm"), radius_of_gyration=r)
    assert lam == pytest.approx(173.205, rel=1e-4)


def test_euler_critical_stress_equals_load_over_area():
    # sigma_cr = pi^2*E/lambda^2 must equal P_cr / A for the same column.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    area = _q("200 mm**2")
    r = radius_of_gyration(second_moment=inertia, area=area)
    lam = slenderness_ratio(effective_length=_q("500 mm"), radius_of_gyration=r)
    sigma_cr = euler_critical_stress(elastic_modulus=_q("200 GPa"), slenderness_ratio=lam)
    p_cr = euler_buckling_load(
        elastic_modulus=_q("200 GPa"), second_moment=inertia, length=_q("500 mm")
    )
    # sigma_cr ~ 65.8 MPa; P_cr/A = 13159.5 N / 200 mm^2 = 65.8 MPa.
    assert sigma_cr.to("MPa").magnitude == pytest.approx(65.797, rel=1e-3)
    assert sigma_cr.to("MPa").magnitude == pytest.approx(
        p_cr.to("N").magnitude / area.to("mm**2").magnitude, rel=1e-4
    )


def test_euler_critical_stress_rejects_bad_slenderness():
    with pytest.raises(ValueError, match="slenderness_ratio must be positive"):
        euler_critical_stress(elastic_modulus=_q("200 GPa"), slenderness_ratio=0.0)


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


def test_bolt_shear_stress_single_and_double():
    # 10 kN through an 8 mm bolt: A = pi*8^2/4 = 50.27 mm^2.
    #   single shear tau = 10000/50.27 = 198.9 MPa; double shear halves it.
    single = bolt_shear_stress(force=_q("10 kN"), diameter=_q("8 mm"))
    assert single.to("MPa").magnitude == pytest.approx(198.94, rel=1e-4)
    double = bolt_shear_stress(force=_q("10 kN"), diameter=_q("8 mm"), shear_planes=2)
    assert double.to("MPa").magnitude == pytest.approx(single.to("MPa").magnitude / 2, rel=1e-9)


def test_bolt_shear_rejects_bad_planes():
    with pytest.raises(ValueError, match="shear_planes must be a positive integer"):
        bolt_shear_stress(force=_q("10 kN"), diameter=_q("8 mm"), shear_planes=0)


def test_bearing_stress_matches_worked_example():
    # 10 kN through an 8 mm pin bearing on a 5 mm plate: sigma = F/(d*t)
    #   = 10000 / (8*5) = 250 MPa.
    sigma = bearing_stress(force=_q("10 kN"), diameter=_q("8 mm"), thickness=_q("5 mm"))
    assert sigma.to("MPa").magnitude == pytest.approx(250.0, rel=1e-6)


def test_bearing_stress_rejects_bad_inputs():
    with pytest.raises(ValueError, match="thickness must be positive"):
        bearing_stress(force=_q("10 kN"), diameter=_q("8 mm"), thickness=_q("0 mm"))
    with pytest.raises(ValueError, match="force must be a"):
        bearing_stress(force=_q("10 mm"), diameter=_q("8 mm"), thickness=_q("5 mm"))


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


def test_polar_second_moment_hollow_and_stress():
    # D=20 mm, d=10 mm tube: J = pi*(20^4 - 10^4)/32 = 14726 mm^4.
    j = polar_second_moment_hollow(outer_diameter=_q("20 mm"), inner_diameter=_q("10 mm"))
    assert j.to("mm**4").magnitude == pytest.approx(14726.2, rel=1e-4)
    # 50 N*m through the tube: tau = T*(D/2)/J = 50000*10/14726 = 33.95 MPa.
    tau = hollow_shaft_torsional_stress(
        torque=_q("50 N*m"), outer_diameter=_q("20 mm"), inner_diameter=_q("10 mm")
    )
    assert tau.to("MPa").magnitude == pytest.approx(33.95, rel=1e-3)
    # A tube carries more stress than a solid shaft of the same OD (less material).
    solid = shaft_torsional_stress(torque=_q("50 N*m"), diameter=_q("20 mm"))
    assert tau.to("MPa").magnitude > solid.to("MPa").magnitude


def test_hollow_shaft_rejects_inner_ge_outer():
    with pytest.raises(ValueError, match="must be non-negative and below"):
        polar_second_moment_hollow(outer_diameter=_q("20 mm"), inner_diameter=_q("20 mm"))


def test_shaft_torsion_rejects_wrong_dimensions():
    with pytest.raises(ValueError, match="torque must be a"):
        shaft_torsional_stress(torque=_q("50 N"), diameter=_q("20 mm"))  # force, not torque


def test_thin_wall_cylinder_matches_worked_example():
    # 2 MPa internal pressure, 100 mm radius, 5 mm wall:
    #   hoop = p*r/t = 2*100/5 = 40 MPa; longitudinal = p*r/(2t) = 20 MPa; r/t = 20.
    result = thin_wall_cylinder(
        pressure=_q("2 MPa"),
        radius=_q("100 mm"),
        wall_thickness=_q("5 mm"),
    )
    assert result.hoop_stress.to("MPa").magnitude == pytest.approx(40.0, rel=1e-6)
    assert result.longitudinal_stress.to("MPa").magnitude == pytest.approx(20.0, rel=1e-6)
    assert result.thin_wall_ratio == pytest.approx(20.0)
    # Hoop is exactly twice the longitudinal stress.
    assert result.hoop_stress.to("MPa").magnitude == pytest.approx(
        2 * result.longitudinal_stress.to("MPa").magnitude
    )
    # Governing (hoop) safety factor against a 250 MPa yield.
    assert result.bending_safety_factor(_q("250 MPa")) == pytest.approx(6.25, rel=1e-6)


def test_thin_wall_cylinder_rejects_bad_inputs():
    with pytest.raises(ValueError, match="pressure must be a"):
        thin_wall_cylinder(
            pressure=_q("2 mm"),  # not a pressure
            radius=_q("100 mm"),
            wall_thickness=_q("5 mm"),
        )
    with pytest.raises(ValueError, match="wall_thickness must be positive"):
        thin_wall_cylinder(
            pressure=_q("2 MPa"),
            radius=_q("100 mm"),
            wall_thickness=_q("0 mm"),
        )


def test_circular_area_matches_pi_d2_over_4():
    # d=20 mm: A = pi*20^2/4 = 314.16 mm^2.
    area = circular_area(_q("20 mm"))
    assert area.to("mm**2").magnitude == pytest.approx(314.159, rel=1e-4)


def test_axial_stress_worked_example_and_sign():
    # 10 kN tension over a 20 mm-diameter rod: sigma = F/A = 10000/314.16 = 31.83 MPa.
    area = circular_area(_q("20 mm"))
    tension = axial_stress(force=_q("10 kN"), area=area)
    assert tension.to("MPa").magnitude == pytest.approx(31.831, rel=1e-4)
    # Compression carries through as a negative stress.
    compression = axial_stress(force=_q("-10 kN"), area=area)
    assert compression.to("MPa").magnitude == pytest.approx(-31.831, rel=1e-4)


def test_axial_stress_rejects_wrong_dimensions():
    with pytest.raises(ValueError, match="area must be a"):
        axial_stress(force=_q("10 kN"), area=_q("20 mm"))  # a length, not an area


def test_goodman_safety_factor_worked_example():
    # sigma_a=100, sigma_m=50 MPa; Se=200, Su=400 MPa:
    #   1/n = 100/200 + 50/400 = 0.5 + 0.125 = 0.625 -> n = 1.6.
    n = goodman_safety_factor(
        alternating_stress=_q("100 MPa"),
        mean_stress=_q("50 MPa"),
        endurance_limit=_q("200 MPa"),
        ultimate_strength=_q("400 MPa"),
    )
    assert n == pytest.approx(1.6, rel=1e-6)


def test_goodman_fully_reversed_reduces_to_endurance_ratio():
    # Zero mean stress: n = Se / sigma_a (pure endurance screening).
    n = goodman_safety_factor(
        alternating_stress=_q("80 MPa"),
        mean_stress=_q("0 MPa"),
        endurance_limit=_q("200 MPa"),
        ultimate_strength=_q("400 MPa"),
    )
    assert n == pytest.approx(200 / 80, rel=1e-9)


def test_goodman_scorecard_uses_db_endurance_and_honours_no_silent_green():
    from anvilate.scorecard import CheckStatus
    from anvilate.standards import default_materials_db

    db = default_materials_db()
    # A36 carries a labelled 0.5*Su endurance estimate -> the screen evaluates.
    a36 = db.get("ASTM-A36")
    evaluated = goodman_scorecard(
        "fatigue",
        alternating_stress=_q("50 MPa"),
        mean_stress=_q("20 MPa"),
        endurance_limit=a36.endurance_limit.quantity,
        ultimate_strength=a36.ultimate_strength.quantity,
        required=1.5,
    )
    assert evaluated.status in (CheckStatus.PASS, CheckStatus.FAIL)  # it ran
    # SS-304 has no endurance limit -> NOT_EVALUATED, never a silent pass.
    ss304 = db.get("SS-304")
    assert ss304.endurance_limit is None
    gap = goodman_scorecard(
        "fatigue",
        alternating_stress=_q("50 MPa"),
        mean_stress=_q("20 MPa"),
        endurance_limit=None,
        ultimate_strength=ss304.ultimate_strength.quantity,
        required=1.5,
    )
    assert gap.status is CheckStatus.NOT_EVALUATED
    assert not gap.passed


def test_goodman_rejects_negative_amplitude():
    with pytest.raises(ValueError, match="amplitude"):
        goodman_safety_factor(
            alternating_stress=_q("-10 MPa"),
            mean_stress=_q("0 MPa"),
            endurance_limit=_q("200 MPa"),
            ultimate_strength=_q("400 MPa"),
        )


def test_combine_axial_bending_extreme_fibres():
    # 50 MPa tension axial + 150 MPa bending: tension fibre 200, compression -100.
    combined = combine_axial_bending(axial_stress=_q("50 MPa"), bending_stress=_q("150 MPa"))
    assert combined.tension_fibre.to("MPa").magnitude == pytest.approx(200.0, rel=1e-9)
    assert combined.compression_fibre.to("MPa").magnitude == pytest.approx(-100.0, rel=1e-9)
    assert combined.peak_magnitude.to("MPa").magnitude == pytest.approx(200.0, rel=1e-9)


def test_combine_axial_bending_compression_governs():
    # Axial compression -50 MPa + 30 MPa bending: fibres -20 and -80; peak = 80.
    combined = combine_axial_bending(axial_stress=_q("-50 MPa"), bending_stress=_q("30 MPa"))
    assert combined.tension_fibre.to("MPa").magnitude == pytest.approx(-20.0, rel=1e-9)
    assert combined.compression_fibre.to("MPa").magnitude == pytest.approx(-80.0, rel=1e-9)
    assert combined.peak_magnitude.to("MPa").magnitude == pytest.approx(80.0, rel=1e-9)


def test_von_mises_plane_stress_worked_example():
    # sigma_x=100, sigma_y=0, tau=50 MPa: sqrt(100^2 + 3*50^2) = sqrt(17500) = 132.29.
    vm = von_mises_plane_stress(sigma_x=_q("100 MPa"), sigma_y=_q("0 MPa"), tau_xy=_q("50 MPa"))
    assert vm.to("MPa").magnitude == pytest.approx(132.288, rel=1e-4)


def test_von_mises_reduces_to_uniaxial_and_pure_shear():
    # Uniaxial: von Mises equals the applied normal stress.
    uni = von_mises_plane_stress(sigma_x=_q("100 MPa"), sigma_y=_q("0 MPa"), tau_xy=_q("0 MPa"))
    assert uni.to("MPa").magnitude == pytest.approx(100.0, rel=1e-9)
    # Pure shear: von Mises = sqrt(3) * tau ~ 173.2 MPa for tau = 100 MPa.
    shear = von_mises_plane_stress(sigma_x=_q("0 MPa"), sigma_y=_q("0 MPa"), tau_xy=_q("100 MPa"))
    assert shear.to("MPa").magnitude == pytest.approx(173.205, rel=1e-4)


def test_von_mises_bending_torsion_matches_plane_stress():
    # The bending+torsion convenience is the plane-stress form with sigma_y = 0.
    combined = von_mises_bending_torsion(bending_stress=_q("100 MPa"), shear_stress=_q("50 MPa"))
    plane = von_mises_plane_stress(sigma_x=_q("100 MPa"), sigma_y=_q("0 MPa"), tau_xy=_q("50 MPa"))
    assert combined.to("MPa").magnitude == pytest.approx(plane.to("MPa").magnitude, rel=1e-9)


def test_yield_safety_factor_from_equivalent_stress():
    vm = von_mises_bending_torsion(bending_stress=_q("100 MPa"), shear_stress=_q("50 MPa"))
    # 132.29 MPa equivalent against a 276 MPa yield → SF ~ 2.086.
    assert yield_safety_factor(vm, _q("276 MPa")) == pytest.approx(276 / 132.288, rel=1e-4)


def test_strength_scorecard_ties_stress_material_and_scorecard():
    # End-to-end: a computed stress screened against a material's yield strength
    # from the database produces a pass/fail scorecard entry.
    from anvilate.scorecard import CheckStatus
    from anvilate.standards import default_materials_db

    db = default_materials_db()
    yield_6061 = db.get("AA-6061-T6").yield_strength.quantity  # 276 MPa
    # 100 MPa working stress vs 276 MPa yield -> SF 2.76 >= 2.0 required -> PASS.
    ok = strength_scorecard("yield", stress=_q("100 MPa"), allowable=yield_6061, required=2.0)
    assert ok.status is CheckStatus.PASS
    # 200 MPa working stress -> SF 1.38 < 2.0 -> FAIL.
    bad = strength_scorecard("yield", stress=_q("200 MPa"), allowable=yield_6061, required=2.0)
    assert bad.status is CheckStatus.FAIL


def test_strength_scorecard_not_evaluated_for_missing_property():
    # No silent green: SS-304 has no listed endurance limit, so a fatigue screen
    # against it is NOT_EVALUATED, never a silent pass.
    from anvilate.scorecard import CheckStatus
    from anvilate.standards import default_materials_db

    ss304 = default_materials_db().get("SS-304")
    assert ss304.endurance_limit is None
    entry = strength_scorecard(
        "fatigue",
        stress=_q("80 MPa"),
        allowable=None,  # the absent endurance limit
        required=1.5,
    )
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert not entry.passed


def test_von_mises_rejects_non_stress_inputs():
    with pytest.raises(ValueError, match="tau_xy must be a"):
        von_mises_plane_stress(sigma_x=_q("100 MPa"), sigma_y=_q("0 MPa"), tau_xy=_q("50 mm"))


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
