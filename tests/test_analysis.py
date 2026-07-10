"""Tests for the T1 analytical checks, against hand-computed worked examples."""

from __future__ import annotations

from math import pi

import pytest

from anvilate.analysis import (
    SHEAR_FORM_CIRCULAR,
    SHEAR_FORM_RECTANGULAR,
    ColumnEnd,
    CrossSection,
    axial_stress,
    bearing_stress,
    bolt_preload_from_torque,
    bolt_shear_stress,
    cantilever_center_patch_load,
    cantilever_end_load,
    cantilever_end_moment,
    cantilever_fundamental_frequency,
    cantilever_offset_load,
    cantilever_offset_moment,
    cantilever_partial_uniform_load,
    cantilever_triangular_load,
    cantilever_triangular_load_peak_at_tip,
    cantilever_uniform_load,
    circular_area,
    circular_second_moment,
    combine_axial_bending,
    concentrated_stress,
    constrained_thermal_stress,
    deflection_scorecard,
    euler_buckling_load,
    euler_critical_stress,
    fixed_fixed_center_load,
    fixed_fixed_center_patch_load,
    fixed_fixed_fundamental_frequency,
    fixed_fixed_offset_load,
    fixed_fixed_partial_uniform_load,
    fixed_fixed_triangular_load,
    fixed_fixed_uniform_load,
    fixed_pinned_center_load,
    fixed_pinned_center_patch_load,
    fixed_pinned_end_moment,
    fixed_pinned_fundamental_frequency,
    fixed_pinned_offset_load,
    fixed_pinned_partial_uniform_load,
    fixed_pinned_triangular_load,
    fixed_pinned_triangular_load_peak_at_prop,
    fixed_pinned_uniform_load,
    frequency_scorecard,
    goodman_safety_factor,
    goodman_scorecard,
    hertz_cylinder_contact,
    hertz_sphere_contact,
    hollow_circular_second_moment,
    hollow_shaft_torsional_stress,
    hollow_shaft_twist_angle,
    interference_axial_capacity,
    interference_fit,
    interference_torque_capacity,
    johnson_critical_stress,
    key_bearing_stress,
    key_shear_stress,
    key_tangential_force,
    max_shear_stress_plane,
    max_transverse_shear_stress,
    natural_frequency,
    natural_frequency_from_deflection,
    polar_second_moment_hollow,
    polar_second_moment_solid,
    principal_stresses_plane,
    radius_of_gyration,
    rectangular_second_moment,
    shaft_torsional_stiffness,
    shaft_torsional_stress,
    shaft_twist_angle,
    simply_supported_center_load,
    simply_supported_center_patch_load,
    simply_supported_end_moment,
    simply_supported_fundamental_frequency,
    simply_supported_offset_load,
    simply_supported_offset_moment,
    simply_supported_partial_uniform_load,
    simply_supported_plate_uniform_load,
    simply_supported_symmetric_point_loads,
    simply_supported_triangular_load,
    simply_supported_uniform_load,
    slenderness_ratio,
    solid_disc_polar_mass_moment,
    spring_index,
    spring_shear_stress,
    strength_scorecard,
    thin_wall_cylinder,
    thin_wall_sphere_stress,
    torque_for_preload,
    torsional_natural_frequency,
    transition_slenderness,
    tresca_equivalent_stress,
    von_mises_bending_torsion,
    von_mises_plane_stress,
    wahl_factor,
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


def test_cantilever_offset_load_matches_worked_example():
    # Same 500 mm, 20 x 10 mm steel cantilever, 100 N at mid-length (250 mm from
    # the fixed end). By hand: M = F*a = 25000 N*mm -> sigma = 25000*5/1666.67
    # = 75 MPa; delta_tip = F*a^2*(3L-a)/(6*E*I) = 100*250^2*1250/(6*200000*1666.67)
    # = 3.90625 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = cantilever_offset_load(
        force=_q("100 N"),
        load_position=_q("250 mm"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(75.0, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(3.90625, rel=1e-4)


def test_cantilever_offset_load_degenerates_to_the_end_case():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    offset = cantilever_offset_load(load_position=_q("500 mm"), **kw)
    end = cantilever_end_load(**kw)
    assert offset.max_bending_stress.to("MPa").magnitude == pytest.approx(
        end.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert offset.max_deflection.to("mm").magnitude == pytest.approx(
        end.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_cantilever_offset_load_rejects_positions_off_the_beam():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for position in ("0 mm", "-10 mm", "600 mm"):
        with pytest.raises(ValueError, match="load_position must lie on the beam"):
            cantilever_offset_load(load_position=_q(position), **kw)


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


def test_simply_supported_offset_load_matches_worked_example():
    # Same 500 mm, 20 x 10 mm steel beam, 100 N at the quarter point (125 mm).
    # By hand: M = P*a*b/L = 100*125*375/500 = 9375 N*mm -> sigma = 28.125 MPa;
    #   delta_max = P*b*(L^2-b^2)^1.5/(9*sqrt(3)*L*E*I) with b = 125 -> 0.54592 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = simply_supported_offset_load(
        force=_q("100 N"),
        load_position=_q("125 mm"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(28.125, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.54592, rel=1e-4)


def test_simply_supported_offset_load_degenerates_to_the_center_case():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    offset = simply_supported_offset_load(force=_q("100 N"), load_position=_q("250 mm"), **kw)
    center = simply_supported_center_load(force=_q("100 N"), **kw)
    assert offset.max_bending_stress.to("MPa").magnitude == pytest.approx(
        center.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert offset.max_deflection.to("mm").magnitude == pytest.approx(
        center.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_symmetric_point_loads_match_worked_example():
    # Four-point bending: 5 kN at 1 m from EACH support of a 3 m span, 80x120x5
    # box (I = 3,755,833 mm^4, c = 60). M = F*a = 5e6 N*mm constant between the
    # loads -> sigma = M*c/I = 79.876 MPa; delta_mid = F*a*(3L^2 - 4a^2)/(24*E*I)
    # = 6.3790 mm (verified against a numeric double-integration of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = simply_supported_symmetric_point_loads(
        force=_q("5 kN"),
        load_offset=_q("1 m"),
        length=_q("3 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(79.8757, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(6.37899, rel=1e-4)


def test_symmetric_point_loads_degenerate_to_a_doubled_center_load():
    # At a = L/2 both loads coincide at mid-span: exactly a 2*F center load.
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    pair = simply_supported_symmetric_point_loads(force=_q("100 N"), load_offset=_q("250 mm"), **kw)
    center = simply_supported_center_load(force=_q("200 N"), **kw)
    assert pair.max_bending_stress.to("MPa").magnitude == pytest.approx(
        center.max_bending_stress.to("MPa").magnitude, rel=1e-12
    )
    assert pair.max_deflection.to("mm").magnitude == pytest.approx(
        center.max_deflection.to("mm").magnitude, rel=1e-12
    )


def test_symmetric_point_loads_beat_the_center_resultant_by_the_moment_ratio():
    # Third-point rails: M = F*L/3, while the 2*F resultant at mid-span gives
    # F*L/2 — modeling a two-footed machine as one center load overstates the
    # moment by exactly 1.5x.
    kw = {
        "length": _q("600 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    pair = simply_supported_symmetric_point_loads(force=_q("100 N"), load_offset=_q("200 mm"), **kw)
    resultant = simply_supported_center_load(force=_q("200 N"), **kw)
    assert resultant.max_bending_stress.to("MPa").magnitude == pytest.approx(
        1.5 * pair.max_bending_stress.to("MPa").magnitude, rel=1e-12
    )


def test_symmetric_point_loads_reject_an_offset_beyond_the_half_span():
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    with pytest.raises(ValueError, match="load_offset must lie within the half-span"):
        simply_supported_symmetric_point_loads(load_offset=_q("300 mm"), **kw)
    with pytest.raises(ValueError, match="load_offset must lie within the half-span"):
        simply_supported_symmetric_point_loads(load_offset=_q("0 mm"), **kw)


def test_symmetric_point_loads_reject_distributed_load_units():
    with pytest.raises(ValueError, match="force must be a"):
        simply_supported_symmetric_point_loads(
            force=_q("1 N/mm"),  # a line load, not a point force
            load_offset=_q("100 mm"),
            length=_q("500 mm"),
            second_moment=rectangular_second_moment(_q("20 mm"), _q("10 mm")),
            extreme_fibre=_q("5 mm"),
            elastic_modulus=_q("200 GPa"),
        )


def test_cantilever_end_moment_matches_worked_example():
    # A 500 mm steel cantilever, 20 x 10 mm section, a 50 N*m couple at the tip.
    # By hand: sigma = M*c/I = 50000 * 5 / 1666.67 = 150 MPa (constant over the
    # whole span); delta = M*L^2/(2*E*I) = 50000*500^2 / (2*200000*1666.67)
    # = 18.75 mm (verified against a numeric integration of the beam ODE).
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = cantilever_end_moment(
        moment=_q("50 N*m"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(150.0, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(18.75, rel=1e-4)


def test_cantilever_end_moment_deflects_1_5x_the_equivalent_tip_force():
    # A couple M0 and a tip force F = M0/L produce the SAME wall moment (and so
    # the same peak stress), but the couple's tip deflection M0*L^2/2EI is
    # exactly 1.5x the force's F*L^3/3EI — constant moment bends the whole span.
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    couple = cantilever_end_moment(moment=_q("50 N*m"), **kw)
    force = cantilever_end_load(force=_q("100 N"), **kw)  # 100 N * 500 mm = 50 N*m
    assert couple.max_bending_stress.to("MPa").magnitude == pytest.approx(
        force.max_bending_stress.to("MPa").magnitude, rel=1e-12
    )
    assert couple.max_deflection.to("mm").magnitude == pytest.approx(
        1.5 * force.max_deflection.to("mm").magnitude, rel=1e-12
    )


def test_simply_supported_end_moment_matches_worked_example():
    # A 500 mm simply-supported span, 20 x 10 mm section, a 50 N*m couple at one
    # end. By hand: sigma = M*c/I = 150 MPa at the loaded end; delta_max =
    # M*L^2/(9*sqrt(3)*E*I) = 50000*500^2 / (15.5885*200000*1666.67) = 2.40563 mm
    # at (1 - 1/sqrt(3))*L from the loaded end (verified against a numeric
    # integration of the beam ODE).
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = simply_supported_end_moment(
        moment=_q("50 N*m"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(150.0, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(2.40563, rel=1e-4)


def test_fixed_pinned_end_moment_matches_worked_example():
    # The same 50 N*m couple at the prop of a 500 mm propped cantilever: the
    # wall carries over M0/2, so the applied couple still governs — sigma =
    # 150 MPa at the prop; delta_max = M*L^2/(27*E*I) = 1.38889 mm at L/3 from
    # the prop (verified against a numeric integration of the beam ODE).
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = fixed_pinned_end_moment(
        moment=_q("50 N*m"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(150.0, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(1.38889, rel=1e-4)


def test_fixed_pinned_end_moment_deflects_1_over_sqrt3_of_simply_supported():
    # Building in the far end leaves the peak stress unchanged (M0 at the
    # loaded end in both) but cuts delta_max to exactly (1/27)/(1/(9*sqrt(3)))
    # = 1/sqrt(3) of the simply-supported value.
    kw = {
        "moment": _q("50 N*m"),
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    propped = fixed_pinned_end_moment(**kw)
    simple = simply_supported_end_moment(**kw)
    assert propped.max_bending_stress.to("MPa").magnitude == pytest.approx(
        simple.max_bending_stress.to("MPa").magnitude, rel=1e-12
    )
    assert propped.max_deflection.to("mm").magnitude == pytest.approx(
        simple.max_deflection.to("mm").magnitude / 3**0.5, rel=1e-12
    )


def test_cantilever_offset_moment_matches_worked_example():
    # The 50 N*m couple moved to mid-length (a = 250 mm of the 500 mm beam):
    # the wall-to-couple segment is in pure bending at sigma = 150 MPa (the
    # peak stress does not drop with position — only the deflection does);
    # delta_tip = M*a*(2L-a)/(2*E*I) = 50000*250*750/(2*200000*1666.67)
    # = 14.0625 mm (verified against a numeric integration of the beam ODE).
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = cantilever_offset_moment(
        moment=_q("50 N*m"),
        load_position=_q("250 mm"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(150.0, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(14.0625, rel=1e-4)


def test_cantilever_offset_moment_degenerates_to_the_end_case():
    kw = {
        "moment": _q("50 N*m"),
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    offset = cantilever_offset_moment(load_position=_q("500 mm"), **kw)
    end = cantilever_end_moment(**kw)
    assert offset.max_bending_stress.to("MPa").magnitude == pytest.approx(
        end.max_bending_stress.to("MPa").magnitude, rel=1e-12
    )
    assert offset.max_deflection.to("mm").magnitude == pytest.approx(
        end.max_deflection.to("mm").magnitude, rel=1e-12
    )


def test_simply_supported_offset_moment_matches_worked_example():
    # The 50 N*m couple at 125 mm of the 500 mm span: the moment jumps by M0
    # across the couple, peaking at M0*max(a,b)/L = 50000*375/500 = 37500 N*mm
    # -> sigma 112.5 MPa; the two-lobed curve's larger stationary value gives
    # delta_max = 1.76183 mm (verified against a numeric integration of the
    # beam ODE).
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = simply_supported_offset_moment(
        moment=_q("50 N*m"),
        load_position=_q("125 mm"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(112.5, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(1.76183, rel=1e-4)


def test_simply_supported_offset_moment_is_symmetric_and_mildest_at_mid_span():
    kw = {
        "moment": _q("50 N*m"),
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    near = simply_supported_offset_moment(load_position=_q("125 mm"), **kw)
    far = simply_supported_offset_moment(load_position=_q("375 mm"), **kw)
    assert near.max_bending_stress.to("MPa").magnitude == pytest.approx(
        far.max_bending_stress.to("MPa").magnitude, rel=1e-12
    )
    assert near.max_deflection.to("mm").magnitude == pytest.approx(
        far.max_deflection.to("mm").magnitude, rel=1e-12
    )
    # A mid-span couple peaks at exactly M0/2 — half the end-moment case's M0,
    # the reverse of a point load's worst position.
    mid = simply_supported_offset_moment(load_position=_q("250 mm"), **kw)
    end = simply_supported_end_moment(**kw)
    assert mid.max_bending_stress.to("MPa").magnitude == pytest.approx(
        end.max_bending_stress.to("MPa").magnitude / 2, rel=1e-12
    )


def test_simply_supported_offset_moment_rejects_positions_off_the_span():
    kw = {
        "moment": _q("50 N*m"),
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    with pytest.raises(ValueError, match="strictly inside the span"):
        simply_supported_offset_moment(load_position=_q("500 mm"), **kw)
    with pytest.raises(ValueError, match="strictly inside the span"):
        simply_supported_offset_moment(load_position=_q("0 mm"), **kw)


def test_cantilever_offset_moment_rejects_positions_off_the_beam():
    kw = {
        "moment": _q("50 N*m"),
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    with pytest.raises(ValueError, match="load_position must lie on the beam"):
        cantilever_offset_moment(load_position=_q("600 mm"), **kw)
    with pytest.raises(ValueError, match="load_position must lie on the beam"):
        cantilever_offset_moment(load_position=_q("0 mm"), **kw)


def test_end_moment_rejects_a_force_load():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    with pytest.raises(ValueError, match="moment must be a"):
        cantilever_end_moment(moment=_q("100 N"), **kw)
    with pytest.raises(ValueError, match="moment must be a"):
        simply_supported_end_moment(moment=_q("100 N"), **kw)


def test_simply_supported_offset_load_is_symmetric():
    # Measuring the position from either support is the same physical case.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    left = simply_supported_offset_load(load_position=_q("125 mm"), **kw)
    right = simply_supported_offset_load(load_position=_q("375 mm"), **kw)
    assert left.max_bending_stress.to("MPa").magnitude == pytest.approx(
        right.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert left.max_deflection.to("mm").magnitude == pytest.approx(
        right.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_simply_supported_offset_load_rejects_positions_outside_the_span():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for position in ("0 mm", "500 mm", "600 mm", "-10 mm"):
        with pytest.raises(ValueError, match="strictly inside the span"):
            simply_supported_offset_load(load_position=_q(position), **kw)


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


def test_cantilever_partial_uniform_load_matches_worked_example():
    # 10 N/mm over the first 1 m (from the wall) of a 2 m, 80x120x5 box cantilever
    # (I = 3,755,833 mm^4, c = 60): M = w*a^2/2 = 5,000,000 N*mm -> sigma = M*c/I
    # = 79.87 MPa; tip delta = w*a^3*(4L-a)/(24*E*I) = 3.8828 mm (verified against
    # a numeric double-integration of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = cantilever_partial_uniform_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("1 m"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(79.867, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(3.88285, rel=1e-4)


def test_cantilever_partial_uniform_load_degenerates_to_the_full_udl():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    partial = cantilever_partial_uniform_load(
        distributed_load=_q("1 N/mm"), loaded_length=_q("500 mm"), **kw
    )
    full = cantilever_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    assert partial.max_bending_stress.to("MPa").magnitude == pytest.approx(
        full.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert partial.max_deflection.to("mm").magnitude == pytest.approx(
        full.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_cantilever_partial_uniform_load_rejects_bad_inputs():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for loaded_length in ("0 mm", "600 mm"):
        with pytest.raises(ValueError, match="loaded_length must lie within the span"):
            cantilever_partial_uniform_load(
                distributed_load=_q("1 N/mm"), loaded_length=_q(loaded_length), **kw
            )
    with pytest.raises(ValueError, match="distributed_load must be a"):
        cantilever_partial_uniform_load(
            distributed_load=_q("100 N"),  # a force, not force-per-length
            loaded_length=_q("250 mm"),
            **kw,
        )


def test_cantilever_center_patch_load_matches_worked_example():
    # 10 N/mm over the middle 1 m of a 2 m, 80x120x5 box cantilever
    # (I = 3,755,833 mm^4, c = 60): the wall moment M = w*a*L/2 = 10,000,000 N*mm
    # -> sigma = M*c/I = 159.75 MPa; tip delta = w*L*a*(5L^2 + a^2)/(48*E*I)
    # = 11.6485 mm (verified against an independent numeric double-integration
    # of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = cantilever_center_patch_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("1 m"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(159.752, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(11.64855, rel=1e-4)


def test_cantilever_center_patch_load_degenerates_to_the_full_udl():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    patch = cantilever_center_patch_load(
        distributed_load=_q("1 N/mm"), loaded_length=_q("500 mm"), **kw
    )
    full = cantilever_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    assert patch.max_bending_stress.to("MPa").magnitude == pytest.approx(
        full.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert patch.max_deflection.to("mm").magnitude == pytest.approx(
        full.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_cantilever_center_patch_degenerates_to_the_mid_span_point_load():
    # As a -> 0 at fixed total w*a the patch becomes a point load at mid-span.
    # The wall moment matches exactly for every patch length (the patch total
    # always acts at its L/2 centroid); the deflection converges as a -> 0.
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    patch = cantilever_center_patch_load(
        distributed_load=_q("200 N/mm"),
        loaded_length=_q("5 mm"),
        **kw,  # 1000 N total
    )
    point = cantilever_offset_load(force=_q("1000 N"), load_position=_q("250 mm"), **kw)
    assert patch.max_bending_stress.to("MPa").magnitude == pytest.approx(
        point.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert patch.max_deflection.to("mm").magnitude == pytest.approx(
        point.max_deflection.to("mm").magnitude, rel=1e-4
    )


def test_cantilever_center_patch_load_rejects_bad_inputs():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for loaded_length in ("0 mm", "600 mm"):
        with pytest.raises(ValueError, match="loaded_length must lie within the span"):
            cantilever_center_patch_load(
                distributed_load=_q("1 N/mm"), loaded_length=_q(loaded_length), **kw
            )
    with pytest.raises(ValueError, match="distributed_load must be a"):
        cantilever_center_patch_load(
            distributed_load=_q("100 N"),  # a force, not force-per-length
            loaded_length=_q("250 mm"),
            **kw,
        )


def test_cantilever_triangular_load_matches_worked_example():
    # 10 N/mm peaking at the fixed end of a 1 m, 80x120x5 box (I = 3,755,833 mm^4,
    # c = 60): M_max = w0*L^2/6 = 1,666,667 N*mm -> sigma = M*c/I = 26.63 MPa;
    #   delta = w0*L^4/(30*E*I) = 0.4438 mm at the free end.
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = cantilever_triangular_load(
        peak_distributed_load=_q("10 N/mm"),
        length=_q("1 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(26.625, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.44375, rel=1e-3)


def test_cantilever_triangular_stress_matches_the_resultant_at_the_centroid():
    # The fixed-end moment of any cantilever load equals its resultant times the
    # centroid distance, so the triangle (total w0*L/2 acting at L/3 from the wall)
    # must match a point load placed there exactly — in stress, not deflection.
    kw = {
        "length": _q("900 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    tri = cantilever_triangular_load(peak_distributed_load=_q("2 N/mm"), **kw)
    resultant = cantilever_offset_load(
        force=_q("900 N"),  # 2 N/mm * 900 mm / 2
        load_position=_q("300 mm"),  # L/3 from the fixed end
        **kw,
    )
    assert tri.max_bending_stress.to("MPa").magnitude == pytest.approx(
        resultant.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert tri.max_deflection.to("mm").magnitude != pytest.approx(
        resultant.max_deflection.to("mm").magnitude, rel=1e-3
    )


def test_cantilever_triangular_load_peak_at_tip_matches_worked_example():
    # 10 N/mm peaking at the TIP of a 1 m, 80x120x5 box (I = 3,755,833 mm^4,
    # c = 60): M_max = w0*L^2/3 = 3,333,333 N*mm -> sigma = M*c/I = 53.25 MPa
    # (TWICE the peak-at-wall orientation); delta = 11*w0*L^4/(120*E*I)
    # = 1.2203 mm at the free end (verified against a numeric double-integration
    # of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = cantilever_triangular_load_peak_at_tip(
        peak_distributed_load=_q("10 N/mm"),
        length=_q("1 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(53.2505, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(1.220324, rel=1e-4)


def test_cantilever_triangle_orientations_superpose_to_the_full_udl():
    # The two orientations sum to a full UDL, and on a cantilever BOTH maxima sit
    # at the same places (moment at the wall, deflection at the tip), so stress
    # AND deflection superpose exactly: 1/6 + 1/3 = 1/2 and 1/30 + 11/120 = 1/8.
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    wall_peak = cantilever_triangular_load(peak_distributed_load=_q("1 N/mm"), **kw)
    tip_peak = cantilever_triangular_load_peak_at_tip(peak_distributed_load=_q("1 N/mm"), **kw)
    udl = cantilever_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    for attribute, unit in (("max_bending_stress", "MPa"), ("max_deflection", "mm")):
        combined = (
            getattr(wall_peak, attribute).to(unit).magnitude
            + getattr(tip_peak, attribute).to(unit).magnitude
        )
        assert combined == pytest.approx(getattr(udl, attribute).to(unit).magnitude, rel=1e-12)
    assert tip_peak.max_bending_stress.to("MPa").magnitude == pytest.approx(
        2 * wall_peak.max_bending_stress.to("MPa").magnitude, rel=1e-12
    )


def test_cantilever_triangular_load_peak_at_tip_rejects_point_load_units():
    with pytest.raises(ValueError, match="peak_distributed_load must be a"):
        cantilever_triangular_load_peak_at_tip(
            peak_distributed_load=_q("100 N"),  # a force, not force-per-length
            length=_q("500 mm"),
            second_moment=rectangular_second_moment(_q("20 mm"), _q("10 mm")),
            extreme_fibre=_q("5 mm"),
            elastic_modulus=_q("200 GPa"),
        )


def test_cantilever_triangular_load_is_milder_than_both_bracketing_uniform_loads():
    # Unlike the simply-supported case, a triangle peaking at the WALL biases its
    # load toward the support where the moment arm is short — so it is milder than
    # even a UDL of the same total load (w0/2), not just the full-w0 one.
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    tri = cantilever_triangular_load(peak_distributed_load=_q("1 N/mm"), **kw)
    full = cantilever_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    same_total = cantilever_uniform_load(distributed_load=_q("0.5 N/mm"), **kw)
    tri_stress = tri.max_bending_stress.to("MPa").magnitude
    assert tri_stress < same_total.max_bending_stress.to("MPa").magnitude
    assert tri_stress < full.max_bending_stress.to("MPa").magnitude
    tri_deflection = tri.max_deflection.to("mm").magnitude
    assert tri_deflection < same_total.max_deflection.to("mm").magnitude
    assert tri_deflection < full.max_deflection.to("mm").magnitude


def test_cantilever_triangular_load_rejects_point_load_units():
    with pytest.raises(ValueError, match="peak_distributed_load must be a"):
        cantilever_triangular_load(
            peak_distributed_load=_q("100 N"),  # a force, not force-per-length
            length=_q("500 mm"),
            second_moment=rectangular_second_moment(_q("20 mm"), _q("10 mm")),
            extreme_fibre=_q("5 mm"),
            elastic_modulus=_q("200 GPa"),
        )


def test_fixed_fixed_center_load_matches_worked_example():
    # 100 N at mid-span of a fixed-fixed 500 mm 20x10 steel beam:
    #   M_max = F*L/8 = 6250 N*mm -> sigma = 6250*5/1666.67 = 18.75 MPa;
    #   delta = F*L^3/(192*E*I) = 100*500^3/(192*200000*1666.67) = 0.1953 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    ff = fixed_fixed_center_load(force=_q("100 N"), **kw)
    assert ff.max_bending_stress.to("MPa").magnitude == pytest.approx(18.75, rel=1e-4)
    assert ff.max_deflection.to("mm").magnitude == pytest.approx(0.19531, rel=1e-4)
    # Fixed-fixed is 4x stiffer than simply-supported (delta 1/192 vs 1/48).
    ss = simply_supported_center_load(force=_q("100 N"), **kw)
    assert ff.max_deflection.to("mm").magnitude == pytest.approx(
        ss.max_deflection.to("mm").magnitude / 4, rel=1e-6
    )


def test_fixed_fixed_offset_load_matches_worked_example():
    # 100 N at the quarter point (a = 125 mm) of the same fixed-fixed beam.
    # By hand: M = F*a*b^2/L^2 = 100*125*375^2/500^2 = 7031.25 N*mm at the nearer
    # wall -> sigma = 7031.25*5/1666.67 = 21.09375 MPa; delta_max =
    # 2*F*b^3*a^2/(3*E*I*(3b+a)^2) = 2*100*375^3*125^2/(3*200000*1666.67*1250^2)
    # = 0.10547 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    result = fixed_fixed_offset_load(
        force=_q("100 N"),
        load_position=_q("125 mm"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(21.09375, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.105469, rel=1e-4)


def test_fixed_fixed_offset_load_degenerates_to_the_center_case():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    offset = fixed_fixed_offset_load(force=_q("100 N"), load_position=_q("250 mm"), **kw)
    center = fixed_fixed_center_load(force=_q("100 N"), **kw)
    assert offset.max_bending_stress.to("MPa").magnitude == pytest.approx(
        center.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert offset.max_deflection.to("mm").magnitude == pytest.approx(
        center.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_fixed_fixed_offset_load_is_symmetric():
    # Measuring the position from either wall is the same physical case.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    left = fixed_fixed_offset_load(load_position=_q("125 mm"), **kw)
    right = fixed_fixed_offset_load(load_position=_q("375 mm"), **kw)
    assert left.max_bending_stress.to("MPa").magnitude == pytest.approx(
        right.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert left.max_deflection.to("mm").magnitude == pytest.approx(
        right.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_fixed_fixed_offset_load_peaks_off_center():
    # Unlike the simply-supported case, the fixed-fixed wall moment is worst at
    # the third point: M = 4*F*L/27 there, 18.5% above the mid-span F*L/8.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    third = fixed_fixed_offset_load(load_position=Quantity(magnitude=500 / 3, unit="mm"), **kw)
    center = fixed_fixed_center_load(**kw)
    assert third.max_bending_stress.to("MPa").magnitude == pytest.approx(
        center.max_bending_stress.to("MPa").magnitude * 32 / 27, rel=1e-6
    )


def test_fixed_fixed_offset_load_rejects_positions_outside_the_span():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for position in ("0 mm", "-10 mm", "500 mm", "600 mm"):
        with pytest.raises(ValueError, match="load_position must lie strictly inside"):
            fixed_fixed_offset_load(load_position=_q(position), **kw)


def test_fixed_fixed_uniform_load_matches_worked_example():
    # 1 N/mm UDL on the same fixed-fixed beam:
    #   M_max = w*L^2/12 = 20833 N*mm -> sigma = 20833*5/1666.67 = 62.5 MPa;
    #   delta = w*L^4/(384*E*I) = 1*500^4/(384*200000*1666.67) = 0.4883 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    ff = fixed_fixed_uniform_load(
        distributed_load=_q("1 N/mm"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert ff.max_bending_stress.to("MPa").magnitude == pytest.approx(62.5, rel=1e-4)
    assert ff.max_deflection.to("mm").magnitude == pytest.approx(0.48828, rel=1e-4)


def test_fixed_fixed_partial_uniform_load_matches_worked_example():
    # 10 N/mm over the first 1 m of a 2 m fixed-fixed span, 80x120x5 box
    # (I = 3,755,833 mm^4, c = 60): the loaded-wall moment
    # M = w*a^2*(6L^2 - 8aL + 3a^2)/(12L^2) = 2,291,667 N*mm -> sigma = M*c/I
    # = 36.61 MPa; delta_max = 0.28542 mm at 0.443*L, the closed-form root of the
    # loaded-region slope (verified against an independent numeric double-
    # integration of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = fixed_fixed_partial_uniform_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("1 m"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(36.610, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.285424, rel=1e-4)


def test_fixed_fixed_partial_uniform_load_with_a_short_patch():
    # 10 N/mm over the first 400 mm only: the maximum deflection sits in the
    # UNLOADED region, at the closed-form stationary point 2L^2/(3*(2L - a))
    # = 740.7 mm (verified against the same numeric integration).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = fixed_fixed_partial_uniform_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("400 mm"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    # M = 10*400^2*(6*2000^2 - 8*400*2000 + 3*400^2)/(12*2000^2) = 602,667 N*mm
    # -> sigma = 9.628 MPa.
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(9.6277, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.031900, rel=1e-4)


def test_fixed_fixed_partial_uniform_load_degenerates_to_the_full_udl():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    partial = fixed_fixed_partial_uniform_load(
        distributed_load=_q("1 N/mm"), loaded_length=_q("500 mm"), **kw
    )
    full = fixed_fixed_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    assert partial.max_bending_stress.to("MPa").magnitude == pytest.approx(
        full.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert partial.max_deflection.to("mm").magnitude == pytest.approx(
        full.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_fixed_fixed_partial_udl_is_stiffer_than_the_simply_supported_one():
    # Clamping the ends of the same patch-loaded beam must cut both the peak
    # deflection and the governing moment relative to simple supports.
    kw = {
        "distributed_load": _q("1 N/mm"),
        "loaded_length": _q("1 m"),
        "length": _q("2 m"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    ff = fixed_fixed_partial_uniform_load(**kw)
    ss = simply_supported_partial_uniform_load(**kw)
    assert ff.max_deflection.to("mm").magnitude < ss.max_deflection.to("mm").magnitude
    assert ff.max_bending_stress.to("MPa").magnitude < ss.max_bending_stress.to("MPa").magnitude


def test_fixed_fixed_partial_uniform_load_rejects_bad_inputs():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for loaded_length in ("0 mm", "600 mm"):
        with pytest.raises(ValueError, match="loaded_length must lie within the span"):
            fixed_fixed_partial_uniform_load(
                distributed_load=_q("1 N/mm"), loaded_length=_q(loaded_length), **kw
            )
    with pytest.raises(ValueError, match="distributed_load must be a"):
        fixed_fixed_partial_uniform_load(
            distributed_load=_q("100 N"),  # a force, not force-per-length
            loaded_length=_q("250 mm"),
            **kw,
        )


def test_fixed_fixed_center_patch_load_matches_worked_example():
    # 10 N/mm over the middle 1 m of a 2 m fixed-fixed span, 80x120x5 box
    # (I = 3,755,833 mm^4, c = 60): the wall moment M = w*a*(3L^2 - a^2)/(24L)
    # = 2,291,667 N*mm -> sigma = M*c/I = 36.61 MPa; mid-span delta
    # = w*a*(2L^3 - 2La^2 + a^3)/(384EI) = 0.45069 mm (verified against an
    # independent numeric double-integration of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = fixed_fixed_center_patch_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("1 m"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(36.610, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.450688, rel=1e-4)


def test_fixed_fixed_center_patch_load_degenerates_to_the_full_udl():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    patch = fixed_fixed_center_patch_load(
        distributed_load=_q("1 N/mm"), loaded_length=_q("500 mm"), **kw
    )
    full = fixed_fixed_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    assert patch.max_bending_stress.to("MPa").magnitude == pytest.approx(
        full.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert patch.max_deflection.to("mm").magnitude == pytest.approx(
        full.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_fixed_fixed_center_patch_sits_between_its_bracketing_idealizations():
    # Spreading the patch total over the whole span understates the demand;
    # concentrating it at mid-span overstates it (the a -> 0 limit).
    kw = {
        "length": _q("2 m"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    patch = fixed_fixed_center_patch_load(
        distributed_load=_q("1 N/mm"), loaded_length=_q("1 m"), **kw
    )
    spread = fixed_fixed_uniform_load(distributed_load=_q("0.5 N/mm"), **kw)
    concentrated = fixed_fixed_center_load(force=_q("1000 N"), **kw)  # the patch total
    patch_stress = patch.max_bending_stress.to("MPa").magnitude
    assert spread.max_bending_stress.to("MPa").magnitude < patch_stress
    assert patch_stress < concentrated.max_bending_stress.to("MPa").magnitude
    patch_deflection = patch.max_deflection.to("mm").magnitude
    assert spread.max_deflection.to("mm").magnitude < patch_deflection
    assert patch_deflection < concentrated.max_deflection.to("mm").magnitude


def test_fixed_fixed_center_patch_load_rejects_bad_inputs():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for loaded_length in ("0 mm", "600 mm"):
        with pytest.raises(ValueError, match="loaded_length must lie within the span"):
            fixed_fixed_center_patch_load(
                distributed_load=_q("1 N/mm"), loaded_length=_q(loaded_length), **kw
            )
    with pytest.raises(ValueError, match="distributed_load must be a"):
        fixed_fixed_center_patch_load(
            distributed_load=_q("100 N"),  # a force, not force-per-length
            loaded_length=_q("250 mm"),
            **kw,
        )


def test_fixed_pinned_center_load_matches_worked_example():
    # 100 N at mid-span of a propped-cantilever 500 mm 20x10 steel beam:
    #   M_max = 3*F*L/16 = 9375 N*mm at the wall -> sigma = 9375*5/1666.67
    #   = 28.125 MPa; delta = F*L^3/(48*sqrt(5)*E*I) = 0.34939 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    fp = fixed_pinned_center_load(force=_q("100 N"), **kw)
    assert fp.max_bending_stress.to("MPa").magnitude == pytest.approx(28.125, rel=1e-4)
    assert fp.max_deflection.to("mm").magnitude == pytest.approx(0.34939, rel=1e-4)
    # The propped cantilever sits between the two symmetric cases on both counts.
    ss = simply_supported_center_load(force=_q("100 N"), **kw)
    ff = fixed_fixed_center_load(force=_q("100 N"), **kw)
    assert (
        ff.max_deflection.to("mm").magnitude
        < fp.max_deflection.to("mm").magnitude
        < ss.max_deflection.to("mm").magnitude
    )


def test_fixed_pinned_offset_load_matches_worked_examples_on_both_sides():
    # Same 500 mm, 20x10 steel propped cantilever, 100 N. At a = 125 mm from the
    # prop the moment under the load governs: M = F*a*b^2*(a+2L)/(2L^3) =
    # 7910.16 N*mm -> sigma 23.73 MPa; delta (a < 0.414L branch) =
    # F*a*(L^2-a^2)^3/(3*E*I*(3L^2-a^2)^2) = 0.29841 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    near_prop = fixed_pinned_offset_load(load_position=_q("125 mm"), **kw)
    assert near_prop.max_bending_stress.to("MPa").magnitude == pytest.approx(23.7305, rel=1e-4)
    assert near_prop.max_deflection.to("mm").magnitude == pytest.approx(0.29841, rel=1e-4)
    # At a = 375 mm the wall moment governs: M = F*a*b*(a+L)/(2L^2) = 8203.1 N*mm
    # -> sigma 24.61 MPa; delta (a > 0.414L branch) =
    # F*a*b^2/(6*E*I)*sqrt(a/(2L+a)) = 0.15300 mm.
    near_wall = fixed_pinned_offset_load(load_position=_q("375 mm"), **kw)
    assert near_wall.max_bending_stress.to("MPa").magnitude == pytest.approx(24.6094, rel=1e-4)
    assert near_wall.max_deflection.to("mm").magnitude == pytest.approx(0.15300, rel=1e-4)
    # The case is asymmetric — mirrored positions are different physical cases.
    assert near_prop.max_bending_stress.to("MPa").magnitude != pytest.approx(
        near_wall.max_bending_stress.to("MPa").magnitude, rel=1e-3
    )


def test_fixed_pinned_offset_load_degenerates_to_the_center_case():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    offset = fixed_pinned_offset_load(force=_q("100 N"), load_position=_q("250 mm"), **kw)
    center = fixed_pinned_center_load(force=_q("100 N"), **kw)
    assert offset.max_bending_stress.to("MPa").magnitude == pytest.approx(
        center.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert offset.max_deflection.to("mm").magnitude == pytest.approx(
        center.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_fixed_pinned_offset_load_worst_position_is_l_over_sqrt3():
    # The wall moment peaks at a = L/sqrt(3) from the prop: M = F*L/(3*sqrt(3)),
    # 2.6% above the mid-span 3*F*L/16 — mid-span is not quite the worst case.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    worst = fixed_pinned_offset_load(
        load_position=Quantity(magnitude=500 / 3**0.5, unit="mm"), **kw
    )
    expected = 100 * 500 / (3 * 3**0.5) * 5 / 1666.6667  # M*c/I
    assert worst.max_bending_stress.to("MPa").magnitude == pytest.approx(expected, rel=1e-4)
    center = fixed_pinned_center_load(**kw)
    assert (
        worst.max_bending_stress.to("MPa").magnitude > center.max_bending_stress.to("MPa").magnitude
    )


def test_fixed_pinned_offset_load_rejects_positions_outside_the_span():
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "force": _q("100 N"),
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for position in ("0 mm", "-10 mm", "500 mm", "600 mm"):
        with pytest.raises(ValueError, match="load_position must lie strictly inside"):
            fixed_pinned_offset_load(load_position=_q(position), **kw)


def test_fixed_pinned_uniform_load_matches_worked_example():
    # 1 N/mm UDL on the same propped-cantilever beam:
    #   M_max = w*L^2/8 = 31250 N*mm at the wall -> sigma = 93.75 MPa (the same
    #   governing moment as simply-supported, but hogging);
    #   delta = w*L^4/(185*E*I) = 1*500^4/(185*200000*1666.67) = 1.01351 mm.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    kw = {
        "length": _q("500 mm"),
        "second_moment": inertia,
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    fp = fixed_pinned_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    assert fp.max_bending_stress.to("MPa").magnitude == pytest.approx(93.75, rel=1e-4)
    assert fp.max_deflection.to("mm").magnitude == pytest.approx(1.01351, rel=1e-4)
    # Deflection sits between the simply-supported (2.441) and fixed-fixed (0.488).
    ss = simply_supported_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    ff = fixed_fixed_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    assert (
        ff.max_deflection.to("mm").magnitude
        < fp.max_deflection.to("mm").magnitude
        < ss.max_deflection.to("mm").magnitude
    )


def test_fixed_pinned_partial_uniform_load_matches_worked_example():
    # 10 N/mm over the first 1 m from the wall of a 2 m propped cantilever,
    # 80x120x5 box (I = 3,755,833 mm^4, c = 60): the wall moment
    # M = w*a^2*(2L - a)^2/(8L^2) = 2,812,500 N*mm -> sigma = M*c/I = 44.93 MPa
    # (numerically equal to the simply-supported end-patch case — at a = L/2 the
    # wall moment w*a^2*(2L-a)^2/(8L^2) coincides with that case's R1^2/(2w));
    # delta_max = 0.45110 mm at 0.512*L from the wall, in the UNLOADED region
    # (verified against an independent numeric double-integration of the beam
    # ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = fixed_pinned_partial_uniform_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("1 m"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(44.930, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.451104, rel=1e-4)


def test_fixed_pinned_partial_uniform_load_with_a_long_patch():
    # 10 N/mm over the first 1.6 m: the maximum deflection now sits INSIDE the
    # loaded region, at the closed-form root 0.567*L of the loaded-region slope
    # (verified against the same numeric integration). M = 4,608,000 N*mm ->
    # sigma = 73.61 MPa.
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = fixed_pinned_partial_uniform_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("1600 mm"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(73.613, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(1.009978, rel=1e-4)


def test_fixed_pinned_partial_uniform_load_degenerates_to_the_full_udl():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    partial = fixed_pinned_partial_uniform_load(
        distributed_load=_q("1 N/mm"), loaded_length=_q("500 mm"), **kw
    )
    full = fixed_pinned_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    assert partial.max_bending_stress.to("MPa").magnitude == pytest.approx(
        full.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    # The full-UDL check uses the rounded handbook constant 185 (exact: 184.6),
    # so the exact elastic-curve deflection agrees only to that rounding.
    assert partial.max_deflection.to("mm").magnitude == pytest.approx(
        full.max_deflection.to("mm").magnitude, rel=2.5e-3
    )


def test_fixed_pinned_partial_udl_sits_between_its_bracketing_end_fixities():
    # For the same wall-adjacent patch, each added restraint stiffens the beam:
    # fixed-fixed deflects least, the propped cantilever sits in the middle,
    # simple supports deflect most.
    kw = {
        "distributed_load": _q("1 N/mm"),
        "loaded_length": _q("1 m"),
        "length": _q("2 m"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    ff = fixed_fixed_partial_uniform_load(**kw)
    fp = fixed_pinned_partial_uniform_load(**kw)
    ss = simply_supported_partial_uniform_load(**kw)
    assert (
        ff.max_deflection.to("mm").magnitude
        < fp.max_deflection.to("mm").magnitude
        < ss.max_deflection.to("mm").magnitude
    )


def test_fixed_pinned_partial_uniform_load_rejects_bad_inputs():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for loaded_length in ("0 mm", "600 mm"):
        with pytest.raises(ValueError, match="loaded_length must lie within the span"):
            fixed_pinned_partial_uniform_load(
                distributed_load=_q("1 N/mm"), loaded_length=_q(loaded_length), **kw
            )
    with pytest.raises(ValueError, match="distributed_load must be a"):
        fixed_pinned_partial_uniform_load(
            distributed_load=_q("100 N"),  # a force, not force-per-length
            loaded_length=_q("250 mm"),
            **kw,
        )


def test_fixed_pinned_center_patch_load_matches_worked_example():
    # 10 N/mm over the middle 1 m of a 2 m propped cantilever, 80x120x5 box
    # (I = 3,755,833 mm^4, c = 60): the wall moment M = w*a*(3L^2 - a^2)/(16L)
    # = 3,437,500 N*mm -> sigma = M*c/I = 54.91 MPa; delta_max = 0.85813 mm at
    # 0.568*L from the wall, bisected from the in-patch slope cubic (verified
    # against an independent numeric double-integration of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = fixed_pinned_center_patch_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("1 m"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(54.915, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.858126, rel=1e-4)


def test_fixed_pinned_center_patch_load_with_a_short_patch():
    # 10 N/mm over the middle 200 mm only: the maximum deflection sits BEYOND
    # the patch toward the prop, at the closed-form smaller root of the
    # prop-side quadratic slope, 0.554*L (verified against the same numeric
    # integration). M = 747,500 N*mm -> sigma = 11.94 MPa.
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = fixed_pinned_center_patch_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("200 mm"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(11.9414, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.197264, rel=1e-4)


def test_fixed_pinned_center_patch_load_degenerates_to_the_full_udl():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    patch = fixed_pinned_center_patch_load(
        distributed_load=_q("1 N/mm"), loaded_length=_q("500 mm"), **kw
    )
    full = fixed_pinned_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    assert patch.max_bending_stress.to("MPa").magnitude == pytest.approx(
        full.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    # The full-UDL check uses the rounded handbook constant 185 (exact: 184.6),
    # so the exact elastic-curve deflection agrees only to that rounding.
    assert patch.max_deflection.to("mm").magnitude == pytest.approx(
        full.max_deflection.to("mm").magnitude, rel=2.5e-3
    )


def test_fixed_pinned_center_patch_degenerates_to_the_center_point_load():
    # In the a -> 0 limit at fixed total w*a, the patch is the center point
    # load: M -> 3PL/16 and delta -> PL^3/(48*sqrt(5)*EI).
    kw = {
        "length": _q("2 m"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    patch = fixed_pinned_center_patch_load(
        distributed_load=_q("1000 N/mm"), loaded_length=_q("1 mm"), **kw
    )
    point = fixed_pinned_center_load(force=_q("1000 N"), **kw)
    assert patch.max_bending_stress.to("MPa").magnitude == pytest.approx(
        point.max_bending_stress.to("MPa").magnitude, rel=1e-6
    )
    assert patch.max_deflection.to("mm").magnitude == pytest.approx(
        point.max_deflection.to("mm").magnitude, rel=1e-6
    )


def test_fixed_pinned_center_patch_load_rejects_bad_inputs():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for loaded_length in ("0 mm", "600 mm"):
        with pytest.raises(ValueError, match="loaded_length must lie within the span"):
            fixed_pinned_center_patch_load(
                distributed_load=_q("1 N/mm"), loaded_length=_q(loaded_length), **kw
            )
    with pytest.raises(ValueError, match="distributed_load must be a"):
        fixed_pinned_center_patch_load(
            distributed_load=_q("100 N"),  # a force, not force-per-length
            loaded_length=_q("250 mm"),
            **kw,
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


def test_simply_supported_partial_uniform_load_matches_worked_example():
    # 10 N/mm over the first 1 m of a 2 m span, 80x120x5 box (I = 3,755,833 mm^4,
    # c = 60): R1 = w*a*(2L-a)/(2L) = 7500 N, M_max = R1^2/(2w) = 2,812,500 N*mm
    # -> sigma = M*c/I = 44.93 MPa; delta_max = 1.3980 mm at 0.460*L (bisected
    # from the loaded-region slope polynomial; verified against an independent
    # numeric double-integration of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = simply_supported_partial_uniform_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("1 m"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(44.925, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(1.39801, rel=1e-4)


def test_simply_supported_partial_uniform_load_with_a_short_patch():
    # 10 N/mm over the first 400 mm only: the maximum deflection sits in the
    # UNLOADED region, at the closed-form stationary point L - sqrt((2L^2-a^2)/6)
    # = 857 mm (verified against the same numeric integration).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = simply_supported_partial_uniform_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("400 mm"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    # R1 = 10*400*3600/4000 = 3600 N -> M = 648,000 N*mm -> sigma = 10.35 MPa.
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(10.352, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.265124, rel=1e-4)


def test_simply_supported_partial_uniform_load_degenerates_to_the_full_udl():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    partial = simply_supported_partial_uniform_load(
        distributed_load=_q("1 N/mm"), loaded_length=_q("500 mm"), **kw
    )
    full = simply_supported_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    assert partial.max_bending_stress.to("MPa").magnitude == pytest.approx(
        full.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert partial.max_deflection.to("mm").magnitude == pytest.approx(
        full.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_partial_uniform_load_sits_between_its_bracketing_idealizations():
    # Spreading the same total load over the whole span understates the demand;
    # concentrating it at its centroid overstates it. The half-span patch of
    # intensity w sits strictly between (M: wL^2/16 < 0.0703*wL^2 < 7*wL^2/64).
    kw = {
        "length": _q("2 m"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    patch = simply_supported_partial_uniform_load(
        distributed_load=_q("1 N/mm"), loaded_length=_q("1 m"), **kw
    )
    spread = simply_supported_uniform_load(distributed_load=_q("0.5 N/mm"), **kw)
    concentrated = simply_supported_offset_load(
        force=_q("1000 N"),  # the patch total, at its centroid L/4
        load_position=_q("500 mm"),
        **kw,
    )
    patch_stress = patch.max_bending_stress.to("MPa").magnitude
    assert spread.max_bending_stress.to("MPa").magnitude < patch_stress
    assert patch_stress < concentrated.max_bending_stress.to("MPa").magnitude


def test_simply_supported_partial_uniform_load_rejects_bad_inputs():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for loaded_length in ("0 mm", "600 mm"):
        with pytest.raises(ValueError, match="loaded_length must lie within the span"):
            simply_supported_partial_uniform_load(
                distributed_load=_q("1 N/mm"), loaded_length=_q(loaded_length), **kw
            )
    with pytest.raises(ValueError, match="distributed_load must be a"):
        simply_supported_partial_uniform_load(
            distributed_load=_q("100 N"),  # a force, not force-per-length
            loaded_length=_q("250 mm"),
            **kw,
        )


def test_simply_supported_center_patch_load_matches_worked_example():
    # 10 N/mm over the middle 800 mm of a 2 m span, 80x120x5 box (I = 3,755,833
    # mm^4, c = 60): M = w*a*(2L-a)/8 = 3,200,000 N*mm -> sigma = M*c/I = 51.12
    # MPa; delta = w*a*(8L^3-4a^2L+a^3)/(384EI) = 1.64722 mm at mid-span
    # (verified against a numeric double-integration of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = simply_supported_center_patch_load(
        distributed_load=_q("10 N/mm"),
        loaded_length=_q("800 mm"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(51.115, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(1.64722, rel=1e-4)


def test_simply_supported_center_patch_load_degenerates_to_the_full_udl():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    patch = simply_supported_center_patch_load(
        distributed_load=_q("1 N/mm"), loaded_length=_q("500 mm"), **kw
    )
    full = simply_supported_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    assert patch.max_bending_stress.to("MPa").magnitude == pytest.approx(
        full.max_bending_stress.to("MPa").magnitude, rel=1e-9
    )
    assert patch.max_deflection.to("mm").magnitude == pytest.approx(
        full.max_deflection.to("mm").magnitude, rel=1e-9
    )


def test_center_patch_sits_between_the_end_patch_and_the_center_point_load():
    # The same patch parked mid-span is harsher than against a support (the load
    # sits farther from the reactions), but milder than its total concentrated
    # at mid-span.
    kw = {
        "length": _q("2 m"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    center = simply_supported_center_patch_load(
        distributed_load=_q("10 N/mm"), loaded_length=_q("800 mm"), **kw
    )
    end = simply_supported_partial_uniform_load(
        distributed_load=_q("10 N/mm"), loaded_length=_q("800 mm"), **kw
    )
    point = simply_supported_center_load(force=_q("8 kN"), **kw)  # the patch total
    stresses = [r.max_bending_stress.to("MPa").magnitude for r in (end, center, point)]
    assert stresses == sorted(stresses)


def test_simply_supported_center_patch_load_rejects_bad_inputs():
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    for loaded_length in ("0 mm", "600 mm"):
        with pytest.raises(ValueError, match="loaded_length must lie within the span"):
            simply_supported_center_patch_load(
                distributed_load=_q("1 N/mm"), loaded_length=_q(loaded_length), **kw
            )
    with pytest.raises(ValueError, match="distributed_load must be a"):
        simply_supported_center_patch_load(
            distributed_load=_q("100 N"),  # a force, not force-per-length
            loaded_length=_q("250 mm"),
            **kw,
        )


def test_simply_supported_triangular_load_matches_worked_example():
    # 10 N/mm peak over a 2 m span, 80x120x5 box (I = 3,755,833 mm^4, c = 60):
    #   M_max = w0*L^2/(9*sqrt(3)) = 2,566,001 N*mm -> sigma = M*c/I = 40.99 MPa;
    #   delta_max = 0.0065223*w0*L^4/(E*I) = 1.3892 mm (at 0.519*L, not mid-span).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = simply_supported_triangular_load(
        peak_distributed_load=_q("10 N/mm"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(40.992, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(1.3892, rel=1e-3)


def test_triangular_load_sits_between_the_bracketing_uniform_loads():
    # A triangle peaking at w0 carries half the total of a w0 UDL, so it must be
    # milder than the full UDL — but harsher than a UDL of the same total load
    # (w0/2), because the triangle biases the load toward one support.
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    tri = simply_supported_triangular_load(peak_distributed_load=_q("1 N/mm"), **kw)
    full = simply_supported_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    same_total = simply_supported_uniform_load(distributed_load=_q("0.5 N/mm"), **kw)
    tri_stress = tri.max_bending_stress.to("MPa").magnitude
    assert same_total.max_bending_stress.to("MPa").magnitude < tri_stress
    assert tri_stress < full.max_bending_stress.to("MPa").magnitude
    tri_deflection = tri.max_deflection.to("mm").magnitude
    assert same_total.max_deflection.to("mm").magnitude < tri_deflection
    assert tri_deflection < full.max_deflection.to("mm").magnitude


def test_simply_supported_triangular_load_rejects_point_load_units():
    with pytest.raises(ValueError, match="peak_distributed_load must be a"):
        simply_supported_triangular_load(
            peak_distributed_load=_q("100 N"),  # a force, not force-per-length
            length=_q("500 mm"),
            second_moment=rectangular_second_moment(_q("20 mm"), _q("10 mm")),
            extreme_fibre=_q("5 mm"),
            elastic_modulus=_q("200 GPa"),
        )


def test_fixed_fixed_triangular_load_matches_worked_example():
    # 10 N/mm peaking at one wall of a 2 m fixed-fixed span, 80x120x5 box
    # (I = 3,755,833 mm^4, c = 60): the peak-end wall governs, M = w0*L^2/20
    # = 2,000,000 N*mm -> sigma = M*c/I = 31.94 MPa; delta_max = 0.27872 mm at
    # xi = (sqrt(105)-5)/10 = 0.525 from the zero end (verified against a
    # numeric double-integration of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = fixed_fixed_triangular_load(
        peak_distributed_load=_q("10 N/mm"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(31.944, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.278721, rel=1e-4)


def test_fixed_fixed_triangular_load_sits_between_the_bracketing_uniform_loads():
    # Same pattern as the simply-supported case: harsher than a UDL of the same
    # total load (w0/2: M = w0*L^2/24 < w0*L^2/20), milder than the full-peak UDL
    # (M = w0*L^2/12) — and stiffer on both counts than the same triangle on
    # simple supports (M = w0*L^2/(9*sqrt(3)) = w0*L^2/15.6).
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    tri = fixed_fixed_triangular_load(peak_distributed_load=_q("1 N/mm"), **kw)
    full = fixed_fixed_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    same_total = fixed_fixed_uniform_load(distributed_load=_q("0.5 N/mm"), **kw)
    simple = simply_supported_triangular_load(peak_distributed_load=_q("1 N/mm"), **kw)
    tri_stress = tri.max_bending_stress.to("MPa").magnitude
    assert same_total.max_bending_stress.to("MPa").magnitude < tri_stress
    assert tri_stress < full.max_bending_stress.to("MPa").magnitude
    assert tri_stress < simple.max_bending_stress.to("MPa").magnitude
    assert tri.max_deflection.to("mm").magnitude < simple.max_deflection.to("mm").magnitude


def test_fixed_fixed_triangular_load_rejects_point_load_units():
    with pytest.raises(ValueError, match="peak_distributed_load must be a"):
        fixed_fixed_triangular_load(
            peak_distributed_load=_q("100 N"),  # a force, not force-per-length
            length=_q("500 mm"),
            second_moment=rectangular_second_moment(_q("20 mm"), _q("10 mm")),
            extreme_fibre=_q("5 mm"),
            elastic_modulus=_q("200 GPa"),
        )


def test_fixed_pinned_triangular_load_matches_worked_example():
    # 10 N/mm peaking at the WALL of a 2 m propped cantilever, 80x120x5 box
    # (I = 3,755,833 mm^4, c = 60): the wall moment governs, M = w0*L^2/15
    # = 2,666,667 N*mm -> sigma = M*c/I = 42.60 MPa; delta_max = 0.50804 mm at
    # exactly 1/sqrt(5) of the span from the prop (verified against a numeric
    # double-integration of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = fixed_pinned_triangular_load(
        peak_distributed_load=_q("10 N/mm"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(42.599, rel=1e-3)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.508039, rel=1e-4)


def test_triangular_load_orders_across_the_support_conditions():
    # With the peak at the wall, propping concentrates moment INTO the wall: the
    # fixed-pinned wall moment w0*L^2/15 exceeds even the simply-supported
    # maximum w0*L^2/(9*sqrt(3)) — while its deflection still sits between the
    # fixed-fixed and simply-supported cases.
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    ff = fixed_fixed_triangular_load(peak_distributed_load=_q("1 N/mm"), **kw)
    fp = fixed_pinned_triangular_load(peak_distributed_load=_q("1 N/mm"), **kw)
    ss = simply_supported_triangular_load(peak_distributed_load=_q("1 N/mm"), **kw)
    stresses = [r.max_bending_stress.to("MPa").magnitude for r in (ff, ss, fp)]
    assert stresses == sorted(stresses)
    deflections = [r.max_deflection.to("mm").magnitude for r in (ff, fp, ss)]
    assert deflections == sorted(deflections)


def test_fixed_pinned_triangular_load_peak_at_prop_matches_worked_example():
    # 10 N/mm peaking at the PROP of a 2 m propped cantilever, same 80x120x5 box
    # as the peak-at-wall example: the wall moment still governs, M = 7*w0*L^2/120
    # = 2,333,333 N*mm -> sigma = M*c/I = 37.275 MPa; delta_max = 0.649256 mm at
    # the root of 10*xi^3 - 27*xi + 14, xi = 0.597538 of the span from the wall
    # (verified against a numeric double-integration of the beam ODE).
    section = CrossSection.hollow_rectangular(
        width=_q("80 mm"), height=_q("120 mm"), wall_thickness=_q("5 mm")
    )
    result = fixed_pinned_triangular_load_peak_at_prop(
        peak_distributed_load=_q("10 N/mm"),
        length=_q("2 m"),
        second_moment=section.second_moment,
        extreme_fibre=section.extreme_fibre,
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(37.2753, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(0.649256, rel=1e-4)


def test_fixed_pinned_triangle_orientations_superpose_to_the_full_udl():
    # The two triangle orientations sum to a full UDL, and both peak moments sit
    # at the wall, so the wall moments superpose EXACTLY: w0*L^2/15 + 7*w0*L^2/120
    # = w0*L^2/8, the fixed-pinned UDL wall moment. Sliding the peak toward the
    # prop relieves the wall (lower stress) but loads the softer mid-span region
    # (larger deflection).
    kw = {
        "length": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    wall_peak = fixed_pinned_triangular_load(peak_distributed_load=_q("1 N/mm"), **kw)
    prop_peak = fixed_pinned_triangular_load_peak_at_prop(peak_distributed_load=_q("1 N/mm"), **kw)
    udl = fixed_pinned_uniform_load(distributed_load=_q("1 N/mm"), **kw)
    combined = (
        wall_peak.max_bending_stress.to("MPa").magnitude
        + prop_peak.max_bending_stress.to("MPa").magnitude
    )
    assert combined == pytest.approx(udl.max_bending_stress.to("MPa").magnitude, rel=1e-12)
    assert (
        prop_peak.max_bending_stress.to("MPa").magnitude
        < wall_peak.max_bending_stress.to("MPa").magnitude
    )
    assert prop_peak.max_deflection.to("mm").magnitude > wall_peak.max_deflection.to("mm").magnitude


def test_fixed_pinned_triangular_load_peak_at_prop_rejects_point_load_units():
    with pytest.raises(ValueError, match="peak_distributed_load must be a"):
        fixed_pinned_triangular_load_peak_at_prop(
            peak_distributed_load=_q("100 N"),  # a force, not force-per-length
            length=_q("500 mm"),
            second_moment=rectangular_second_moment(_q("20 mm"), _q("10 mm")),
            extreme_fibre=_q("5 mm"),
            elastic_modulus=_q("200 GPa"),
        )


def test_fixed_pinned_triangular_load_rejects_point_load_units():
    with pytest.raises(ValueError, match="peak_distributed_load must be a"):
        fixed_pinned_triangular_load(
            peak_distributed_load=_q("100 N"),  # a force, not force-per-length
            length=_q("500 mm"),
            second_moment=rectangular_second_moment(_q("20 mm"), _q("10 mm")),
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


def test_johnson_and_euler_meet_at_transition_slenderness():
    # Sy=250 MPa, E=200 GPa: transition lambda_1 = pi*sqrt(2E/Sy) = 125.66.
    sy, e = _q("250 MPa"), _q("200 GPa")
    lam1 = transition_slenderness(yield_strength=sy, elastic_modulus=e)
    assert lam1 == pytest.approx(125.66, rel=1e-3)
    # At lambda_1 the Johnson parabola meets Euler at exactly Sy/2 = 125 MPa.
    johnson_at_transition = johnson_critical_stress(
        yield_strength=sy, elastic_modulus=e, slenderness_ratio=lam1
    )
    assert johnson_at_transition.to("MPa").magnitude == pytest.approx(125.0, rel=1e-4)
    euler_at_transition = euler_critical_stress(elastic_modulus=e, slenderness_ratio=lam1)
    assert euler_at_transition.to("MPa").magnitude == pytest.approx(125.0, rel=1e-4)


def test_johnson_critical_stress_worked_example():
    # lambda=50 (an intermediate column): sigma_cr = Sy[1 - Sy*lambda^2/(4pi^2 E)]
    #   = 250*[1 - 250*2500/(4pi^2*200000)] = 230.2 MPa (below Sy, above Euler's).
    sigma = johnson_critical_stress(
        yield_strength=_q("250 MPa"), elastic_modulus=_q("200 GPa"), slenderness_ratio=50.0
    )
    assert sigma.to("MPa").magnitude == pytest.approx(230.2, rel=1e-3)


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


def test_spring_index_and_wahl_factor():
    # D=20 mm, d=2 mm: C = 10; Wahl Kw = (4*10-1)/(4*10-4) + 0.615/10 = 1.1448.
    c = spring_index(mean_coil_diameter=_q("20 mm"), wire_diameter=_q("2 mm"))
    assert c == pytest.approx(10.0)
    assert wahl_factor(c) == pytest.approx(1.14483, rel=1e-4)


def test_spring_shear_stress_worked_example():
    # 100 N on the C=10 spring: tau = Kw*8*F*D/(pi*d^3)
    #   = 1.14483 * 8*100*20 / (pi*2^3) = 728.8 MPa.
    tau = spring_shear_stress(
        force=_q("100 N"), mean_coil_diameter=_q("20 mm"), wire_diameter=_q("2 mm")
    )
    assert tau.to("MPa").magnitude == pytest.approx(728.8, rel=1e-3)


def test_spring_rejects_wire_wider_than_coil():
    with pytest.raises(ValueError, match="must be positive and below"):
        spring_index(mean_coil_diameter=_q("5 mm"), wire_diameter=_q("5 mm"))


def test_key_stresses_worked_example():
    # 50 N*m through a 20 mm shaft, 6x6x25 mm key: F = 2T/d = 5000 N;
    #   shear tau = F/(w*L) = 5000/(6*25) = 33.33 MPa;
    #   bearing sigma = F/((h/2)*L) = 5000/(3*25) = 66.67 MPa (2x the shear).
    torque, shaft = _q("50 N*m"), _q("20 mm")
    assert key_tangential_force(torque=torque, shaft_diameter=shaft).to(
        "N"
    ).magnitude == pytest.approx(5000.0, rel=1e-6)
    tau = key_shear_stress(
        torque=torque, shaft_diameter=shaft, key_width=_q("6 mm"), key_length=_q("25 mm")
    )
    assert tau.to("MPa").magnitude == pytest.approx(33.333, rel=1e-4)
    sigma = key_bearing_stress(
        torque=torque, shaft_diameter=shaft, key_height=_q("6 mm"), key_length=_q("25 mm")
    )
    assert sigma.to("MPa").magnitude == pytest.approx(66.667, rel=1e-4)
    assert sigma.to("MPa").magnitude == pytest.approx(2 * tau.to("MPa").magnitude, rel=1e-6)


def test_key_stress_rejects_non_torque():
    with pytest.raises(ValueError, match="torque must be a"):
        key_tangential_force(torque=_q("50 N"), shaft_diameter=_q("20 mm"))


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


def test_hollow_shaft_twist_angle_matches_worked_example():
    # 50 N*m over a 1 m, 20/10 mm steel tube, G=77 GPa: J = 14726 mm^4,
    #   theta = T*L/(G*J) = 50 / (77e9 * 14726e-12) = 0.0441 rad = 2.527 deg.
    theta = hollow_shaft_twist_angle(
        torque=_q("50 N*m"),
        length=_q("1 m"),
        outer_diameter=_q("20 mm"),
        inner_diameter=_q("10 mm"),
        shear_modulus=_q("77 GPa"),
    )
    assert theta.to("degree").magnitude == pytest.approx(2.527, rel=1e-3)
    # A tube twists more than a solid shaft of the same OD (less material).
    solid = shaft_twist_angle(
        torque=_q("50 N*m"),
        length=_q("1 m"),
        diameter=_q("20 mm"),
        shear_modulus=_q("77 GPa"),
    )
    assert theta.to("degree").magnitude > solid.to("degree").magnitude


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


def test_thin_wall_sphere_is_half_the_cylinder_hoop():
    # 2 MPa, 100 mm radius, 5 mm wall: sphere sigma = p*r/2t = 20 MPa, which is
    # half the cylinder hoop (40 MPa) for the same geometry.
    sphere = thin_wall_sphere_stress(
        pressure=_q("2 MPa"), radius=_q("100 mm"), wall_thickness=_q("5 mm")
    )
    assert sphere.to("MPa").magnitude == pytest.approx(20.0, rel=1e-6)
    cyl = thin_wall_cylinder(pressure=_q("2 MPa"), radius=_q("100 mm"), wall_thickness=_q("5 mm"))
    assert sphere.to("MPa").magnitude == pytest.approx(cyl.hoop_stress.to("MPa").magnitude / 2)


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


def test_interference_fit_matches_hand_calc():
    # Same-material solid shaft, E=200 GPa, d=50, D=100, radial interference 0.02 mm.
    # Same material + solid shaft collapses Shigley's form to p = δ·E·(D²−d²)/(d·D²)
    #   = 0.02*200000*7500/(50*10000) = 60 MPa;
    # hub bore hoop = p·(D²+d²)/(D²−d²) = 60*1.6667 = 100 MPa (tensile);
    # solid shaft surface hoop = −p = −60 MPa.
    fit = interference_fit(
        radial_interference=_q("0.02 mm"),
        interface_diameter=_q("50 mm"),
        hub_outer_diameter=_q("100 mm"),
        hub_modulus=_q("200 GPa"),
        hub_poisson=0.3,
        shaft_modulus=_q("200 GPa"),
        shaft_poisson=0.3,
    )
    assert fit.contact_pressure.to("MPa").magnitude == pytest.approx(60.0, rel=1e-6)
    assert fit.hub_hoop_stress.to("MPa").magnitude == pytest.approx(100.0, rel=1e-6)
    assert fit.shaft_hoop_stress.to("MPa").magnitude == pytest.approx(-60.0, rel=1e-6)
    assert fit.hub_safety_factor(_q("250 MPa")) == pytest.approx(2.5, rel=1e-6)


def test_interference_fit_hollow_shaft_lowers_pressure():
    # Boring the shaft makes it more compliant, so the same interference develops
    # a lower contact pressure than the solid shaft above.
    solid = interference_fit(
        radial_interference=_q("0.02 mm"),
        interface_diameter=_q("50 mm"),
        hub_outer_diameter=_q("100 mm"),
        hub_modulus=_q("200 GPa"),
        hub_poisson=0.3,
        shaft_modulus=_q("200 GPa"),
        shaft_poisson=0.3,
    )
    hollow = interference_fit(
        radial_interference=_q("0.02 mm"),
        interface_diameter=_q("50 mm"),
        hub_outer_diameter=_q("100 mm"),
        hub_modulus=_q("200 GPa"),
        hub_poisson=0.3,
        shaft_modulus=_q("200 GPa"),
        shaft_poisson=0.3,
        shaft_bore_diameter=_q("30 mm"),
    )
    assert hollow.contact_pressure.to("MPa").magnitude < solid.contact_pressure.to("MPa").magnitude


def test_hertz_sphere_contact_matches_hand_calc():
    # Two Ø20 mm steel spheres (E=200 GPa, nu=0.3), 100 N:
    #   1/E* = 2*(1-0.09)/200000 -> E* = 109890 MPa; R = 5 mm (1/R = 1/10 + 1/10);
    #   a = (3*100*5/(4*109890))**(1/3) = 0.15055 mm; p_max = 3*100/(2*pi*a^2) = 2106 MPa.
    c = hertz_sphere_contact(
        force=_q("100 N"),
        diameter1=_q("20 mm"),
        diameter2=_q("20 mm"),
        modulus1=_q("200 GPa"),
        poisson1=0.3,
        modulus2=_q("200 GPa"),
        poisson2=0.3,
    )
    assert c.contact_radius.to("mm").magnitude == pytest.approx(0.150554, rel=1e-4)
    assert c.max_contact_pressure.to("MPa").magnitude == pytest.approx(2106.5, rel=1e-4)
    assert c.surface_safety_factor(_q("2000 MPa")) == pytest.approx(2000 / 2106.5, rel=1e-4)


def test_hertz_sphere_on_flat_softens_the_contact():
    # A sphere on a flat has R = R1 (the flat's 1/R2 -> 0), double the effective
    # radius of two equal spheres, so the patch is larger and the peak pressure
    # lower than the two-sphere case above.
    two = hertz_sphere_contact(
        force=_q("100 N"),
        diameter1=_q("20 mm"),
        diameter2=_q("20 mm"),
        modulus1=_q("200 GPa"),
        poisson1=0.3,
        modulus2=_q("200 GPa"),
        poisson2=0.3,
    )
    flat = hertz_sphere_contact(
        force=_q("100 N"),
        diameter1=_q("20 mm"),
        modulus1=_q("200 GPa"),
        poisson1=0.3,
        modulus2=_q("200 GPa"),
        poisson2=0.3,
    )
    assert flat.contact_radius.to("mm").magnitude > two.contact_radius.to("mm").magnitude
    assert (
        flat.max_contact_pressure.to("MPa").magnitude < two.max_contact_pressure.to("MPa").magnitude
    )


def test_hertz_cylinder_contact_matches_hand_calc():
    # Two Ø20 mm steel cylinders (E=200 GPa, nu=0.3), 1000 N over 50 mm length:
    #   1/E* = 2*(1-0.09)/200000 = 9.1e-6; 1/d1+1/d2 = 0.1 /mm;
    #   b = sqrt((2*1000/(pi*50)) * 9.1e-6 / 0.1) = 0.034039 mm;
    #   p_max = 2*1000/(pi*b*50) = 374.05 MPa.
    c = hertz_cylinder_contact(
        force=_q("1000 N"),
        length=_q("50 mm"),
        diameter1=_q("20 mm"),
        diameter2=_q("20 mm"),
        modulus1=_q("200 GPa"),
        poisson1=0.3,
        modulus2=_q("200 GPa"),
        poisson2=0.3,
    )
    assert c.half_width.to("mm").magnitude == pytest.approx(0.0340389, rel=1e-4)
    assert c.max_contact_pressure.to("MPa").magnitude == pytest.approx(374.05, rel=1e-4)
    assert c.surface_safety_factor(_q("400 MPa")) == pytest.approx(400 / 374.05, rel=1e-4)


def test_hertz_cylinder_on_flat_softens_the_contact():
    # A cylinder on a flat (1/d2 -> 0) spreads the load wider than two equal
    # cylinders, so the peak pressure is lower.
    two = hertz_cylinder_contact(
        force=_q("1000 N"),
        length=_q("50 mm"),
        diameter1=_q("20 mm"),
        diameter2=_q("20 mm"),
        modulus1=_q("200 GPa"),
        poisson1=0.3,
        modulus2=_q("200 GPa"),
        poisson2=0.3,
    )
    flat = hertz_cylinder_contact(
        force=_q("1000 N"),
        length=_q("50 mm"),
        diameter1=_q("20 mm"),
        modulus1=_q("200 GPa"),
        poisson1=0.3,
        modulus2=_q("200 GPa"),
        poisson2=0.3,
    )
    assert (
        flat.max_contact_pressure.to("MPa").magnitude < two.max_contact_pressure.to("MPa").magnitude
    )


def test_hertz_cylinder_contact_rejects_nonpositive_length():
    with pytest.raises(ValueError, match="length must be positive"):
        hertz_cylinder_contact(
            force=_q("1000 N"),
            length=_q("0 mm"),
            diameter1=_q("20 mm"),
            modulus1=_q("200 GPa"),
            poisson1=0.3,
            modulus2=_q("200 GPa"),
            poisson2=0.3,
        )


def test_hertz_sphere_contact_rejects_bad_inputs():
    with pytest.raises(ValueError, match="force must be a"):
        hertz_sphere_contact(
            force=_q("100 mm"),  # not a force
            diameter1=_q("20 mm"),
            modulus1=_q("200 GPa"),
            poisson1=0.3,
            modulus2=_q("200 GPa"),
            poisson2=0.3,
        )
    with pytest.raises(ValueError, match="diameter1 must be positive"):
        hertz_sphere_contact(
            force=_q("100 N"),
            diameter1=_q("0 mm"),
            modulus1=_q("200 GPa"),
            poisson1=0.3,
            modulus2=_q("200 GPa"),
            poisson2=0.3,
        )


def test_interference_holding_capacity_matches_hand_calc():
    # p=110 MPa on a Ø40 x 60 mm engagement, mu=0.15:
    #   contact area = pi*d*L = pi*40*60 = 7539.82 mm^2; normal = 110*area = 829380 N;
    #   axial push-out = mu*normal = 124407 N; torque = axial*(d/2) = 2488.1 N*m.
    kw = {
        "interface_diameter": _q("40 mm"),
        "engagement_length": _q("60 mm"),
        "friction_coefficient": 0.15,
    }
    axial = interference_axial_capacity(_q("110 MPa"), **kw)
    torque = interference_torque_capacity(_q("110 MPa"), **kw)
    assert axial.to("N").magnitude == pytest.approx(124407.0, rel=1e-4)
    assert torque.to("N*m").magnitude == pytest.approx(2488.1, rel=1e-4)
    # Torque is exactly the axial capacity acting at the shaft radius.
    assert torque.to("N*m").magnitude == pytest.approx(axial.to("N").magnitude * 0.020, rel=1e-6)


def test_interference_capacity_rejects_bad_friction():
    with pytest.raises(ValueError, match="friction_coefficient must be positive"):
        interference_axial_capacity(
            _q("110 MPa"),
            interface_diameter=_q("40 mm"),
            engagement_length=_q("60 mm"),
            friction_coefficient=0.0,
        )


def test_interference_fit_rejects_bad_geometry():
    with pytest.raises(ValueError, match="hub_outer_diameter > interface_diameter"):
        interference_fit(
            radial_interference=_q("0.02 mm"),
            interface_diameter=_q("100 mm"),  # not smaller than the hub OD
            hub_outer_diameter=_q("100 mm"),
            hub_modulus=_q("200 GPa"),
            hub_poisson=0.3,
            shaft_modulus=_q("200 GPa"),
            shaft_poisson=0.3,
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


def test_constrained_thermal_stress_worked_example():
    # A fully-restrained steel bar heated 50 K: sigma = E*alpha*dT
    #   = 200000 * 12e-6 * 50 = 120 MPa.
    sigma = constrained_thermal_stress(
        elastic_modulus=_q("200 GPa"),
        thermal_expansion_coefficient=_q("12e-6 / K"),
        temperature_change=_q("50 K"),
    )
    assert sigma.to("MPa").magnitude == pytest.approx(120.0, rel=1e-6)
    # A temperature difference in delta_degC gives the same magnitude.
    same = constrained_thermal_stress(
        elastic_modulus=_q("200 GPa"),
        thermal_expansion_coefficient=_q("12e-6 / delta_degC"),
        temperature_change=_q("50 delta_degC"),
    )
    assert same.to("MPa").magnitude == pytest.approx(120.0, rel=1e-6)


def test_constrained_thermal_stress_rejects_bad_units():
    with pytest.raises(ValueError, match="thermal_expansion_coefficient"):
        constrained_thermal_stress(
            elastic_modulus=_q("200 GPa"),
            thermal_expansion_coefficient=_q("12 mm"),  # not 1/temperature
            temperature_change=_q("50 K"),
        )


def test_natural_frequency_sdof():
    # k = 8000 N/m, m = 1 kg: fn = (1/2pi)*sqrt(8000/1) = 14.24 Hz.
    fn = natural_frequency(stiffness=_q("8000 N/m"), mass=_q("1 kg"))
    assert fn.to("Hz").magnitude == pytest.approx(14.235, rel=1e-3)


def test_natural_frequency_from_a_beam_stiffness():
    # A beam with 100 N producing 12.5 mm deflection has k = F/delta = 8 N/mm =
    # 8000 N/m; carrying a 1 kg mass it resonates at 14.24 Hz.
    inertia = rectangular_second_moment(_q("20 mm"), _q("10 mm"))
    beam = cantilever_end_load(
        force=_q("100 N"),
        length=_q("500 mm"),
        second_moment=inertia,
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    k_n_per_mm = 100.0 / beam.max_deflection.to("mm").magnitude  # 8 N/mm
    fn = natural_frequency(stiffness=_q(f"{k_n_per_mm} N/mm"), mass=_q("1 kg"))
    assert fn.to("Hz").magnitude == pytest.approx(14.235, rel=1e-3)


def test_rayleigh_frequency_from_self_weight_deflection():
    # fn = (1/2pi)*sqrt(g/delta); delta = 12.5 mm -> 4.458 Hz.
    fn = natural_frequency_from_deflection(_q("12.5 mm"))
    assert fn.to("Hz").magnitude == pytest.approx(4.458, rel=1e-3)


def test_frequency_scorecard_resonance_screen():
    from anvilate.scorecard import CheckStatus

    fn = natural_frequency(stiffness=_q("8000 N/m"), mass=_q("1 kg"))  # 14.24 Hz
    ok = frequency_scorecard("resonance", frequency=fn, min_frequency=_q("10 Hz"))
    assert ok.status is CheckStatus.PASS
    bad = frequency_scorecard("resonance", frequency=fn, min_frequency=_q("20 Hz"))
    assert bad.status is CheckStatus.FAIL
    # No silent green: no operating-frequency requirement -> NOT_EVALUATED.
    none = frequency_scorecard("resonance", frequency=fn, min_frequency=None)
    assert none.status is CheckStatus.NOT_EVALUATED
    assert not none.passed


def test_natural_frequency_rejects_bad_inputs():
    with pytest.raises(ValueError, match="stiffness must be a"):
        natural_frequency(stiffness=_q("100 N"), mass=_q("1 kg"))  # force, not stiffness
    with pytest.raises(ValueError, match="static_deflection must be positive"):
        natural_frequency_from_deflection(_q("0 mm"))


_BEAM_MODAL_KW = {
    "mass_per_length": _q("1.57 kg/m"),  # a 20x10 mm steel bar (7850 kg/m^3)
    "length": _q("500 mm"),
    "second_moment": _q("1666.6667 mm**4"),
    "elastic_modulus": _q("200 GPa"),
}


def test_beam_fundamental_frequencies_match_worked_example():
    # sqrt(E*I/(m*L^4)) = sqrt(333.333/(1.57*0.0625)) = 58.284 rad/s; f1 =
    # lambda1^2 * 58.284 / (2*pi): cantilever 3.51602 -> 32.62 Hz, simply
    # supported pi^2 -> 91.55, fixed-pinned 15.41821 -> 143.02, fixed-fixed
    # 22.37329 -> 207.54 (Blevins Table 8-1 eigenvalues, verified against
    # their characteristic equations by bisection).
    assert cantilever_fundamental_frequency(**_BEAM_MODAL_KW).to("Hz").magnitude == pytest.approx(
        32.615, rel=1e-4
    )
    assert simply_supported_fundamental_frequency(**_BEAM_MODAL_KW).to(
        "Hz"
    ).magnitude == pytest.approx(91.552, rel=1e-4)
    assert fixed_pinned_fundamental_frequency(**_BEAM_MODAL_KW).to("Hz").magnitude == pytest.approx(
        143.022, rel=1e-4
    )
    assert fixed_fixed_fundamental_frequency(**_BEAM_MODAL_KW).to("Hz").magnitude == pytest.approx(
        207.539, rel=1e-4
    )


def test_beam_fundamentals_order_by_end_fixity():
    # More fixity -> stiffer first mode: cantilever < ss < fixed-pinned < ff.
    values = [
        f(**_BEAM_MODAL_KW).to("Hz").magnitude
        for f in (
            cantilever_fundamental_frequency,
            simply_supported_fundamental_frequency,
            fixed_pinned_fundamental_frequency,
            fixed_fixed_fundamental_frequency,
        )
    ]
    assert values == sorted(values)


def test_simply_supported_fundamental_exceeds_rayleigh_by_the_exact_ratio():
    # The Rayleigh shortcut reads the mid-span self-weight deflection delta =
    # 5*m*g*L^4/(384*E*I), so its estimate trails the exact pi^2 eigenvalue by
    # exactly pi^2/sqrt(384/5) = 1.1262 — the shortcut is always conservative
    # on a simply-supported span.
    m = _BEAM_MODAL_KW["mass_per_length"].to("kg/m").magnitude
    length_m = _BEAM_MODAL_KW["length"].to("m").magnitude
    e_i = 200e9 * _BEAM_MODAL_KW["second_moment"].to("m**4").magnitude
    g = 9.80665
    delta = 5 * m * g * length_m**4 / (384 * e_i)
    rayleigh = natural_frequency_from_deflection(Quantity(magnitude=delta, unit="m"))
    exact = simply_supported_fundamental_frequency(**_BEAM_MODAL_KW)
    ratio = exact.to("Hz").magnitude / rayleigh.to("Hz").magnitude
    assert ratio == pytest.approx(pi**2 / (384 / 5) ** 0.5, rel=1e-9)


def test_square_plate_reproduces_the_handbook_coefficients():
    # A 500 x 500 x 6 mm simply-supported steel cover under 50 kPa: the exact
    # Navier series must land on the classic Roark/Timoshenko coefficients
    # (nu = 0.3): sigma = 0.2874*q*b^2/t^2 = 99.8 MPa and
    # w = 0.0444*q*b^4/(E*t^3) = 3.21 mm.
    result = simply_supported_plate_uniform_load(
        pressure=_q("50 kPa"),
        length=_q("500 mm"),
        width=_q("500 mm"),
        thickness=_q("6 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    q, b, t = 0.05, 500.0, 6.0
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(
        0.2874 * q * b**2 / t**2, rel=2e-3
    )
    assert result.max_deflection.to("mm").magnitude == pytest.approx(
        0.0444 * q * b**4 / (200000 * t**3), rel=2e-3
    )


def test_two_to_one_plate_matches_the_handbook_beta():
    # Stretching the plate 2:1 raises the stress coefficient to beta = 0.6102
    # (the short span carries the load); the result must also be orientation-
    # blind (length/width swapped exactly).
    kw = {
        "pressure": _q("50 kPa"),
        "thickness": _q("6 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    wide = simply_supported_plate_uniform_load(length=_q("1000 mm"), width=_q("500 mm"), **kw)
    tall = simply_supported_plate_uniform_load(length=_q("500 mm"), width=_q("1000 mm"), **kw)
    assert wide.max_bending_stress.to("MPa").magnitude == pytest.approx(
        0.6102 * 0.05 * 500.0**2 / 36.0, rel=2e-3
    )
    assert wide.max_bending_stress.to("MPa").magnitude == pytest.approx(
        tall.max_bending_stress.to("MPa").magnitude, rel=1e-12
    )
    assert wide.max_deflection.to("mm").magnitude == pytest.approx(
        tall.max_deflection.to("mm").magnitude, rel=1e-12
    )


def test_plate_rejects_bad_inputs():
    kw = {
        "length": _q("500 mm"),
        "width": _q("500 mm"),
        "thickness": _q("6 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    with pytest.raises(ValueError, match="pressure must be a"):
        simply_supported_plate_uniform_load(pressure=_q("50 N"), **kw)
    with pytest.raises(ValueError, match="poisson_ratio must lie in"):
        simply_supported_plate_uniform_load(pressure=_q("50 kPa"), poisson_ratio=0.6, **kw)


def test_torsional_natural_frequency_matches_worked_example():
    # A 5 kg, 200 mm flywheel on a 20 mm x 500 mm steel stub (G = 80 GPa):
    # J = pi*20^4/32 = 15708 mm^4 -> k_t = G*J/L = 2513.3 N*m/rad;
    # I = m*d^2/8 = 5*0.04/8 = 0.025 kg*m^2;
    # f_n = sqrt(2513.3/0.025)/(2*pi) = 50.46 Hz.
    stiffness = shaft_torsional_stiffness(
        polar_second_moment=polar_second_moment_solid(_q("20 mm")),
        length=_q("500 mm"),
        shear_modulus=_q("80 GPa"),
    )
    assert stiffness.to("N*m").magnitude == pytest.approx(2513.27, rel=1e-4)
    inertia = solid_disc_polar_mass_moment(mass=_q("5 kg"), diameter=_q("200 mm"))
    assert inertia.to("kg*m**2").magnitude == pytest.approx(0.025, rel=1e-9)
    fn = torsional_natural_frequency(torsional_stiffness=stiffness, polar_mass_moment=inertia)
    assert fn.to("Hz").magnitude == pytest.approx(50.463, rel=1e-4)


def test_torsional_frequency_rejects_bad_inputs():
    with pytest.raises(ValueError, match="torsional_stiffness must be a"):
        torsional_natural_frequency(
            torsional_stiffness=_q("100 N/m"),  # a linear rate, not torque/radian
            polar_mass_moment=_q("0.025 kg*m**2"),
        )
    with pytest.raises(ValueError, match="polar_mass_moment must be a"):
        torsional_natural_frequency(
            torsional_stiffness=_q("2513 N*m"),
            polar_mass_moment=_q("5 kg"),  # a mass, not a rotary inertia
        )
    with pytest.raises(ValueError, match="mass and diameter must be positive"):
        solid_disc_polar_mass_moment(mass=_q("0 kg"), diameter=_q("200 mm"))


def test_beam_fundamental_rejects_bad_inputs():
    with pytest.raises(ValueError, match="mass_per_length must be a"):
        cantilever_fundamental_frequency(
            mass_per_length=_q("5 kg"),  # a lumped mass, not a line density
            length=_q("500 mm"),
            second_moment=_q("1666.6667 mm**4"),
            elastic_modulus=_q("200 GPa"),
        )


def test_von_mises_plane_stress_worked_example():
    # sigma_x=100, sigma_y=0, tau=50 MPa: sqrt(100^2 + 3*50^2) = sqrt(17500) = 132.29.
    vm = von_mises_plane_stress(sigma_x=_q("100 MPa"), sigma_y=_q("0 MPa"), tau_xy=_q("50 MPa"))
    assert vm.to("MPa").magnitude == pytest.approx(132.288, rel=1e-4)


def test_concentrated_stress_applies_kt():
    # A Kt of 2.5 at a fillet raises a 100 MPa nominal stress to 250 MPa.
    peak = concentrated_stress(nominal_stress=_q("100 MPa"), kt=2.5)
    assert peak.to("MPa").magnitude == pytest.approx(250.0, rel=1e-9)


def test_concentrated_stress_rejects_kt_below_one():
    with pytest.raises(ValueError, match="kt must be at least 1"):
        concentrated_stress(nominal_stress=_q("100 MPa"), kt=0.8)


def test_principal_stresses_and_tresca_worked_example():
    # sigma_x=100, sigma_y=0, tau=50: centre 50, radius sqrt(50^2+50^2)=70.71;
    #   sigma_1 = 120.71, sigma_2 = -20.71.
    kw = {"sigma_x": _q("100 MPa"), "sigma_y": _q("0 MPa"), "tau_xy": _q("50 MPa")}
    s1, s2 = principal_stresses_plane(**kw)
    assert s1.to("MPa").magnitude == pytest.approx(120.711, rel=1e-4)
    assert s2.to("MPa").magnitude == pytest.approx(-20.711, rel=1e-4)
    # Tresca eq = sigma_max - sigma_min over {120.71, -20.71, 0} = 141.42 MPa;
    # tau_max is half that.
    tau_max = max_shear_stress_plane(**kw)
    assert tau_max.to("MPa").magnitude == pytest.approx(70.711, rel=1e-4)
    tresca = tresca_equivalent_stress(**kw)
    assert tresca.to("MPa").magnitude == pytest.approx(141.421, rel=1e-4)


def test_tresca_is_never_below_von_mises():
    # Tresca is the conservative criterion: sigma_tresca >= sigma_vm always.
    kw = {"sigma_x": _q("100 MPa"), "sigma_y": _q("0 MPa"), "tau_xy": _q("50 MPa")}
    tresca = tresca_equivalent_stress(**kw).to("MPa").magnitude
    vm = von_mises_plane_stress(**kw).to("MPa").magnitude
    assert tresca >= vm
    assert tresca == pytest.approx(141.421, rel=1e-4)
    assert vm == pytest.approx(132.288, rel=1e-4)


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
