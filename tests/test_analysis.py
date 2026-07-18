"""Tests for the T1 analytical checks, against hand-computed worked examples."""

from __future__ import annotations

from math import pi

import pytest

from anvilate.analysis import (
    ROLLER_BEARING_LIFE_EXPONENT,
    SHEAR_FORM_CIRCULAR,
    SHEAR_FORM_RECTANGULAR,
    SPRING_END_HINGED_HINGED,
    SPRING_END_PARALLEL_PLATES,
    UNIFORM_PRESSURE,
    ColumnEnd,
    CrossSection,
    annular_disc_polar_mass_moment,
    asme_cylinder_thickness,
    axial_stress,
    band_brake_max_lining_pressure,
    band_brake_tight_tension_for_torque,
    band_brake_torque,
    barth_velocity_factor,
    base_excitation_relative_transmissibility,
    base_tangent_length,
    basquin_cycles_to_failure,
    basquin_stress_for_life,
    beam_on_elastic_foundation_max_deflection,
    beam_on_elastic_foundation_max_moment,
    bearing_basic_rating_life,
    bearing_equivalent_dynamic_load,
    bearing_equivalent_static_load,
    bearing_life_hours,
    bearing_reliability_life_factor,
    bearing_static_safety_factor,
    bearing_stress,
    belleville_flat_load,
    belleville_washer_force,
    belt_centrifugal_tension,
    belt_length,
    belt_max_transmissible_force,
    belt_max_transmissible_force_at_speed,
    belt_mean_tension,
    belt_slack_tension,
    belt_speed_for_max_power,
    belt_transmitted_power,
    belt_wrap_angle,
    bevel_gear_axial_load,
    bevel_gear_radial_load,
    bevel_pitch_cone_angle,
    bimetallic_strip_curvature,
    bimetallic_strip_tip_deflection,
    bolt_axial_stiffness,
    bolt_axial_stress,
    bolt_diameter_for_shear,
    bolt_load_in_joint,
    bolt_preload_from_torque,
    bolt_proof_load,
    bolt_shear_stress,
    bolt_tensile_stress_area,
    cam_follower_motion,
    cam_pressure_angle,
    cantilever_center_patch_load,
    cantilever_end_load,
    cantilever_end_moment,
    cantilever_fundamental_frequency,
    cantilever_offset_load,
    cantilever_offset_moment,
    cantilever_partial_uniform_load,
    cantilever_tip_mass_frequency,
    cantilever_triangular_load,
    cantilever_triangular_load_peak_at_tip,
    cantilever_uniform_load,
    capstan_tension_ratio,
    catenary_arc_length,
    catenary_max_tension,
    catenary_sag,
    chain_length_in_pitches,
    chain_speed,
    chordal_speed_variation,
    circular_area,
    circular_curved_beam_stress,
    circular_plastic_section_modulus,
    circular_second_moment,
    clamped_annular_plate_fundamental_frequency,
    clamped_annular_plate_uniform_load,
    clamped_circular_plate_center_load_deflection,
    clamped_circular_plate_fundamental_frequency,
    clamped_circular_plate_thickness_for_pressure,
    clamped_circular_plate_uniform_load,
    clamped_plate_fundamental_frequency,
    clamped_plate_uniform_load,
    coefficient_of_fluctuation,
    combine_axial_bending,
    composite_curved_beam_stress,
    concentrated_stress,
    cone_clutch_torque,
    constrained_thermal_stress,
    critical_crack_length,
    critical_damping_coefficient,
    crossed_belt_length,
    crossed_belt_wrap_angle,
    cyclic_stress_components,
    cylinder_axial_buckling_stress,
    cylinder_external_pressure_buckling,
    damped_natural_frequency,
    deflection_scorecard,
    differential_band_brake_actuation_force,
    differential_band_brake_is_self_locking,
    differential_thermal_stress,
    disc_clutch_force_for_torque,
    disc_clutch_torque,
    dunkerley_fundamental_frequency,
    dynamic_magnification_factor,
    eccentric_shear_group_peak_force,
    elliptical_bar_torsional_stress,
    elliptical_bar_twist_angle,
    elliptical_hole_stress_concentration,
    estimated_endurance_limit,
    euler_buckling_load,
    euler_critical_stress,
    euler_second_moment_for_load,
    fastener_spacing_for_shear_flow,
    fatigue_notch_factor,
    fillet_weld_leg_for_load,
    fillet_weld_throat_stress,
    fixed_fixed_center_load,
    fixed_fixed_center_mass_frequency,
    fixed_fixed_center_patch_load,
    fixed_fixed_fundamental_frequency,
    fixed_fixed_offset_load,
    fixed_fixed_partial_uniform_load,
    fixed_fixed_plastic_collapse_load,
    fixed_fixed_plastic_collapse_udl,
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
    flange_coupling_bolt_force,
    flange_coupling_torque,
    flywheel_energy_fluctuation,
    flywheel_inertia_for_fluctuation,
    foundation_characteristic_parameter,
    fourbar_transmission_angle,
    fourbar_type,
    free_thermal_expansion,
    frequency_scorecard,
    gear_contact_stress,
    gear_normal_load,
    gear_radial_load,
    gear_tangential_load,
    gear_tooth_thickness_at_radius,
    gear_train_efficiency,
    gear_train_value,
    geneva_advance_fraction,
    geneva_crank_radius,
    geneva_driven_radius,
    geneva_dwell_fraction,
    geneva_index_angle,
    gerber_safety_factor,
    gerber_scorecard,
    goodman_equivalent_reversed_stress,
    goodman_safety_factor,
    goodman_scorecard,
    helical_gear_axial_thrust,
    helical_gear_radial_load,
    helical_spring_active_coils_for_rate,
    helical_spring_buckling,
    helical_spring_rate,
    helical_spring_solid_length,
    helical_torsion_spring_rate,
    helical_torsion_spring_stress,
    helical_virtual_teeth,
    hertz_cylinder_contact,
    hertz_effective_modulus,
    hertz_sphere_approach,
    hertz_sphere_contact,
    hollow_circular_plastic_section_modulus,
    hollow_circular_second_moment,
    hollow_shaft_diameter_for_bending_torsion,
    hollow_shaft_torsional_stress,
    hollow_shaft_twist_angle,
    horizontal_impact_force,
    i_section_plastic_section_modulus,
    i_section_second_moment,
    impact_factor,
    impact_stress,
    interference_axial_capacity,
    interference_fit,
    interference_for_contact_pressure,
    interference_torque_capacity,
    involute_angle,
    involute_function,
    is_grashof,
    johnson_critical_stress,
    joint_separation_load,
    joint_stiffness_factor,
    journal_bearing_minimum_film_thickness,
    journal_bearing_unit_load,
    key_bearing_stress,
    key_length_for_torque,
    key_shear_stress,
    key_tangential_force,
    lateral_torsional_buckling_moment,
    lead_angle,
    leaf_spring_rate,
    leaf_spring_stress,
    lewis_bending_stress,
    logarithmic_decrement,
    marin_endurance_limit,
    max_shear_stress_plane,
    max_transverse_shear_stress,
    member_clamp_load_in_joint,
    member_stiffness_frustum,
    miner_cumulative_damage,
    miner_spectrum_repeats_to_failure,
    minimum_teeth_to_avoid_undercut,
    morrow_equivalent_reversed_stress,
    natural_frequency,
    natural_frequency_from_deflection,
    neuber_notch_sensitivity,
    octahedral_shear_stress,
    operating_pressure_angle,
    overhang_tip_load,
    overhang_uniform_load,
    parabolic_cable_length,
    parabolic_cable_max_tension,
    parabolic_cable_sag,
    paris_law_crack_growth_rate,
    paris_law_cycles_to_failure,
    perry_robertson_stress,
    peterson_notch_sensitivity,
    petroff_friction_power,
    petroff_friction_torque,
    physical_pendulum_period,
    pitch_line_velocity,
    planetary_can_assemble,
    planetary_planet_teeth,
    planetary_speed,
    planetary_torques,
    plastic_moment,
    plate_buckling_stress,
    plate_compression_buckling_coefficient,
    plate_shear_buckling_coefficient,
    polar_second_moment_hollow,
    polar_second_moment_solid,
    power_screw_collar_torque,
    power_screw_efficiency,
    power_screw_is_self_locking,
    power_screw_lower_torque,
    power_screw_raise_torque,
    preloaded_bolt_cyclic_stress,
    principal_stresses_plane,
    profile_shift_sum_for_center_distance,
    propped_cantilever_plastic_collapse_load,
    propped_cantilever_plastic_collapse_udl,
    quality_factor,
    radius_of_gyration,
    rankine_gordon_stress,
    recommended_bolt_preload,
    rectangular_bar_torsion_constant,
    rectangular_bar_twist_angle,
    rectangular_curved_beam_stress,
    rectangular_plastic_section_modulus,
    rectangular_second_moment,
    rectangular_tube_enclosed_area,
    rectangular_tube_plastic_section_modulus,
    rectangular_tube_second_moment,
    rectangular_tube_torsional_stress,
    rectangular_tube_twist_angle,
    required_axial_area,
    resonance_phase_angle,
    reverted_train_is_coaxial,
    riveted_joint_efficiency,
    rotating_annular_disc_bore_stress,
    rotating_annular_disc_radial_stress,
    rotating_annular_disc_tangential_stress,
    rotating_rim_burst_speed,
    rotating_rim_hoop_stress,
    rotating_rim_radial_growth,
    rotating_solid_disc_max_stress,
    rotating_solid_disc_radial_stress,
    rotating_solid_disc_tangential_stress,
    scotch_yoke_acceleration,
    scotch_yoke_displacement,
    scotch_yoke_velocity,
    secant_column_max_stress,
    shaft_diameter_for_bending_torsion,
    shaft_diameter_for_torque,
    shaft_torsional_stiffness,
    shaft_torsional_stress,
    shaft_twist_angle,
    shaft_von_mises_stress,
    shear_flow,
    short_shoe_brake_torque,
    short_shoe_is_self_locking,
    short_shoe_normal_force,
    shrink_fit_assembly_temperature,
    simple_pendulum_period,
    simply_supported_annular_plate_fundamental_frequency,
    simply_supported_annular_plate_uniform_load,
    simply_supported_center_load,
    simply_supported_center_mass_frequency,
    simply_supported_center_patch_load,
    simply_supported_circular_plate_center_load_deflection,
    simply_supported_circular_plate_fundamental_frequency,
    simply_supported_circular_plate_uniform_load,
    simply_supported_end_moment,
    simply_supported_fundamental_frequency,
    simply_supported_offset_load,
    simply_supported_offset_moment,
    simply_supported_partial_uniform_load,
    simply_supported_plastic_collapse_load,
    simply_supported_plastic_collapse_udl,
    simply_supported_plate_center_patch_load,
    simply_supported_plate_fundamental_frequency,
    simply_supported_plate_uniform_load,
    simply_supported_symmetric_point_loads,
    simply_supported_triangular_load,
    simply_supported_uniform_load,
    slenderness_ratio,
    slider_crank_acceleration,
    slider_crank_displacement,
    slider_crank_piston_side_thrust,
    slider_crank_velocity,
    smith_watson_topper_stress,
    soderberg_safety_factor,
    soderberg_scorecard,
    solid_disc_polar_mass_moment,
    sommerfeld_number,
    span_deflection_limit,
    sphere_external_pressure_buckling,
    spiral_spring_rate,
    spiral_spring_stress,
    spring_index,
    spring_shear_stress,
    spring_stored_energy,
    spring_surge_frequency,
    springs_in_parallel,
    springs_in_series,
    spur_gear_contact_ratio,
    strength_scorecard,
    stress_intensity_factor,
    string_natural_frequency,
    thermal_buckling_temperature_rise,
    thermal_shock_stress,
    thick_wall_cylinder,
    thick_wall_sphere,
    thin_closed_tube_torsional_stress,
    thin_open_strip_torsion_constant,
    thin_open_strip_torsional_stress,
    thin_open_strip_twist_angle,
    thin_ring_buckling_pressure,
    thin_ring_diametral_deflection,
    thin_ring_max_moment,
    thin_wall_cylinder,
    thin_wall_sphere_stress,
    thin_wall_thickness_for_pressure,
    thread_engagement_for_load,
    thread_stripping_shear_area,
    thread_stripping_stress,
    torque_for_preload,
    torque_from_power,
    torsional_natural_frequency,
    transition_slenderness,
    transmissibility,
    trapezoidal_curved_beam_stress,
    tresca_equivalent_stress,
    tresca_principal,
    triangular_bar_torsional_stress,
    triangular_bar_twist_angle,
    triaxial_constrained_thermal_stress,
    tuned_mass_damper_optimal_damping,
    tuned_mass_damper_optimal_frequency_ratio,
    two_rotor_torsional_natural_frequency,
    vee_belt_effective_friction,
    von_mises_bending_torsion,
    von_mises_plane_stress,
    von_mises_principal,
    wahl_factor,
    worm_gear_efficiency,
    worm_gear_ratio,
    worm_is_self_locking,
    worm_lead_angle,
    worm_separating_force,
    worm_tangential_force,
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


def test_overhang_tip_load_matches_worked_example():
    # 100 N at the tip of a 250 mm overhang past a 500 mm back span (20x10
    # steel): |M|max = F*c = 25000 N*mm at the inner support -> sigma 75 MPa;
    # tip drop F*c^2*(L+c)/(3EI) = 4.6875 mm governs over the back-span
    # uplift 1.2028 mm (verified against a numeric integration of the ODE).
    kw = {
        "back_span": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    result = overhang_tip_load(force=_q("100 N"), overhang=_q("250 mm"), **kw)
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(75.0, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(4.6875, rel=1e-4)
    # A SHORT overhang is governed by the back-span uplift instead: at
    # c = 50 mm the tip drops only 0.1375 mm but the span bows up 0.2406 mm.
    short = overhang_tip_load(force=_q("100 N"), overhang=_q("50 mm"), **kw)
    assert short.max_deflection.to("mm").magnitude == pytest.approx(0.24056, rel=1e-4)


def test_overhang_uniform_load_matches_worked_example():
    # 1 N/mm over the same 250 mm overhang: |M|max = w*c^2/2 = 31250 N*mm ->
    # sigma 93.75 MPa; tip drop w*c^3*(4L+3c)/(24EI) = 5.3711 mm governs
    # (verified against a numeric integration of the beam ODE).
    result = overhang_uniform_load(
        distributed_load=_q("1 N/mm"),
        back_span=_q("500 mm"),
        overhang=_q("250 mm"),
        second_moment=rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        extreme_fibre=_q("5 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(93.75, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(5.37109, rel=1e-4)


def test_overhang_rejects_bad_inputs():
    kw = {
        "back_span": _q("500 mm"),
        "second_moment": rectangular_second_moment(_q("20 mm"), _q("10 mm")),
        "extreme_fibre": _q("5 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    with pytest.raises(ValueError, match="must be positive"):
        overhang_tip_load(force=_q("100 N"), overhang=_q("0 mm"), **kw)
    with pytest.raises(ValueError, match="distributed_load must be a"):
        overhang_uniform_load(distributed_load=_q("100 N"), overhang=_q("250 mm"), **kw)


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


def test_span_deflection_limit_is_span_over_ratio():
    # A 6 m floor beam at L/360 (plaster/live-load limit): 6000/360 = 16.67 mm.
    limit = span_deflection_limit(span=_q("6 m"), ratio=360)
    assert limit.to("mm").magnitude == pytest.approx(16.667, rel=1e-4)
    # A looser L/240 general-floor limit is exactly 1.5x as generous.
    loose = span_deflection_limit(span=_q("6 m"), ratio=240)
    assert loose.to("mm").magnitude == pytest.approx(1.5 * limit.to("mm").magnitude, rel=1e-9)


def test_span_deflection_limit_feeds_the_deflection_scorecard():
    from anvilate.scorecard import CheckStatus

    # A 6 m beam sagging 20 mm busts the L/360 (16.67 mm) limit but clears L/240.
    tight = span_deflection_limit(span=_q("6 m"), ratio=360)
    loose = span_deflection_limit(span=_q("6 m"), ratio=240)
    assert deflection_scorecard("floor", deflection=_q("20 mm"), limit=tight).status is (
        CheckStatus.FAIL
    )
    assert deflection_scorecard("floor", deflection=_q("20 mm"), limit=loose).status is (
        CheckStatus.PASS
    )


def test_span_deflection_limit_rejects_bad_inputs():
    with pytest.raises(ValueError, match="span must be positive"):
        span_deflection_limit(span=_q("0 m"), ratio=360)
    with pytest.raises(ValueError, match="ratio must be positive"):
        span_deflection_limit(span=_q("6 m"), ratio=0)


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


def test_euler_second_moment_for_load_inverts_the_buckling_load():
    # Size a 3 m pinned steel strut for 50 kN at a 2.0 buckling margin:
    #   I_min = n*P*(K*L)^2/(pi^2*E) = 2*50000*9/(pi^2*200e9) = 4.559e-7 m^4.
    i_min = euler_second_moment_for_load(
        design_load=_q("50 kN"),
        length=_q("3 m"),
        elastic_modulus=_q("200 GPa"),
        required_safety_factor=2.0,
    )
    assert i_min.to("mm**4").magnitude == pytest.approx(455_940.0, rel=1e-4)
    # A section with exactly this I buckles at n * the design load.
    p_cr = euler_buckling_load(elastic_modulus=_q("200 GPa"), second_moment=i_min, length=_q("3 m"))
    assert p_cr.to("N").magnitude == pytest.approx(2.0 * 50000, rel=1e-9)


def test_euler_second_moment_scales_with_margin_and_end_condition():
    kw = {
        "design_load": _q("50 kN"),
        "length": _q("3 m"),
        "elastic_modulus": _q("200 GPa"),
    }
    n2 = euler_second_moment_for_load(required_safety_factor=2.0, **kw)
    n3 = euler_second_moment_for_load(required_safety_factor=3.0, **kw)
    # I scales linearly with the required margin...
    assert n3.to("mm**4").magnitude == pytest.approx(1.5 * n2.to("mm**4").magnitude, rel=1e-9)
    # ...and with (K)^2: a fixed-free strut (K=2) needs 4x the I of pinned-pinned.
    fixed_free = euler_second_moment_for_load(
        required_safety_factor=2.0, effective_length_factor=2.0, **kw
    )
    assert fixed_free.to("mm**4").magnitude == pytest.approx(4 * n2.to("mm**4").magnitude, rel=1e-9)


def test_euler_second_moment_rejects_bad_inputs():
    with pytest.raises(ValueError, match="required_safety_factor must be positive"):
        euler_second_moment_for_load(
            design_load=_q("50 kN"),
            length=_q("3 m"),
            elastic_modulus=_q("200 GPa"),
            required_safety_factor=0.0,
        )
    with pytest.raises(ValueError, match="design_load must be a"):
        euler_second_moment_for_load(
            design_load=_q("50 mm"),
            length=_q("3 m"),
            elastic_modulus=_q("200 GPa"),
            required_safety_factor=2.0,
        )


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


# A 20x30 mm steel bar, 1.2 m pin-ended, load 5 mm off-centroid: A = 600 mm^2,
# I = 45000 mm^4, c = 15 mm, Euler load pi^2*200e9*4.5e-8/1.44 = 61.685 kN.
_SECANT_KW = {
    "eccentricity": _q("5 mm"),
    "area": _q("600 mm**2"),
    "second_moment": _q("45000 mm**4"),
    "extreme_fiber": _q("15 mm"),
    "length": _q("1.2 m"),
    "elastic_modulus": _q("200 GPa"),
}


def test_secant_column_matches_the_fd_verified_case():
    # At P = 0.3*P_euler = 18.506 kN the amplification is sec = 1.5334 and
    # sigma_max = 78.135 MPa — verified against an independent
    # finite-difference beam-column solve (rel 4e-9 in scratch).
    sigma = secant_column_max_stress(load=_q("18505.5 N"), **_SECANT_KW)
    assert sigma.to("MPa").magnitude == pytest.approx(78.135, rel=1e-4)


def test_secant_column_recovers_and_then_beats_the_naive_reading():
    # As P -> 0 the secant -> 1 and the formula collapses to the naive
    # P/A + P*e*c/I; at working loads the P-delta feedback makes it strictly
    # worse than naive — the direction that matters.
    tiny = 1.0  # N — P/P_euler = 1.6e-5, secant amplification 1.00002
    sigma = secant_column_max_stress(load=_q("1 N"), **_SECANT_KW)
    naive = tiny / 600e-6 + tiny * 0.005 * 0.015 / 4.5e-8
    assert sigma.to("Pa").magnitude == pytest.approx(naive, rel=1e-4)
    working = secant_column_max_stress(load=_q("37011 N"), **_SECANT_KW)  # 0.6 Pe
    naive_working = 37011 / 600e-6 + 37011 * 0.005 * 0.015 / 4.5e-8
    assert working.to("Pa").magnitude > naive_working


def test_secant_column_refuses_loads_at_or_beyond_euler():
    with pytest.raises(ValueError, match="beyond the Euler critical load"):
        secant_column_max_stress(load=_q("61.69 kN"), **_SECANT_KW)
    with pytest.raises(ValueError, match="must be positive"):
        secant_column_max_stress(load=_q("10 kN"), **{**_SECANT_KW, "eccentricity": _q("0 mm")})


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


def test_helical_spring_rate_matches_worked_example():
    # d = 4 mm, D = 32 mm (C = 8), Na = 10, G = 79.3 GPa:
    # k = G*d^4/(8*D^3*Na) = 79.3e9*2.56e-10/(8*3.2768e-5*10) = 7744 N/m.
    rate = helical_spring_rate(
        mean_coil_diameter=_q("32 mm"),
        wire_diameter=_q("4 mm"),
        active_coils=10,
        shear_modulus=_q("79.3 GPa"),
    )
    assert rate.to("N/mm").magnitude == pytest.approx(7.7441, rel=1e-4)


def test_spring_surge_is_exactly_pi_times_the_sdof_shortcut():
    # A spring between its seats is a fixed-fixed elastic rod: f1 =
    # (1/2)*sqrt(k/m) on its OWN mass — exactly pi x the SDOF
    # (1/2pi)*sqrt(k/m) reading of the same numbers. The 7.744 N/mm coil at
    # 100 g surges at 139.1 Hz.
    k, m = _q("7.7441 N/mm"), _q("100 g")
    surge = spring_surge_frequency(spring_rate=k, spring_mass=m)
    sdof = natural_frequency(stiffness=k, mass=m)
    assert surge.to("Hz").magnitude == pytest.approx(pi * sdof.to("Hz").magnitude, rel=1e-12)
    assert surge.to("Hz").magnitude == pytest.approx(139.14, rel=1e-3)


def test_spring_rate_and_surge_reject_bad_inputs():
    with pytest.raises(ValueError, match="active_coils must be positive"):
        helical_spring_rate(
            mean_coil_diameter=_q("32 mm"),
            wire_diameter=_q("4 mm"),
            active_coils=0,
            shear_modulus=_q("79.3 GPa"),
        )
    with pytest.raises(ValueError, match="shear_modulus must be a"):
        helical_spring_rate(
            mean_coil_diameter=_q("32 mm"),
            wire_diameter=_q("4 mm"),
            active_coils=10,
            shear_modulus=_q("79.3 N"),
        )
    with pytest.raises(ValueError, match="spring_rate must be a"):
        spring_surge_frequency(spring_rate=_q("7.7 N"), spring_mass=_q("100 g"))
    with pytest.raises(ValueError, match="must be positive"):
        spring_surge_frequency(spring_rate=_q("7.7 N/mm"), spring_mass=_q("0 g"))


def test_spring_stored_energy_worked_example():
    # k = 7.744 N/mm compressed 30 mm: U = 0.5*k*y^2 = 0.5*7.744*900 = 3484.8 N*mm
    #   = 3.4848 J, and equals 0.5*F*y for F = k*y = 232.3 N.
    u = spring_stored_energy(spring_rate=_q("7.744 N/mm"), deflection=_q("30 mm"))
    assert u.to("J").magnitude == pytest.approx(3.4848, rel=1e-4)
    force = 7.744 * 30  # N
    assert u.to("J").magnitude == pytest.approx(0.5 * force * 30 / 1000, rel=1e-9)


def test_spring_stored_energy_rejects_bad_inputs():
    with pytest.raises(ValueError, match="spring_rate must be a"):
        spring_stored_energy(spring_rate=_q("7.744 N"), deflection=_q("30 mm"))
    with pytest.raises(ValueError, match="deflection must be non-negative"):
        spring_stored_energy(spring_rate=_q("7.744 N/mm"), deflection=_q("-1 mm"))


def test_spring_buckling_critical_deflection_worked_example():
    # Steel E=207 GPa, G=79.3 GPa: C1'=0.81049, C2'=6.8947 (sqrt=2.6258).
    # D=25 mm, L0=200 mm, parallel plates a=0.5: lambda=0.5*200/25=4.0 > 2.6258,
    # so it buckles. C2'/lam^2=6.8947/16=0.43092; y_cr=200*0.81049*(1-sqrt(1-
    # 0.43092)) = 200*0.81049*0.24563 = 39.82 mm.
    result = helical_spring_buckling(
        free_length=_q("200 mm"),
        mean_coil_diameter=_q("25 mm"),
        elastic_modulus=_q("207 GPa"),
        shear_modulus=_q("79.3 GPa"),
    )
    assert result.effective_slenderness == pytest.approx(4.0)
    assert result.absolutely_stable is False
    assert result.critical_deflection.to("mm").magnitude == pytest.approx(39.82, rel=1e-3)
    # A working deflection past y_cr buckles; one short of it does not.
    assert result.will_buckle(_q("50 mm")) is True
    assert result.will_buckle(_q("30 mm")) is False


def test_spring_buckling_absolute_stability_below_threshold():
    # Same steel and diameter but a stubby L0=100 mm: lambda=0.5*100/25=2.0 <
    # sqrt(C2')=2.6258, so the coil cannot buckle at any deflection.
    result = helical_spring_buckling(
        free_length=_q("100 mm"),
        mean_coil_diameter=_q("25 mm"),
        elastic_modulus=_q("207 GPa"),
        shear_modulus=_q("79.3 GPa"),
    )
    assert result.effective_slenderness == pytest.approx(2.0)
    assert result.absolutely_stable is True
    assert result.critical_deflection is None
    assert result.will_buckle(_q("40 mm")) is False


def test_spring_buckling_hinged_ends_are_less_stable_than_plates():
    # The same slender coil on pivoted (hinged) seats, a=1.0, doubles lambda and
    # buckles far sooner than on parallel plates.
    common = {
        "free_length": _q("120 mm"),
        "mean_coil_diameter": _q("25 mm"),
        "elastic_modulus": _q("207 GPa"),
        "shear_modulus": _q("79.3 GPa"),
    }
    plates = helical_spring_buckling(end_condition_constant=SPRING_END_PARALLEL_PLATES, **common)
    hinged = helical_spring_buckling(end_condition_constant=SPRING_END_HINGED_HINGED, **common)
    assert plates.absolutely_stable is True
    assert hinged.absolutely_stable is False
    assert hinged.effective_slenderness == pytest.approx(2 * plates.effective_slenderness)


def test_spring_buckling_rejects_bad_inputs():
    good = {
        "free_length": _q("200 mm"),
        "mean_coil_diameter": _q("25 mm"),
        "elastic_modulus": _q("207 GPa"),
        "shear_modulus": _q("79.3 GPa"),
    }
    with pytest.raises(ValueError, match="end_condition_constant must be positive"):
        helical_spring_buckling(**{**good, "end_condition_constant": 0.0})
    with pytest.raises(ValueError, match="elastic_modulus must be a"):
        helical_spring_buckling(**{**good, "elastic_modulus": _q("207 N")})
    with pytest.raises(ValueError, match="need elastic_modulus > shear_modulus"):
        helical_spring_buckling(**{**good, "shear_modulus": _q("250 GPa")})


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


def test_key_length_for_torque_governed_by_bearing():
    # 200 N*m through a 40 mm shaft, 12x8 key, allowables 60/100 MPa: F = 10 kN;
    #   L_shear = F/(w*tau) = 10000/(12*60) = 13.889 mm;
    #   L_bearing = F/((h/2)*sigma) = 10000/(4*100) = 25.0 mm -> bearing governs.
    req = key_length_for_torque(
        torque=_q("200 N*m"),
        shaft_diameter=_q("40 mm"),
        key_width=_q("12 mm"),
        key_height=_q("8 mm"),
        allowable_shear=_q("60 MPa"),
        allowable_bearing=_q("100 MPa"),
    )
    assert req.shear_length.to("mm").magnitude == pytest.approx(13.889, rel=1e-4)
    assert req.bearing_length.to("mm").magnitude == pytest.approx(25.0, rel=1e-6)
    assert req.required_length.to("mm").magnitude == pytest.approx(25.0, rel=1e-6)
    assert req.governing_mode == "bearing"


def test_key_length_for_torque_inverts_the_stress_checks():
    # At the required length each governing stress lands exactly on its allowable.
    req = key_length_for_torque(
        torque=_q("200 N*m"),
        shaft_diameter=_q("40 mm"),
        key_width=_q("12 mm"),
        key_height=_q("8 mm"),
        allowable_shear=_q("60 MPa"),
        allowable_bearing=_q("100 MPa"),
    )
    sigma = key_bearing_stress(
        torque=_q("200 N*m"),
        shaft_diameter=_q("40 mm"),
        key_height=_q("8 mm"),
        key_length=req.required_length,
    )
    assert sigma.to("MPa").magnitude == pytest.approx(100.0, rel=1e-6)


def test_key_length_rejects_bad_allowable():
    with pytest.raises(ValueError, match="must be positive"):
        key_length_for_torque(
            torque=_q("200 N*m"),
            shaft_diameter=_q("40 mm"),
            key_width=_q("12 mm"),
            key_height=_q("8 mm"),
            allowable_shear=_q("0 MPa"),
            allowable_bearing=_q("100 MPa"),
        )


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


def test_fillet_weld_throat_stress_worked_example():
    # 20 kN on a 6 mm x 100 mm fillet: throat = 0.707*6*100 = 424.2 mm^2,
    #   tau = 20000/424.2 = 47.15 MPa.
    tau = fillet_weld_throat_stress(force=_q("20 kN"), leg_size=_q("6 mm"), length=_q("100 mm"))
    assert tau.to("MPa").magnitude == pytest.approx(47.15, rel=1e-3)


def test_fillet_weld_leg_for_load_inverts_the_throat_stress():
    # Size the leg for 20 kN over 100 mm within a 290 MPa allowable (0.6*E70):
    #   w = F/(0.707*L*tau) = 20000/(0.707*100*290) = 0.975 mm.
    w = fillet_weld_leg_for_load(
        force=_q("20 kN"), length=_q("100 mm"), allowable_shear=_q("290 MPa")
    )
    assert w.to("mm").magnitude == pytest.approx(0.9754, rel=1e-3)
    # A weld with exactly this leg is worked to the allowable on the throat.
    tau = fillet_weld_throat_stress(force=_q("20 kN"), leg_size=w, length=_q("100 mm"))
    assert tau.to("MPa").magnitude == pytest.approx(290.0, rel=1e-4)


def test_fillet_weld_leg_scales_with_margin():
    base = fillet_weld_leg_for_load(
        force=_q("20 kN"), length=_q("100 mm"), allowable_shear=_q("290 MPa")
    )
    with_sf = fillet_weld_leg_for_load(
        force=_q("20 kN"),
        length=_q("100 mm"),
        allowable_shear=_q("290 MPa"),
        required_safety_factor=2.0,
    )
    assert with_sf.to("mm").magnitude == pytest.approx(2.0 * base.to("mm").magnitude, rel=1e-9)


def test_fillet_weld_rejects_bad_inputs():
    with pytest.raises(ValueError, match="force must be a"):
        fillet_weld_throat_stress(force=_q("20 mm"), leg_size=_q("6 mm"), length=_q("100 mm"))
    with pytest.raises(ValueError, match="leg_size and length must be positive"):
        fillet_weld_throat_stress(force=_q("20 kN"), leg_size=_q("0 mm"), length=_q("100 mm"))
    with pytest.raises(ValueError, match="allowable_shear must be positive"):
        fillet_weld_leg_for_load(
            force=_q("20 kN"), length=_q("100 mm"), allowable_shear=_q("0 MPa")
        )


def test_bolt_diameter_for_shear_inverts_the_shear_check():
    # 20 kN in single shear within a 120 MPa allowable needs
    #   d = sqrt(4*F/(pi*tau)) = sqrt(80000/(pi*120)) = 14.57 mm.
    d = bolt_diameter_for_shear(shear_load=_q("20 kN"), allowable_shear=_q("120 MPa"))
    assert d.to("mm").magnitude == pytest.approx(14.567, rel=1e-4)
    # A bolt of exactly this diameter is worked to the allowable in shear.
    tau = bolt_shear_stress(force=_q("20 kN"), diameter=d)
    assert tau.to("MPa").magnitude == pytest.approx(120.0, rel=1e-6)


def test_bolt_diameter_for_shear_shrinks_in_double_shear():
    # Two shear planes halve the required area, so the diameter drops by sqrt(2).
    single = bolt_diameter_for_shear(shear_load=_q("20 kN"), allowable_shear=_q("120 MPa"))
    double = bolt_diameter_for_shear(
        shear_load=_q("20 kN"), allowable_shear=_q("120 MPa"), shear_planes=2
    )
    assert double.to("mm").magnitude == pytest.approx(single.to("mm").magnitude / 2**0.5, rel=1e-9)


def test_bolt_diameter_for_shear_rejects_bad_inputs():
    with pytest.raises(ValueError, match="shear_load must be a"):
        bolt_diameter_for_shear(shear_load=_q("20 mm"), allowable_shear=_q("120 MPa"))
    with pytest.raises(ValueError, match="shear_planes must be a positive integer"):
        bolt_diameter_for_shear(
            shear_load=_q("20 kN"), allowable_shear=_q("120 MPa"), shear_planes=0
        )
    with pytest.raises(ValueError, match="allowable_shear must be positive"):
        bolt_diameter_for_shear(shear_load=_q("20 kN"), allowable_shear=_q("0 MPa"))


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


def test_bolt_tensile_stress_area_recovers_the_iso_898_table():
    # A_t = (pi/4)(d - 0.9382*P)^2 lands on the ISO 898-1 table values.
    m10 = bolt_tensile_stress_area(nominal_diameter=_q("10 mm"), pitch=_q("1.5 mm"))
    assert m10.to("mm**2").magnitude == pytest.approx(58.0, abs=0.1)
    m8 = bolt_tensile_stress_area(nominal_diameter=_q("8 mm"), pitch=_q("1.25 mm"))
    assert m8.to("mm**2").magnitude == pytest.approx(36.6, abs=0.1)
    # It is smaller than the nominal shank area (pi/4*d^2 = 78.5 mm^2 for M10).
    assert m10.to("mm**2").magnitude < pi * 10**2 / 4


def test_bolt_axial_stress_uses_the_tensile_area_not_the_shank():
    # 20 kN of tension on an M10x1.5: sigma = F/A_t = 20000/57.99 = 344.9 MPa,
    # higher than the 254.6 MPa the nominal shank area would report.
    sigma = bolt_axial_stress(tension=_q("20 kN"), nominal_diameter=_q("10 mm"), pitch=_q("1.5 mm"))
    assert sigma.to("MPa").magnitude == pytest.approx(344.9, rel=1e-3)
    shank = 20000.0 / (pi * 10**2 / 4)
    assert sigma.to("MPa").magnitude > shank


def test_bolt_tensile_area_rejects_bad_inputs():
    with pytest.raises(ValueError, match="pitch must be positive"):
        bolt_tensile_stress_area(nominal_diameter=_q("10 mm"), pitch=_q("0 mm"))
    with pytest.raises(ValueError, match="must exceed 0.9382"):
        bolt_tensile_stress_area(nominal_diameter=_q("1 mm"), pitch=_q("2 mm"))
    with pytest.raises(ValueError, match="tension must be a"):
        bolt_axial_stress(tension=_q("20 mm"), nominal_diameter=_q("10 mm"), pitch=_q("1.5 mm"))


def test_bolt_proof_load_and_recommended_preload():
    # Proof load F_p = A_t*S_p: M12x1.75 (A_t = 84.27 mm^2), grade 8.8 (S_p = 600 MPa)
    # -> 50.56 kN.
    area = bolt_tensile_stress_area(nominal_diameter=_q("12 mm"), pitch=_q("1.75 mm"))
    fp = bolt_proof_load(tensile_stress_area=area, proof_strength=_q("600 MPa"))
    assert fp.to("N").magnitude == pytest.approx(area.to("mm**2").magnitude * 600, rel=1e-12)
    assert fp.to("kN").magnitude == pytest.approx(50.56, rel=1e-3)
    # Reused connections are preloaded to 0.75*F_p, permanent ones to 0.90*F_p.
    reused = recommended_bolt_preload(proof_load=fp)
    permanent = recommended_bolt_preload(proof_load=fp, permanent=True)
    assert reused.to("N").magnitude == pytest.approx(0.75 * fp.to("N").magnitude, rel=1e-12)
    assert permanent.to("N").magnitude == pytest.approx(0.90 * fp.to("N").magnitude, rel=1e-12)
    assert permanent.to("N").magnitude > reused.to("N").magnitude
    with pytest.raises(ValueError, match="proof_strength must be positive"):
        bolt_proof_load(tensile_stress_area=area, proof_strength=_q("0 MPa"))
    with pytest.raises(ValueError, match="tensile_stress_area must be a"):
        bolt_proof_load(tensile_stress_area=_q("84 mm"), proof_strength=_q("600 MPa"))


def test_flywheel_inertia_and_energy_round_trip():
    # A press flywheel smoothing a 5000 J energy swing at 200 rpm mean speed to a
    # coefficient of fluctuation of 0.05 needs I = dE/(omega^2*Cs) = 227.97 kg*m^2.
    inertia = flywheel_inertia_for_fluctuation(
        energy_fluctuation=_q("5000 J"),
        mean_speed=_q("200 rpm"),
        coefficient_of_fluctuation=0.05,
    )
    assert inertia.to("kg*m**2").magnitude == pytest.approx(227.973, rel=1e-4)
    # The forward energy recovers the 5000 J at that inertia.
    energy = flywheel_energy_fluctuation(
        inertia=inertia, mean_speed=_q("200 rpm"), coefficient_of_fluctuation=0.05
    )
    assert energy.to("J").magnitude == pytest.approx(5000.0, rel=1e-9)
    # The omega^2 lever: doubling the mean speed quarters the required inertia.
    faster = flywheel_inertia_for_fluctuation(
        energy_fluctuation=_q("5000 J"),
        mean_speed=_q("400 rpm"),
        coefficient_of_fluctuation=0.05,
    )
    assert faster.to("kg*m**2").magnitude == pytest.approx(
        inertia.to("kg*m**2").magnitude / 4, rel=1e-9
    )


def test_coefficient_of_fluctuation_from_speed_swing():
    # 205/195 rpm about a 200 mean: Cs = (205-195)/200 = 0.05.
    cs = coefficient_of_fluctuation(max_speed=_q("205 rpm"), min_speed=_q("195 rpm"))
    assert cs == pytest.approx(0.05, rel=1e-9)
    with pytest.raises(ValueError, match="max_speed .* must exceed min_speed"):
        coefficient_of_fluctuation(max_speed=_q("195 rpm"), min_speed=_q("205 rpm"))
    with pytest.raises(ValueError, match="coefficient_of_fluctuation must be positive"):
        flywheel_energy_fluctuation(
            inertia=_q("10 kg*m**2"), mean_speed=_q("200 rpm"), coefficient_of_fluctuation=0.0
        )
    with pytest.raises(ValueError, match="energy_fluctuation must be a"):
        flywheel_inertia_for_fluctuation(
            energy_fluctuation=_q("5000 N"),
            mean_speed=_q("200 rpm"),
            coefficient_of_fluctuation=0.05,
        )


def test_impact_factor_energy_method():
    # A load applied suddenly from rest (h=0) still doubles the static values.
    sudden = impact_factor(drop_height=_q("0 mm"), static_deflection=_q("5 mm"))
    assert sudden == pytest.approx(2.0, rel=1e-12)
    # A 100 mm drop onto a member that deflects 2 mm statically: K = 1+sqrt(1+2*100/2)
    # = 1 + sqrt(101) = 11.05.
    dropped = impact_factor(drop_height=_q("100 mm"), static_deflection=_q("2 mm"))
    assert dropped == pytest.approx(1 + (101) ** 0.5, rel=1e-9)
    # A stiffer target (smaller static deflection) amplifies a drop more.
    stiffer = impact_factor(drop_height=_q("100 mm"), static_deflection=_q("1 mm"))
    assert stiffer > dropped


def test_impact_stress_scales_the_static_stress_by_the_factor():
    # 20 MPa static, applied suddenly -> 40 MPa (K=2).
    sudden = impact_stress(
        static_stress=_q("20 MPa"), drop_height=_q("0 mm"), static_deflection=_q("5 mm")
    )
    assert sudden.to("MPa").magnitude == pytest.approx(40.0, rel=1e-12)
    # It equals the static stress times the impact factor for the same drop.
    k = impact_factor(drop_height=_q("100 mm"), static_deflection=_q("2 mm"))
    dropped = impact_stress(
        static_stress=_q("20 MPa"), drop_height=_q("100 mm"), static_deflection=_q("2 mm")
    )
    assert dropped.to("MPa").magnitude == pytest.approx(20.0 * k, rel=1e-12)


def test_impact_rejects_bad_inputs():
    with pytest.raises(ValueError, match="drop_height must be non-negative"):
        impact_factor(drop_height=_q("-5 mm"), static_deflection=_q("5 mm"))
    with pytest.raises(ValueError, match="static_deflection must be positive"):
        impact_factor(drop_height=_q("5 mm"), static_deflection=_q("0 mm"))
    with pytest.raises(ValueError, match="static_stress must be a"):
        impact_stress(
            static_stress=_q("20 mm"), drop_height=_q("0 mm"), static_deflection=_q("5 mm")
        )


def test_power_screw_torques_match_the_worked_example():
    # Square-thread jack screw: d_m=25 mm, lead=5 mm, F=6.4 kN, mu=0.08.
    kw = {"mean_diameter": _q("25 mm"), "lead": _q("5 mm")}
    assert lead_angle(**kw).to("degree").magnitude == pytest.approx(3.6426, rel=1e-4)
    raise_t = power_screw_raise_torque(load=_q("6.4 kN"), friction_coefficient=0.08, **kw)
    assert raise_t.to("N*m").magnitude == pytest.approx(11.5518, rel=1e-4)
    lower_t = power_screw_lower_torque(load=_q("6.4 kN"), friction_coefficient=0.08, **kw)
    assert lower_t.to("N*m").magnitude == pytest.approx(1.3004, rel=1e-4)
    # Efficiency matches the closed form AND the raise-torque energy balance.
    eff = power_screw_efficiency(friction_coefficient=0.08, **kw)
    assert eff == pytest.approx(0.44088, rel=1e-4)
    energy_eff = 6400 * 0.005 / (2 * pi * raise_t.to("N*m").magnitude)
    assert eff == pytest.approx(energy_eff, rel=1e-6)


def test_power_screw_self_locking_boundary():
    kw = {"mean_diameter": _q("25 mm"), "lead": _q("5 mm"), "load": _q("6.4 kN")}
    geom = {"mean_diameter": _q("25 mm"), "lead": _q("5 mm")}
    # mu=0.08 > tan(lambda)=0.0637: self-locking, lowering torque is positive.
    assert power_screw_is_self_locking(friction_coefficient=0.08, **geom)
    assert power_screw_lower_torque(friction_coefficient=0.08, **kw).to("N*m").magnitude > 0
    # A slick thread (mu=0.03 < tan lambda) backdrives: lowering torque goes negative.
    assert not power_screw_is_self_locking(friction_coefficient=0.03, **geom)
    assert power_screw_lower_torque(friction_coefficient=0.03, **kw).to("N*m").magnitude < 0
    # Self-locking screws pay for it with efficiency below 50%.
    assert power_screw_efficiency(friction_coefficient=0.08, **geom) < 0.5


def test_power_screw_rejects_bad_inputs():
    kw = {"mean_diameter": _q("25 mm"), "lead": _q("5 mm")}
    with pytest.raises(ValueError, match="lead must be positive"):
        lead_angle(mean_diameter=_q("25 mm"), lead=_q("0 mm"))
    with pytest.raises(ValueError, match="friction_coefficient must be non-negative"):
        power_screw_raise_torque(load=_q("6.4 kN"), friction_coefficient=-0.1, **kw)
    with pytest.raises(ValueError, match="load must be a"):
        power_screw_raise_torque(load=_q("6.4 mm"), friction_coefficient=0.08, **kw)


def test_power_screw_collar_torque_adds_to_the_thread_torque():
    # T_c = mu_c * F * r_c: 10 kN axial, 25 mm collar radius, mu_c = 0.15 -> 37.5 N*m.
    tc = power_screw_collar_torque(
        load=_q("10 kN"), collar_mean_radius=_q("25 mm"), collar_friction_coefficient=0.15
    )
    assert tc.to("N*m").magnitude == pytest.approx(0.15 * 10000 * 0.025, rel=1e-12)
    assert tc.to("N*m").magnitude == pytest.approx(37.5, rel=1e-9)
    # A frictionless (e.g. rolling) thrust bearing adds no collar torque.
    zero = power_screw_collar_torque(
        load=_q("10 kN"), collar_mean_radius=_q("25 mm"), collar_friction_coefficient=0.0
    )
    assert zero.to("N*m").magnitude == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(ValueError, match="collar_mean_radius must be positive"):
        power_screw_collar_torque(
            load=_q("10 kN"), collar_mean_radius=_q("0 mm"), collar_friction_coefficient=0.15
        )
    with pytest.raises(ValueError, match="collar_friction_coefficient must be non-negative"):
        power_screw_collar_torque(
            load=_q("10 kN"), collar_mean_radius=_q("25 mm"), collar_friction_coefficient=-0.1
        )


def test_flange_coupling_torque_and_bolt_force_invert():
    # 6 bolts each carrying 5 kN at an 80 mm bolt circle: T = n*F*R = 2400 N*m.
    t = flange_coupling_torque(
        bolt_shear_force=_q("5 kN"), bolt_circle_radius=_q("80 mm"), num_bolts=6
    )
    assert t.to("N*m").magnitude == pytest.approx(2400.0, rel=1e-9)
    # The inverse recovers the 5 kN per-bolt shear from that torque.
    f = flange_coupling_bolt_force(torque=t, bolt_circle_radius=_q("80 mm"), num_bolts=6)
    assert f.to("kN").magnitude == pytest.approx(5.0, rel=1e-9)
    # More bolts share the same torque at a lower per-bolt force.
    f12 = flange_coupling_bolt_force(torque=t, bolt_circle_radius=_q("80 mm"), num_bolts=12)
    assert f12.to("kN").magnitude == pytest.approx(2.5, rel=1e-9)
    with pytest.raises(ValueError, match="num_bolts must be a positive integer"):
        flange_coupling_torque(
            bolt_shear_force=_q("5 kN"), bolt_circle_radius=_q("80 mm"), num_bolts=0
        )


def test_leaf_spring_stress_rate_and_deflection_are_consistent():
    kw = {
        "length": _q("400 mm"),
        "num_leaves": 4,
        "leaf_width": _q("50 mm"),
        "leaf_thickness": _q("10 mm"),
    }
    # sigma = 6*F*L/(n*b*t^2): 2 kN, 400 mm, 4x50x10 -> 240 MPa.
    sigma = leaf_spring_stress(load=_q("2 kN"), **kw)
    assert sigma.to("MPa").magnitude == pytest.approx(240.0, rel=1e-9)
    # rate = E*n*b*t^3/(6*L^3), and F/rate must equal the 6*F*L^3/(E*n*b*t^3) drop.
    rate = leaf_spring_rate(elastic_modulus=_q("207 GPa"), **kw)
    assert rate.to("N/mm").magnitude == pytest.approx(107.8125, rel=1e-6)
    deflection = 2000.0 / rate.to("N/mm").magnitude
    expected = 6 * 2000 * 400**3 / (207000 * 4 * 50 * 10**3)
    assert deflection == pytest.approx(expected, rel=1e-9)
    # A thicker leaf stiffens it steeply (t^3 lever): double t -> 8x the rate.
    thick_kw = {**kw, "leaf_thickness": _q("20 mm")}
    thicker = leaf_spring_rate(elastic_modulus=_q("207 GPa"), **thick_kw)
    assert thicker.to("N/mm").magnitude == pytest.approx(8 * rate.to("N/mm").magnitude, rel=1e-9)


def test_leaf_spring_rejects_bad_inputs():
    with pytest.raises(ValueError, match="num_leaves must be a positive integer"):
        leaf_spring_stress(
            load=_q("2 kN"),
            length=_q("400 mm"),
            num_leaves=0,
            leaf_width=_q("50 mm"),
            leaf_thickness=_q("10 mm"),
        )
    with pytest.raises(ValueError, match="load must be a"):
        leaf_spring_stress(
            load=_q("2 mm"),
            length=_q("400 mm"),
            num_leaves=4,
            leaf_width=_q("50 mm"),
            leaf_thickness=_q("10 mm"),
        )


def test_springs_in_series_and_parallel():
    rates = [_q("10 N/mm"), _q("20 N/mm")]
    # Series is softer than the softest spring: 1/k = 1/10 + 1/20 -> 6.667 N/mm.
    series = springs_in_series(rates)
    assert series.to("N/mm").magnitude == pytest.approx(20.0 / 3.0, rel=1e-9)
    assert series.to("N/mm").magnitude < 10.0
    # Parallel is stiffer than the stiffest: k = 10 + 20 = 30 N/mm.
    parallel = springs_in_parallel(rates)
    assert parallel.to("N/mm").magnitude == pytest.approx(30.0, rel=1e-12)
    assert parallel.to("N/mm").magnitude > 20.0
    # A single spring returns its own rate either way.
    assert springs_in_series([_q("15 N/mm")]).to("N/mm").magnitude == pytest.approx(15.0, rel=1e-12)


def test_spring_combination_rejects_bad_inputs():
    with pytest.raises(ValueError, match="at least one spring rate"):
        springs_in_parallel([])
    with pytest.raises(ValueError, match="each spring rate must be positive"):
        springs_in_series([_q("10 N/mm"), _q("0 N/mm")])
    with pytest.raises(ValueError, match=r"each spring rate must be a \[force\]/\[length\]"):
        springs_in_parallel([_q("10 N")])


def test_plate_buckling_stress_scales_with_thickness_squared():
    # k=4, E=200 GPa, t=5 mm, b=300 mm, nu=0.3:
    #   sigma_cr = 4*pi^2*E/(12*(1-nu^2))*(t/b)^2 = 200.85 MPa.
    sigma = plate_buckling_stress(
        buckling_coefficient=4.0,
        elastic_modulus=_q("200 GPa"),
        thickness=_q("5 mm"),
        width=_q("300 mm"),
    )
    assert sigma.to("MPa").magnitude == pytest.approx(200.847, rel=1e-4)
    # The (t/b)^2 lever: doubling the thickness quadruples the critical stress.
    thicker = plate_buckling_stress(
        buckling_coefficient=4.0,
        elastic_modulus=_q("200 GPa"),
        thickness=_q("10 mm"),
        width=_q("300 mm"),
    )
    assert thicker.to("MPa").magnitude == pytest.approx(4 * sigma.to("MPa").magnitude, rel=1e-9)


def test_plate_buckling_rejects_bad_inputs():
    with pytest.raises(ValueError, match="buckling_coefficient must be positive"):
        plate_buckling_stress(
            buckling_coefficient=0.0,
            elastic_modulus=_q("200 GPa"),
            thickness=_q("5 mm"),
            width=_q("300 mm"),
        )
    with pytest.raises(ValueError, match="poisson_ratio must lie in"):
        plate_buckling_stress(
            buckling_coefficient=4.0,
            elastic_modulus=_q("200 GPa"),
            thickness=_q("5 mm"),
            width=_q("300 mm"),
            poisson_ratio=0.7,
        )
    with pytest.raises(ValueError, match="elastic_modulus must be a"):
        plate_buckling_stress(
            buckling_coefficient=4.0,
            elastic_modulus=_q("200 mm"),
            thickness=_q("5 mm"),
            width=_q("300 mm"),
        )


def test_journal_bearing_unit_load_and_sommerfeld_number():
    # P = W/(D*L): 5 kN over 50x50 mm projected area -> 2 MPa.
    p = journal_bearing_unit_load(
        radial_load=_q("5 kN"), journal_diameter=_q("50 mm"), bearing_length=_q("50 mm")
    )
    assert p.to("MPa").magnitude == pytest.approx(2.0, rel=1e-9)
    # S = (r/c)^2 * (mu*N/P) with r/c=500, mu=0.05, N=30 rev/s, P=2e6 -> 0.1875.
    s = sommerfeld_number(
        journal_radius=_q("25 mm"),
        radial_clearance=_q("0.05 mm"),
        viscosity=_q("0.05 Pa*s"),
        speed=_q("1800 rpm"),
        unit_load=p,
    )
    assert s == pytest.approx(0.1875, rel=1e-4)
    # A more heavily loaded bearing (higher P) has a smaller Sommerfeld number.
    heavier = sommerfeld_number(
        journal_radius=_q("25 mm"),
        radial_clearance=_q("0.05 mm"),
        viscosity=_q("0.05 Pa*s"),
        speed=_q("1800 rpm"),
        unit_load=_q("4 MPa"),
    )
    assert heavier == pytest.approx(s / 2, rel=1e-9)
    with pytest.raises(ValueError, match="unit_load must be a"):
        sommerfeld_number(
            journal_radius=_q("25 mm"),
            radial_clearance=_q("0.05 mm"),
            viscosity=_q("0.05 Pa*s"),
            speed=_q("1800 rpm"),
            unit_load=_q("4 kN"),
        )


def test_journal_bearing_minimum_film_thickness():
    # h0 = c*(1-eps): c = 40 um, eps = 0.6 -> 16 um of oil film.
    h0 = journal_bearing_minimum_film_thickness(
        radial_clearance=_q("40 um"), eccentricity_ratio=0.6
    )
    assert h0.to("um").magnitude == pytest.approx(40 * (1 - 0.6), rel=1e-12)
    assert h0.to("um").magnitude == pytest.approx(16.0, rel=1e-9)
    # A concentric journal (eps = 0) has the full clearance as film thickness.
    assert journal_bearing_minimum_film_thickness(
        radial_clearance=_q("40 um"), eccentricity_ratio=0.0
    ).to("um").magnitude == pytest.approx(40.0, rel=1e-12)
    # A more heavily loaded (more eccentric) bearing runs a thinner film.
    thinner = journal_bearing_minimum_film_thickness(
        radial_clearance=_q("40 um"), eccentricity_ratio=0.9
    )
    assert thinner.to("um").magnitude < h0.to("um").magnitude
    with pytest.raises(ValueError, match=r"eccentricity_ratio must lie in \[0, 1\)"):
        journal_bearing_minimum_film_thickness(radial_clearance=_q("40 um"), eccentricity_ratio=1.0)


def test_petroff_journal_bearing_friction():
    from math import pi

    kw = {
        "viscosity": _q("0.05 Pa*s"),
        "speed": _q("1800 rpm"),
        "journal_radius": _q("25 mm"),
        "bearing_length": _q("50 mm"),
        "radial_clearance": _q("0.05 mm"),
    }
    # T = 4*pi^2*mu*N*L*r^3/c with N=30 rev/s -> 0.9253 N*m.
    torque = petroff_friction_torque(**kw)
    assert torque.to("N*m").magnitude == pytest.approx(0.92534, rel=1e-4)
    # Power = T*omega = T*2*pi*30 -> 174.4 W.
    power = petroff_friction_power(**kw)
    assert power.to("W").magnitude == pytest.approx(
        torque.to("N*m").magnitude * 2 * pi * 30, rel=1e-6
    )
    # Tighter clearance (half c) doubles the friction torque.
    tight = petroff_friction_torque(**{**kw, "radial_clearance": _q("0.025 mm")})
    assert tight.to("N*m").magnitude == pytest.approx(2 * torque.to("N*m").magnitude, rel=1e-9)


def test_petroff_rejects_bad_inputs():
    kw = {
        "speed": _q("1800 rpm"),
        "journal_radius": _q("25 mm"),
        "bearing_length": _q("50 mm"),
        "radial_clearance": _q("0.05 mm"),
    }
    with pytest.raises(ValueError, match="viscosity must be a"):
        petroff_friction_torque(viscosity=_q("0.05 Pa"), **kw)
    with pytest.raises(ValueError, match="radial_clearance must be positive"):
        petroff_friction_torque(
            viscosity=_q("0.05 Pa*s"),
            speed=_q("1800 rpm"),
            journal_radius=_q("25 mm"),
            bearing_length=_q("50 mm"),
            radial_clearance=_q("0 mm"),
        )


def test_gear_contact_stress_matches_the_hertz_line_contact():
    from math import cos, radians, sin

    from anvilate.analysis import hertz_cylinder_contact

    kw = {
        "tangential_load": _q("2 kN"),
        "pinion_pitch_diameter": _q("100 mm"),
        "gear_pitch_diameter": _q("200 mm"),
        "pressure_angle": 20,
        "face_width": _q("40 mm"),
        "modulus_pinion": _q("200 GPa"),
        "modulus_gear": _q("200 GPa"),
    }
    sigma = gear_contact_stress(**kw)
    # It delegates to the line-contact solver with the pitch-point geometry:
    # equivalent cylinder diameters d*sin(phi), normal load W_t/cos(phi).
    phi = radians(20)
    ref = hertz_cylinder_contact(
        force=_q(f"{2000 / cos(phi)} N"),
        length=_q("40 mm"),
        diameter1=_q(f"{100 * sin(phi)} mm"),
        modulus1=_q("200 GPa"),
        poisson1=0.3,
        modulus2=_q("200 GPa"),
        poisson2=0.3,
        diameter2=_q(f"{200 * sin(phi)} mm"),
    )
    assert sigma.to("MPa").magnitude == pytest.approx(
        ref.max_contact_pressure.to("MPa").magnitude, rel=1e-9
    )
    assert sigma.to("MPa").magnitude == pytest.approx(404.05, rel=1e-3)
    with pytest.raises(ValueError, match=r"pressure_angle \(degrees\) must lie in"):
        gear_contact_stress(**{**kw, "pressure_angle": 0})


def test_gear_pitch_line_velocity_and_barth_factor():
    # V = pi*d*n: 100 mm pitch circle at 1500 rpm -> 7.854 m/s.
    v = pitch_line_velocity(pitch_diameter=_q("100 mm"), rotational_speed=_q("1500 rpm"))
    assert v.to("m/s").magnitude == pytest.approx(7.85398, rel=1e-4)
    # Barth Kv for cut teeth = (6.1 + V)/6.1 = 2.288 -> more than doubles the load.
    kv_cut = barth_velocity_factor(pitch_line_velocity=v, quality="cut")
    assert kv_cut == pytest.approx((6.1 + 7.85398) / 6.1, rel=1e-4)
    # Finer teeth amplify less: precision < hobbed < cut.
    kv_hobbed = barth_velocity_factor(pitch_line_velocity=v, quality="hobbed")
    kv_precision = barth_velocity_factor(pitch_line_velocity=v, quality="precision")
    assert kv_precision < kv_hobbed < kv_cut
    with pytest.raises(ValueError, match="quality must be one of"):
        barth_velocity_factor(pitch_line_velocity=v, quality="forged")
    with pytest.raises(ValueError, match="rotational_speed must be a"):
        pitch_line_velocity(pitch_diameter=_q("100 mm"), rotational_speed=_q("1500 N"))


def test_gear_force_resolution_from_pressure_angle():
    from math import cos, radians, tan

    wt = _q("2000 N")
    # Radial (separating) load W_r = W_t*tan(phi) at 20 deg -> 727.94 N.
    wr = gear_radial_load(tangential_load=wt, pressure_angle=20)
    assert wr.to("N").magnitude == pytest.approx(2000 * tan(radians(20)), rel=1e-9)
    # Normal tooth load W_n = W_t/cos(phi) always exceeds W_t.
    wn = gear_normal_load(tangential_load=wt, pressure_angle=20)
    assert wn.to("N").magnitude == pytest.approx(2000 / cos(radians(20)), rel=1e-9)
    assert wn.to("N").magnitude > 2000.0
    # A larger pressure angle raises the separating load.
    assert (
        gear_radial_load(tangential_load=wt, pressure_angle=25).to("N").magnitude
        > wr.to("N").magnitude
    )
    with pytest.raises(ValueError, match=r"pressure_angle \(degrees\) must lie in"):
        gear_radial_load(tangential_load=wt, pressure_angle=0)


def test_gear_lewis_bending_and_tangential_load():
    # W_t = 2*T/d: 100 N*m on a 100 mm pitch circle -> 2000 N.
    wt = gear_tangential_load(torque=_q("100 N*m"), pitch_diameter=_q("100 mm"))
    assert wt.to("N").magnitude == pytest.approx(2000.0, rel=1e-9)
    # Lewis sigma = W_t/(F*m*Y): 3 kN, m=5 mm, F=50 mm, Y=0.34 -> 35.29 MPa.
    sigma = lewis_bending_stress(
        tangential_load=_q("3 kN"),
        module=_q("5 mm"),
        face_width=_q("50 mm"),
        form_factor=0.34,
    )
    assert sigma.to("MPa").magnitude == pytest.approx(35.294, rel=1e-4)
    # A wider face or a coarser (larger-module) tooth lowers the stress.
    wider = lewis_bending_stress(
        tangential_load=_q("3 kN"),
        module=_q("5 mm"),
        face_width=_q("100 mm"),
        form_factor=0.34,
    )
    assert wider.to("MPa").magnitude == pytest.approx(sigma.to("MPa").magnitude / 2, rel=1e-9)


def test_gear_lewis_rejects_bad_inputs():
    with pytest.raises(ValueError, match="pitch_diameter must be positive"):
        gear_tangential_load(torque=_q("100 N*m"), pitch_diameter=_q("0 mm"))
    with pytest.raises(ValueError, match=r"form_factor \(Lewis Y\) must be positive"):
        lewis_bending_stress(
            tangential_load=_q("3 kN"), module=_q("5 mm"), face_width=_q("50 mm"), form_factor=0.0
        )
    with pytest.raises(ValueError, match="tangential_load must be a"):
        lewis_bending_stress(
            tangential_load=_q("3 mm"), module=_q("5 mm"), face_width=_q("50 mm"), form_factor=0.34
        )


def test_riveted_joint_efficiency_takes_the_weakest_mode():
    # p=50, d=20, t=10, sigma_t=80, tau=60, sigma_c=120 (MPa), 1 rivet/pitch:
    #   tearing=(50-20)*10*80=24 kN, shearing=(pi/4)*400*60=18.85 kN,
    #   crushing=20*10*120=24 kN, solid=50*10*80=40 kN. Shearing governs.
    r = riveted_joint_efficiency(
        pitch=_q("50 mm"),
        rivet_diameter=_q("20 mm"),
        plate_thickness=_q("10 mm"),
        allowable_tension=_q("80 MPa"),
        allowable_shear=_q("60 MPa"),
        allowable_bearing=_q("120 MPa"),
    )
    assert r.tearing_strength.to("kN").magnitude == pytest.approx(24.0, rel=1e-9)
    assert r.shearing_strength.to("kN").magnitude == pytest.approx(
        pi / 4 * 400 * 60 / 1000, rel=1e-9
    )
    assert r.governing_mode == "shearing"
    assert r.joint_strength.to("kN").magnitude == pytest.approx(
        r.shearing_strength.to("kN").magnitude, rel=1e-12
    )
    assert r.efficiency == pytest.approx(r.shearing_strength.to("kN").magnitude / 40.0, rel=1e-9)


def test_riveted_joint_rejects_bad_inputs():
    good = {
        "rivet_diameter": _q("20 mm"),
        "plate_thickness": _q("10 mm"),
        "allowable_tension": _q("80 MPa"),
        "allowable_shear": _q("60 MPa"),
        "allowable_bearing": _q("120 MPa"),
    }
    with pytest.raises(ValueError, match="pitch .* must exceed rivet_diameter"):
        riveted_joint_efficiency(pitch=_q("15 mm"), **good)
    with pytest.raises(ValueError, match="rivets_per_pitch must be a positive integer"):
        riveted_joint_efficiency(pitch=_q("50 mm"), rivets_per_pitch=0, **good)


def test_cone_clutch_torque_wedges_up_the_disc_torque():
    from math import radians, sin

    kw = {
        "actuating_force": _q("5 kN"),
        "outer_radius": _q("100 mm"),
        "inner_radius": _q("50 mm"),
        "friction_coefficient": 0.3,
    }
    # Cone half-angle 12 deg: T = mu*F*r_mean/sin(alpha) = 112.5/sin(12) = 541.1 N*m.
    cone = cone_clutch_torque(cone_half_angle=12, **kw)
    assert cone.to("N*m").magnitude == pytest.approx(112.5 / sin(radians(12)), rel=1e-4)
    # It is the single-surface disc torque times the 1/sin(alpha) wedge factor.
    disc = disc_clutch_torque(**kw)  # N=1 by default
    assert cone.to("N*m").magnitude == pytest.approx(
        disc.to("N*m").magnitude / sin(radians(12)), rel=1e-9
    )
    # A shallower cone (smaller angle) multiplies the torque more.
    shallower = cone_clutch_torque(cone_half_angle=8, **kw)
    assert shallower.to("N*m").magnitude > cone.to("N*m").magnitude
    with pytest.raises(ValueError, match=r"cone_half_angle \(degrees\) must lie in"):
        cone_clutch_torque(cone_half_angle=0, **kw)


def test_disc_clutch_torque_both_theories():
    kw = {
        "outer_radius": _q("100 mm"),
        "inner_radius": _q("50 mm"),
        "friction_coefficient": 0.3,
        "surfaces": 2,
    }
    # Uniform wear: T = mu*F*N*(ro+ri)/2 = 0.3*5000*2*0.075 = 225 N*m.
    wear = disc_clutch_torque(actuating_force=_q("5 kN"), **kw)
    assert wear.to("N*m").magnitude == pytest.approx(225.0, rel=1e-9)
    # Uniform pressure gives a slightly higher torque (233.3 N*m) -> wear is the
    # conservative design basis.
    pressure = disc_clutch_torque(actuating_force=_q("5 kN"), theory=UNIFORM_PRESSURE, **kw)
    assert pressure.to("N*m").magnitude == pytest.approx(233.333, rel=1e-4)
    assert wear.to("N*m").magnitude < pressure.to("N*m").magnitude
    # The force inverse recovers the 5 kN clamp for the wear torque.
    force = disc_clutch_force_for_torque(torque=wear, **kw)
    assert force.to("kN").magnitude == pytest.approx(5.0, rel=1e-9)


def test_disc_clutch_rejects_bad_inputs():
    kw = {"outer_radius": _q("100 mm"), "inner_radius": _q("50 mm"), "friction_coefficient": 0.3}
    with pytest.raises(ValueError, match="outer_radius .* must exceed inner_radius"):
        disc_clutch_torque(
            actuating_force=_q("5 kN"),
            outer_radius=_q("50 mm"),
            inner_radius=_q("100 mm"),
            friction_coefficient=0.3,
        )
    with pytest.raises(ValueError, match="surfaces must be a positive integer"):
        disc_clutch_torque(actuating_force=_q("5 kN"), surfaces=0, **kw)
    with pytest.raises(ValueError, match="theory must be"):
        disc_clutch_torque(actuating_force=_q("5 kN"), theory="linear", **kw)
    with pytest.raises(ValueError, match="actuating_force must be a"):
        disc_clutch_torque(actuating_force=_q("5 mm"), **kw)


def test_belt_drive_geometry_and_capstan_composition():
    from math import asin, pi

    kw = {
        "large_pulley_diameter": _q("200 mm"),
        "small_pulley_diameter": _q("100 mm"),
        "center_distance": _q("500 mm"),
    }
    # L = 2C + pi*(D+d)/2 + (D-d)^2/(4C) = 1476.24 mm.
    length = belt_length(**kw)
    assert length.to("mm").magnitude == pytest.approx(1476.239, rel=1e-4)
    # Small-pulley wrap beta = pi - 2*asin((D-d)/(2C)) < pi (it grips less).
    beta = belt_wrap_angle(**kw)
    assert beta == pytest.approx(pi - 2 * asin(100 / 1000), rel=1e-9)
    assert beta < pi
    # The wrap angle feeds the capstan ratio for the drive's real slip capacity.
    ratio = capstan_tension_ratio(friction_coefficient=0.3, wrap_angle=beta)
    assert ratio == pytest.approx(2.4166, rel=1e-3)
    with pytest.raises(ValueError, match="center_distance .* is too small"):
        belt_length(
            large_pulley_diameter=_q("400 mm"),
            small_pulley_diameter=_q("100 mm"),
            center_distance=_q("100 mm"),
        )


def test_crossed_belt_is_longer_and_wraps_more_than_the_open_belt():
    from math import asin, pi

    kw = {
        "large_pulley_diameter": _q("300 mm"),
        "small_pulley_diameter": _q("150 mm"),
        "center_distance": _q("600 mm"),
    }
    # Crossed belt uses the SUM of the radii: L = 2C + pi*(D+d)/2 + (D+d)^2/(4C).
    crossed_len = crossed_belt_length(**kw)
    assert crossed_len.to("mm").magnitude == pytest.approx(
        2 * 600 + pi * 450 / 2 + 450**2 / (4 * 600), rel=1e-12
    )
    # It is always longer than the open belt on the same pulleys.
    assert crossed_len.to("mm").magnitude > belt_length(**kw).to("mm").magnitude
    # Both pulleys wrap the same angle beta = pi + 2*asin((D+d)/(2C)) > pi.
    crossed_beta = crossed_belt_wrap_angle(**kw)
    assert crossed_beta == pytest.approx(pi + 2 * asin(450 / 1200), rel=1e-12)
    assert crossed_beta > pi > belt_wrap_angle(**kw)
    # The pulleys must clear at the cross (C > (D+d)/2).
    with pytest.raises(ValueError, match=r"must exceed \(D\+d\)/2"):
        crossed_belt_length(
            large_pulley_diameter=_q("300 mm"),
            small_pulley_diameter=_q("150 mm"),
            center_distance=_q("200 mm"),
        )


def test_vee_belt_effective_friction_multiplies_grip():
    from math import radians, sin

    # A 38-degree groove: mu' = mu/sin(19 deg) = 0.3/0.32557 = 0.9215.
    mu_eff = vee_belt_effective_friction(friction_coefficient=0.3, groove_angle=38)
    assert mu_eff == pytest.approx(0.3 / sin(radians(19)), rel=1e-9)
    # The wedge roughly triples the effective friction over a flat belt.
    assert mu_eff > 3 * 0.3 * 0.9
    # A narrower groove grips even harder.
    assert vee_belt_effective_friction(friction_coefficient=0.3, groove_angle=34) > mu_eff
    with pytest.raises(ValueError, match=r"groove_angle \(degrees\) must lie in"):
        vee_belt_effective_friction(friction_coefficient=0.3, groove_angle=0)


def test_capstan_tension_ratio_and_belt_tensions():
    from math import exp, pi

    # A rope with a 180-degree wrap (beta=pi) at mu=0.3: T1/T2 = e^(0.3*pi) = 2.566.
    ratio = capstan_tension_ratio(friction_coefficient=0.3, wrap_angle=pi)
    assert ratio == pytest.approx(exp(0.3 * pi), rel=1e-12)
    # 500 N tight side -> slack side is T1/ratio, and the two split the tight
    # tension: slack + transmissible force = tight.
    slack = belt_slack_tension(tight_tension=_q("500 N"), friction_coefficient=0.3, wrap_angle=pi)
    force = belt_max_transmissible_force(
        tight_tension=_q("500 N"), friction_coefficient=0.3, wrap_angle=pi
    )
    assert slack.to("N").magnitude == pytest.approx(500 / ratio, rel=1e-12)
    assert slack.to("N").magnitude + force.to("N").magnitude == pytest.approx(500.0, rel=1e-12)
    # More wrap (a second turn) grips exponentially harder.
    two_turns = capstan_tension_ratio(friction_coefficient=0.3, wrap_angle=pi + 2 * pi)
    assert two_turns > ratio


def test_capstan_rejects_bad_inputs():
    from math import pi

    with pytest.raises(ValueError, match="friction_coefficient must be non-negative"):
        capstan_tension_ratio(friction_coefficient=-0.1, wrap_angle=pi)
    with pytest.raises(ValueError, match="wrap_angle .* must be positive"):
        capstan_tension_ratio(friction_coefficient=0.3, wrap_angle=0.0)
    with pytest.raises(ValueError, match="tight_tension must be a"):
        belt_slack_tension(tight_tension=_q("500 mm"), friction_coefficient=0.3, wrap_angle=pi)


def test_belt_centrifugal_tension_sheds_grip_at_speed():
    from math import pi

    # 0.25 kg/m of belt at 20 m/s carries Tc = m'*v^2 = 100 N of its own tension.
    tc = belt_centrifugal_tension(linear_density=_q("0.25 kg/m"), belt_speed=_q("20 m/s"))
    assert tc.to("N").magnitude == pytest.approx(100.0, rel=1e-12)
    # Only the excess above Tc grips: at speed the transmissible force is the
    # still-belt force evaluated on (T1 - Tc).
    at_speed = belt_max_transmissible_force_at_speed(
        tight_tension=_q("500 N"),
        linear_density=_q("0.25 kg/m"),
        belt_speed=_q("20 m/s"),
        friction_coefficient=0.3,
        wrap_angle=pi,
    )
    reduced = belt_max_transmissible_force(
        tight_tension=_q("400 N"), friction_coefficient=0.3, wrap_angle=pi
    )
    assert at_speed.to("N").magnitude == pytest.approx(reduced.to("N").magnitude, rel=1e-12)
    # At rest it reduces exactly to the still-belt form.
    at_rest = belt_max_transmissible_force_at_speed(
        tight_tension=_q("500 N"),
        linear_density=_q("0.25 kg/m"),
        belt_speed=_q("0 m/s"),
        friction_coefficient=0.3,
        wrap_angle=pi,
    )
    still = belt_max_transmissible_force(
        tight_tension=_q("500 N"), friction_coefficient=0.3, wrap_angle=pi
    )
    assert at_rest.to("N").magnitude == pytest.approx(still.to("N").magnitude, rel=1e-12)
    # Past the speed where Tc eats the whole tight tension the belt transmits
    # nothing -- the function refuses rather than returning a negative force.
    with pytest.raises(ValueError, match="cannot transmit"):
        belt_max_transmissible_force_at_speed(
            tight_tension=_q("500 N"),
            linear_density=_q("0.25 kg/m"),
            belt_speed=_q("45 m/s"),
            friction_coefficient=0.3,
            wrap_angle=pi,
        )


def test_belt_speed_for_max_power_is_the_power_peak():
    from math import pi

    # v* = sqrt(T1/(3 m')): 500 N / 0.25 kg/m -> 25.820 m/s, where Tc = T1/3.
    v_star = belt_speed_for_max_power(tight_tension=_q("500 N"), linear_density=_q("0.25 kg/m"))
    assert v_star.to("m/s").magnitude == pytest.approx((500.0 / 0.75) ** 0.5, rel=1e-12)
    tc = belt_centrifugal_tension(linear_density=_q("0.25 kg/m"), belt_speed=v_star)
    assert tc.to("N").magnitude == pytest.approx(500.0 / 3.0, rel=1e-12)

    # Power = force * speed genuinely peaks there: v* beats speeds 10% either side.
    def power(v: float) -> float:
        force = belt_max_transmissible_force_at_speed(
            tight_tension=_q("500 N"),
            linear_density=_q("0.25 kg/m"),
            belt_speed=_q(f"{v} m/s"),
            friction_coefficient=0.3,
            wrap_angle=pi,
        )
        return force.to("N").magnitude * v

    best = power(v_star.to("m/s").magnitude)
    assert best > power(0.9 * v_star.to("m/s").magnitude)
    assert best > power(1.1 * v_star.to("m/s").magnitude)
    with pytest.raises(ValueError, match="linear_density must be a"):
        belt_speed_for_max_power(tight_tension=_q("500 N"), linear_density=_q("0.25 kg"))


def test_band_brake_torque_is_the_capstan_grip_at_the_drum_radius():
    from math import exp, pi

    # 2 kN anchor tension, mu=0.25 lining, 270-degree wrap on a 300 mm drum:
    # grip = 1 - e^(-0.25*3pi/2) = 0.69216, T = 2000*0.69216*0.15 = 207.65 N*m.
    wrap = 3.0 * pi / 2.0
    torque = band_brake_torque(
        tight_tension=_q("2 kN"),
        drum_diameter=_q("300 mm"),
        friction_coefficient=0.25,
        wrap_angle=wrap,
    )
    grip = 1.0 - exp(-0.25 * wrap)
    assert torque.to("N*m").magnitude == pytest.approx(2000.0 * grip * 0.15, rel=1e-12)
    assert torque.to("N*m").magnitude == pytest.approx(207.648, rel=1e-4)
    # The torque IS the belt transmissible force acting at the drum radius —
    # single source of truth with the capstan primitive.
    force = belt_max_transmissible_force(
        tight_tension=_q("2 kN"), friction_coefficient=0.25, wrap_angle=wrap
    )
    assert torque.to("N*m").magnitude == pytest.approx(force.to("N").magnitude * 0.15, rel=1e-12)
    # More wrap holds more torque with the same band tension.
    fuller_wrap = band_brake_torque(
        tight_tension=_q("2 kN"),
        drum_diameter=_q("300 mm"),
        friction_coefficient=0.25,
        wrap_angle=2.0 * pi,
    )
    assert fuller_wrap.to("N*m").magnitude > torque.to("N*m").magnitude


def test_band_brake_tension_inverse_round_trips():
    from math import pi

    # Size the band for a 500 N*m hold, then check the forward torque lands on it.
    wrap = 3.0 * pi / 2.0
    tension = band_brake_tight_tension_for_torque(
        torque=_q("500 N*m"),
        drum_diameter=_q("300 mm"),
        friction_coefficient=0.25,
        wrap_angle=wrap,
    )
    back = band_brake_torque(
        tight_tension=tension,
        drum_diameter=_q("300 mm"),
        friction_coefficient=0.25,
        wrap_angle=wrap,
    )
    assert back.to("N*m").magnitude == pytest.approx(500.0, rel=1e-12)


def test_band_brake_lining_pressure_peaks_at_the_tight_end():
    # p_max = 2*T1/(b*D): 2 kN on a 50 mm band over a 300 mm drum -> 0.2667 MPa,
    # under a ~0.34 MPa woven-lining allowable.
    pressure = band_brake_max_lining_pressure(
        tight_tension=_q("2 kN"), band_width=_q("50 mm"), drum_diameter=_q("300 mm")
    )
    assert pressure.to("MPa").magnitude == pytest.approx(2.0 * 2000.0 / (50.0 * 300.0), rel=1e-12)
    assert pressure.to("MPa").magnitude == pytest.approx(0.26667, rel=1e-4)
    # A wider band spreads the same tension thinner.
    wider = band_brake_max_lining_pressure(
        tight_tension=_q("2 kN"), band_width=_q("80 mm"), drum_diameter=_q("300 mm")
    )
    assert wider.to("MPa").magnitude < pressure.to("MPa").magnitude


def test_band_brake_rejects_bad_inputs():
    from math import pi

    with pytest.raises(ValueError, match="drum_diameter must be positive"):
        band_brake_torque(
            tight_tension=_q("2 kN"),
            drum_diameter=_q("0 mm"),
            friction_coefficient=0.25,
            wrap_angle=pi,
        )
    with pytest.raises(ValueError, match="torque must be positive"):
        band_brake_tight_tension_for_torque(
            torque=_q("0 N*m"),
            drum_diameter=_q("300 mm"),
            friction_coefficient=0.25,
            wrap_angle=pi,
        )
    with pytest.raises(ValueError, match="friction_coefficient must be positive"):
        band_brake_tight_tension_for_torque(
            torque=_q("500 N*m"),
            drum_diameter=_q("300 mm"),
            friction_coefficient=0.0,
            wrap_angle=pi,
        )
    with pytest.raises(ValueError, match="band_width must be positive"):
        band_brake_max_lining_pressure(
            tight_tension=_q("2 kN"), band_width=_q("0 mm"), drum_diameter=_q("300 mm")
        )
    with pytest.raises(ValueError, match="tight_tension must be a"):
        band_brake_max_lining_pressure(
            tight_tension=_q("2 m"), band_width=_q("50 mm"), drum_diameter=_q("300 mm")
        )


def test_bearing_basic_rating_life_follows_the_load_life_law():
    # A ball bearing rated C=14 kN carrying P=2 kN: L10 = (14/2)^3 = 343 million
    # revolutions.
    life = bearing_basic_rating_life(dynamic_load_rating=_q("14 kN"), equivalent_load=_q("2 kN"))
    assert life == pytest.approx(343.0, rel=1e-9)
    # The law is steep: halving the load raises a ball bearing's life 8x.
    half_load = bearing_basic_rating_life(
        dynamic_load_rating=_q("14 kN"), equivalent_load=_q("1 kN")
    )
    assert half_load == pytest.approx(8 * life, rel=1e-9)
    # A roller bearing (p=10/3) outlives a ball bearing at the same C/P ratio.
    roller = bearing_basic_rating_life(
        dynamic_load_rating=_q("14 kN"),
        equivalent_load=_q("2 kN"),
        life_exponent=ROLLER_BEARING_LIFE_EXPONENT,
    )
    assert roller == pytest.approx(7 ** (10 / 3), rel=1e-9)
    assert roller > life


def test_bearing_static_safety_factor():
    # s0 = C0/P0: a 12 kN static rating under a 4 kN static load -> 3.0.
    s0 = bearing_static_safety_factor(
        static_load_rating=_q("12 kN"), equivalent_static_load=_q("4 kN")
    )
    assert s0 == pytest.approx(3.0, rel=1e-12)
    with pytest.raises(ValueError, match="equivalent_static_load must be positive"):
        bearing_static_safety_factor(
            static_load_rating=_q("12 kN"), equivalent_static_load=_q("0 kN")
        )
    with pytest.raises(ValueError, match="static_load_rating must be a"):
        bearing_static_safety_factor(
            static_load_rating=_q("12 mm"), equivalent_static_load=_q("4 kN")
        )


def test_bearing_life_hours_converts_revolutions_at_speed():
    # 343 Mrev at 1800 rpm: L10h = 343e6 / (60*1800) = 3175.93 hours.
    hours = bearing_life_hours(
        dynamic_load_rating=_q("14 kN"), equivalent_load=_q("2 kN"), speed=_q("1800 rpm")
    )
    assert hours.to("hour").magnitude == pytest.approx(3175.926, rel=1e-4)
    # Twice the speed spends the same revolutions in half the hours.
    faster = bearing_life_hours(
        dynamic_load_rating=_q("14 kN"), equivalent_load=_q("2 kN"), speed=_q("3600 rpm")
    )
    assert faster.to("hour").magnitude == pytest.approx(hours.to("hour").magnitude / 2, rel=1e-9)


def test_bearing_life_rejects_bad_inputs():
    with pytest.raises(ValueError, match="dynamic_load_rating must be a"):
        bearing_basic_rating_life(dynamic_load_rating=_q("14 mm"), equivalent_load=_q("2 kN"))
    with pytest.raises(ValueError, match="equivalent_load must be positive"):
        bearing_basic_rating_life(dynamic_load_rating=_q("14 kN"), equivalent_load=_q("0 kN"))
    with pytest.raises(ValueError, match="life_exponent must be positive"):
        bearing_basic_rating_life(
            dynamic_load_rating=_q("14 kN"), equivalent_load=_q("2 kN"), life_exponent=0.0
        )
    with pytest.raises(ValueError, match="speed must be a"):
        bearing_life_hours(
            dynamic_load_rating=_q("14 kN"), equivalent_load=_q("2 kN"), speed=_q("1800 N")
        )


def test_shear_flow_and_fastener_spacing():
    # Built-up beam: V=10 kN, Q=120,000 mm^3, I=50e6 mm^4 -> q = V*Q/I = 24 N/mm.
    q = shear_flow(
        shear_force=_q("10 kN"),
        first_moment_of_area=_q("120000 mm**3"),
        second_moment_of_area=_q("50e6 mm**4"),
    )
    assert q.to("N/mm").magnitude == pytest.approx(24.0, rel=1e-9)
    # A 4 kN fastener can sit at most s = F/q = 4000/24 = 166.7 mm apart.
    s = fastener_spacing_for_shear_flow(fastener_capacity=_q("4 kN"), shear_flow=q)
    assert s.to("mm").magnitude == pytest.approx(166.667, rel=1e-4)
    # A double row (twice the capacity) doubles the allowable spacing.
    s2 = fastener_spacing_for_shear_flow(fastener_capacity=_q("8 kN"), shear_flow=q)
    assert s2.to("mm").magnitude == pytest.approx(2 * s.to("mm").magnitude, rel=1e-9)


def test_shear_flow_rejects_bad_inputs():
    with pytest.raises(ValueError, match="first_moment_of_area must be a"):
        shear_flow(
            shear_force=_q("10 kN"),
            first_moment_of_area=_q("120000 mm**2"),
            second_moment_of_area=_q("50e6 mm**4"),
        )
    with pytest.raises(ValueError, match="second_moment_of_area must be positive"):
        shear_flow(
            shear_force=_q("10 kN"),
            first_moment_of_area=_q("120000 mm**3"),
            second_moment_of_area=_q("0 mm**4"),
        )
    with pytest.raises(ValueError, match="shear_flow must be positive"):
        fastener_spacing_for_shear_flow(fastener_capacity=_q("4 kN"), shear_flow=_q("0 N/mm"))


def test_preloaded_bolt_cyclic_stress_keeps_the_amplitude_small():
    # Fi=25 kN, C=0.3, external 0..10 kN, A_t=84.3 mm^2. Bolt stress runs between
    # (25000)/84.3 = 296.6 and (25000+3000)/84.3 = 332.1 MPa.
    cs = preloaded_bolt_cyclic_stress(
        preload=_q("25 kN"),
        min_external_load=_q("0 kN"),
        max_external_load=_q("10 kN"),
        stiffness_factor=0.3,
        tensile_stress_area=_q("84.3 mm**2"),
    )
    # Alternating = C*(Pmax-Pmin)/(2*A_t) is tiny (17.8 MPa) despite a high mean...
    assert cs.alternating_stress.to("MPa").magnitude == pytest.approx(17.794, rel=1e-3)
    assert cs.mean_stress.to("MPa").magnitude == pytest.approx(314.353, rel=1e-4)
    # ...which is the point of preload: the amplitude stays far below the mean.
    assert cs.alternating_stress.to("MPa").magnitude < cs.mean_stress.to("MPa").magnitude
    # It feeds straight into a Goodman screen.
    from anvilate.analysis import goodman_safety_factor

    n = goodman_safety_factor(
        alternating_stress=cs.alternating_stress,
        mean_stress=cs.mean_stress,
        endurance_limit=_q("120 MPa"),
        ultimate_strength=_q("800 MPa"),
    )
    assert n > 1  # a preloaded bolt survives the fluctuating load


def test_preloaded_bolt_cyclic_stress_rejects_bad_inputs():
    good = {
        "preload": _q("25 kN"),
        "min_external_load": _q("0 kN"),
        "stiffness_factor": 0.3,
        "tensile_stress_area": _q("84.3 mm**2"),
    }
    with pytest.raises(ValueError, match="max_external_load .* must be at least"):
        preloaded_bolt_cyclic_stress(max_external_load=_q("-5 kN"), **good)
    with pytest.raises(ValueError, match="tensile_stress_area must be a"):
        preloaded_bolt_cyclic_stress(
            preload=_q("25 kN"),
            min_external_load=_q("0 kN"),
            max_external_load=_q("10 kN"),
            stiffness_factor=0.3,
            tensile_stress_area=_q("84.3 mm"),
        )


def test_preloaded_joint_shares_the_external_load():
    # A joint with a bolt 3 MN/m into members 7 MN/m: C = 3/(3+7) = 0.3.
    c = joint_stiffness_factor(bolt_stiffness=_q("3 MN/m"), member_stiffness=_q("7 MN/m"))
    assert c == pytest.approx(0.3, rel=1e-12)
    kw = {"preload": _q("25 kN"), "external_load": _q("10 kN"), "stiffness_factor": c}
    # The bolt sees only C*P = 3 kN of the 10 kN external load on top of preload.
    bolt = bolt_load_in_joint(**kw)
    assert bolt.to("kN").magnitude == pytest.approx(28.0, rel=1e-9)
    # The members shed (1-C)*P = 7 kN of clamp, leaving 18 kN.
    clamp = member_clamp_load_in_joint(**kw)
    assert clamp.to("kN").magnitude == pytest.approx(18.0, rel=1e-9)
    # The bolt load plus the clamp relief equals preload plus the full external load.
    assert bolt.to("kN").magnitude + (25.0 - clamp.to("kN").magnitude) == pytest.approx(
        25.0 + 10.0, rel=1e-9
    )


def test_joint_separation_load_opens_the_clamp():
    c = joint_stiffness_factor(bolt_stiffness=_q("3 MN/m"), member_stiffness=_q("7 MN/m"))
    # Separation at P0 = Fi/(1-C) = 25/0.7 = 35.71 kN.
    p0 = joint_separation_load(preload=_q("25 kN"), stiffness_factor=c)
    assert p0.to("kN").magnitude == pytest.approx(35.714, rel=1e-4)
    # At exactly P0 the member clamp reaches zero.
    clamp = member_clamp_load_in_joint(preload=_q("25 kN"), external_load=p0, stiffness_factor=c)
    assert clamp.to("kN").magnitude == pytest.approx(0.0, abs=1e-9)


def test_preloaded_joint_rejects_bad_inputs():
    with pytest.raises(ValueError, match="member_stiffness must be positive"):
        joint_stiffness_factor(bolt_stiffness=_q("3 MN/m"), member_stiffness=_q("0 MN/m"))
    with pytest.raises(ValueError, match=r"stiffness_factor .* must lie in \(0, 1\)"):
        bolt_load_in_joint(preload=_q("25 kN"), external_load=_q("10 kN"), stiffness_factor=1.0)
    with pytest.raises(ValueError, match="preload must be a"):
        joint_separation_load(preload=_q("25 mm"), stiffness_factor=0.3)


def test_eccentric_shear_group_peak_force_matches_the_vector_sum():
    from math import sqrt

    def mm(v):
        return _q(f"{v} mm")

    # Two bolts on a vertical line +-50 mm; a 10 kN load offset 100 mm sideways.
    # J = 2*50^2 = 5000 mm^2, T = 10 kN * 100 mm = 1e6 N*mm. The extreme bolt sees
    # a torsional 10 kN horizontal + a direct 5 kN vertical -> sqrt(10^2+5^2)=11.18.
    positions = [(mm(0), mm(50)), (mm(0), mm(-50))]
    peak = eccentric_shear_group_peak_force(
        positions=positions, load=_q("10 kN"), eccentricity=mm(100)
    )
    assert peak.to("N").magnitude == pytest.approx(sqrt(10000.0**2 + 5000.0**2), rel=1e-12)
    assert peak.to("kN").magnitude == pytest.approx(11.180, rel=1e-3)
    # A concentric load (zero eccentricity) puts pure direct shear on each bolt.
    concentric = eccentric_shear_group_peak_force(
        positions=positions, load=_q("10 kN"), eccentricity=mm(0)
    )
    assert concentric.to("kN").magnitude == pytest.approx(5.0, rel=1e-12)
    # A wider bolt group (bigger J) carries the same eccentric load with less peak.
    wide = eccentric_shear_group_peak_force(
        positions=[(mm(0), mm(150)), (mm(0), mm(-150))],
        load=_q("10 kN"),
        eccentricity=mm(100),
    )
    assert wide.to("N").magnitude < peak.to("N").magnitude
    with pytest.raises(ValueError, match="at least two fasteners"):
        eccentric_shear_group_peak_force(
            positions=[(mm(0), mm(0))], load=_q("10 kN"), eccentricity=mm(100)
        )
    with pytest.raises(ValueError, match="must not all coincide"):
        eccentric_shear_group_peak_force(
            positions=[(mm(0), mm(0)), (mm(0), mm(0))], load=_q("10 kN"), eccentricity=mm(100)
        )


def test_thread_stripping_shear_area_matches_basic_profile():
    # M12x1.75, 12 mm engagement. External (bolt) threads strip on a cylinder at
    # the internal minor diameter D1 = 12 - 1.0825*1.75 = 10.106 mm:
    #   A = 0.75*pi*10.106*12 = 285.7 mm^2.
    ext = thread_stripping_shear_area(
        nominal_diameter=_q("12 mm"), pitch=_q("1.75 mm"), engagement_length=_q("12 mm")
    )
    assert ext.to("mm**2").magnitude == pytest.approx(285.7, rel=1e-3)
    # Internal (nut) threads strip on a cylinder at the major diameter d = 12 mm:
    #   A = 0.875*pi*12*12 = 395.8 mm^2.
    internal = thread_stripping_shear_area(
        nominal_diameter=_q("12 mm"),
        pitch=_q("1.75 mm"),
        engagement_length=_q("12 mm"),
        member="internal",
    )
    assert internal.to("mm**2").magnitude == pytest.approx(395.8, rel=1e-3)
    # With matched materials the bolt threads strip first: the internal area is
    # always the larger (0.875*d > 0.75*D1 for any metric thread).
    assert internal.to("mm**2").magnitude > ext.to("mm**2").magnitude
    # The area is linear in the length of engagement.
    doubled = thread_stripping_shear_area(
        nominal_diameter=_q("12 mm"), pitch=_q("1.75 mm"), engagement_length=_q("24 mm")
    )
    assert doubled.to("mm**2").magnitude == pytest.approx(2 * ext.to("mm**2").magnitude, rel=1e-9)


def test_thread_stripping_stress_is_load_over_area():
    # 30 kN over the external stripping area of an M12x1.75 at 12 mm engagement:
    #   tau = 30000 / 285.7 = 105.0 MPa.
    tau = thread_stripping_stress(
        load=_q("30 kN"),
        nominal_diameter=_q("12 mm"),
        pitch=_q("1.75 mm"),
        engagement_length=_q("12 mm"),
    )
    area = thread_stripping_shear_area(
        nominal_diameter=_q("12 mm"), pitch=_q("1.75 mm"), engagement_length=_q("12 mm")
    )
    assert tau.to("MPa").magnitude == pytest.approx(105.0, rel=1e-3)
    assert tau.to("MPa").magnitude == pytest.approx(30000.0 / area.to("mm**2").magnitude, rel=1e-9)
    # The internal (nut) threads see a lower stress on their larger area.
    tau_int = thread_stripping_stress(
        load=_q("30 kN"),
        nominal_diameter=_q("12 mm"),
        pitch=_q("1.75 mm"),
        engagement_length=_q("12 mm"),
        member="internal",
    )
    assert tau_int.to("MPa").magnitude < tau.to("MPa").magnitude


def test_thread_stripping_rejects_bad_inputs():
    with pytest.raises(ValueError, match="pitch must be positive"):
        thread_stripping_shear_area(
            nominal_diameter=_q("12 mm"), pitch=_q("0 mm"), engagement_length=_q("12 mm")
        )
    with pytest.raises(ValueError, match="engagement_length must be positive"):
        thread_stripping_shear_area(
            nominal_diameter=_q("12 mm"), pitch=_q("1.75 mm"), engagement_length=_q("0 mm")
        )
    with pytest.raises(ValueError, match="must exceed 1.0825"):
        thread_stripping_shear_area(
            nominal_diameter=_q("1 mm"), pitch=_q("2 mm"), engagement_length=_q("12 mm")
        )
    with pytest.raises(ValueError, match="member must be"):
        thread_stripping_shear_area(
            nominal_diameter=_q("12 mm"),
            pitch=_q("1.75 mm"),
            engagement_length=_q("12 mm"),
            member="bolt",
        )
    with pytest.raises(ValueError, match="load must be a"):
        thread_stripping_stress(
            load=_q("12 mm"),
            nominal_diameter=_q("12 mm"),
            pitch=_q("1.75 mm"),
            engagement_length=_q("12 mm"),
        )


def test_thread_engagement_for_load_inverts_the_stripping_stress():
    # Size the aluminium tapped hole (member="internal") so 40 kN develops within
    # a 159 MPa allowable: at the returned engagement the stripping stress lands
    # exactly on the allowable.
    le = thread_engagement_for_load(
        load=_q("40 kN"),
        nominal_diameter=_q("12 mm"),
        pitch=_q("1.75 mm"),
        allowable_shear=_q("159 MPa"),
        member="internal",
    )
    tau = thread_stripping_stress(
        load=_q("40 kN"),
        nominal_diameter=_q("12 mm"),
        pitch=_q("1.75 mm"),
        engagement_length=le,
        member="internal",
    )
    assert tau.to("MPa").magnitude == pytest.approx(159.0, rel=1e-9)
    # A required safety factor scales the engagement linearly.
    le2 = thread_engagement_for_load(
        load=_q("40 kN"),
        nominal_diameter=_q("12 mm"),
        pitch=_q("1.75 mm"),
        allowable_shear=_q("159 MPa"),
        member="internal",
        required_safety_factor=2.0,
    )
    assert le2.to("mm").magnitude == pytest.approx(2 * le.to("mm").magnitude, rel=1e-9)
    # The bolt's external threads, on the smaller shear cylinder, need a deeper
    # engagement than the nut threads for the same load and allowable.
    le_ext = thread_engagement_for_load(
        load=_q("40 kN"),
        nominal_diameter=_q("12 mm"),
        pitch=_q("1.75 mm"),
        allowable_shear=_q("159 MPa"),
        member="external",
    )
    assert le_ext.to("mm").magnitude > le.to("mm").magnitude


def test_thread_engagement_for_load_rejects_bad_inputs():
    with pytest.raises(ValueError, match="allowable_shear must be positive"):
        thread_engagement_for_load(
            load=_q("40 kN"),
            nominal_diameter=_q("12 mm"),
            pitch=_q("1.75 mm"),
            allowable_shear=_q("0 MPa"),
        )
    with pytest.raises(ValueError, match="required_safety_factor must be positive"):
        thread_engagement_for_load(
            load=_q("40 kN"),
            nominal_diameter=_q("12 mm"),
            pitch=_q("1.75 mm"),
            allowable_shear=_q("159 MPa"),
            required_safety_factor=0.0,
        )
    with pytest.raises(ValueError, match="member must be"):
        thread_engagement_for_load(
            load=_q("40 kN"),
            nominal_diameter=_q("12 mm"),
            pitch=_q("1.75 mm"),
            allowable_shear=_q("159 MPa"),
            member="nut",
        )


def test_shaft_von_mises_stress_is_the_forward_of_the_sizing_inverse():
    # At the diameter the combined-loading inverse returns, the forward von Mises
    # stress lands exactly on the allowable Sy/n = 350/2 = 175 MPa.
    d = shaft_diameter_for_bending_torsion(
        bending_moment=_q("300 N*m"),
        torque=_q("500 N*m"),
        yield_strength=_q("350 MPa"),
        required_safety_factor=2.0,
    )
    vm = shaft_von_mises_stress(bending_moment=_q("300 N*m"), torque=_q("500 N*m"), diameter=d)
    assert vm.to("MPa").magnitude == pytest.approx(175.0, rel=1e-9)
    # It equals sqrt(sigma^2 + 3*tau^2) built from the separate bending and shear.
    sigma = _q(f"{32 * 300000.0 / (pi * d.to('mm').magnitude ** 3)} MPa")
    tau = shaft_torsional_stress(torque=_q("500 N*m"), diameter=d)
    combined = von_mises_bending_torsion(bending_stress=sigma, shear_stress=tau)
    assert vm.to("MPa").magnitude == pytest.approx(combined.to("MPa").magnitude, rel=1e-9)
    # Pure bending (T=0) reduces to the plain bending stress 32*M/(pi*d^3).
    pure_bending = shaft_von_mises_stress(
        bending_moment=_q("300 N*m"), torque=_q("0 N*m"), diameter=_q("40 mm")
    )
    assert pure_bending.to("MPa").magnitude == pytest.approx(32 * 300000.0 / (pi * 40**3), rel=1e-9)


def test_shaft_von_mises_stress_rejects_bad_inputs():
    with pytest.raises(ValueError, match="bending_moment must be a"):
        shaft_von_mises_stress(
            bending_moment=_q("300 mm"), torque=_q("500 N*m"), diameter=_q("40 mm")
        )
    with pytest.raises(ValueError, match="diameter must be a"):
        shaft_von_mises_stress(
            bending_moment=_q("300 N*m"), torque=_q("500 N*m"), diameter=_q("40 N")
        )


def test_shaft_diameter_for_bending_torsion_matches_worked_example():
    # 300 N*m bending + 500 N*m torsion, Sy 350 MPa, SF 2.0:
    #   d = (32*n*sqrt(M^2 + 0.75*T^2)/(pi*Sy))^(1/3) = 31.30 mm.
    d = shaft_diameter_for_bending_torsion(
        bending_moment=_q("300 N*m"),
        torque=_q("500 N*m"),
        yield_strength=_q("350 MPa"),
        required_safety_factor=2.0,
    )
    assert d.to("mm").magnitude == pytest.approx(31.299, rel=1e-4)


def test_shaft_diameter_for_bending_torsion_lands_on_the_von_mises_allowable():
    # At the sized diameter the von Mises stress equals exactly Sy/n.
    d = shaft_diameter_for_bending_torsion(
        bending_moment=_q("300 N*m"),
        torque=_q("500 N*m"),
        yield_strength=_q("350 MPa"),
        required_safety_factor=2.0,
    )
    d3 = d.to("mm").magnitude ** 3
    sigma = _q(f"{32 * 300000.0 / (pi * d3)} MPa")  # 32*M/(pi*d^3), M in N*mm
    tau = shaft_torsional_stress(torque=_q("500 N*m"), diameter=d)
    vm = von_mises_bending_torsion(bending_stress=sigma, shear_stress=tau)
    assert vm.to("MPa").magnitude == pytest.approx(175.0, rel=1e-6)  # Sy/n = 350/2


def test_hollow_shaft_diameter_for_bending_torsion_inflates_the_solid_size():
    kw = {
        "bending_moment": _q("300 N*m"),
        "torque": _q("500 N*m"),
        "yield_strength": _q("350 MPa"),
        "required_safety_factor": 2.0,
    }
    solid = shaft_diameter_for_bending_torsion(**kw)
    # A k=0.6 bore needs a slightly larger outer diameter: d_o = d_solid/(1-k^4)^(1/3).
    hollow = hollow_shaft_diameter_for_bending_torsion(bore_ratio=0.6, **kw)
    factor = (1 - 0.6**4) ** (1 / 3)
    assert hollow.to("mm").magnitude == pytest.approx(solid.to("mm").magnitude / factor, rel=1e-9)
    assert hollow.to("mm").magnitude == pytest.approx(32.781, rel=1e-4)
    # ...yet the tube is far lighter: cross-section (d_o^2 - d_i^2) < solid d^2.
    do = hollow.to("mm").magnitude
    di = 0.6 * do
    assert do**2 - di**2 < solid.to("mm").magnitude ** 2
    # k=0 recovers the solid diameter exactly.
    zero_bore = hollow_shaft_diameter_for_bending_torsion(bore_ratio=0.0, **kw)
    assert zero_bore.to("mm").magnitude == pytest.approx(solid.to("mm").magnitude, rel=1e-12)


def test_hollow_shaft_diameter_for_bending_torsion_rejects_bad_bore_ratio():
    kw = {
        "bending_moment": _q("300 N*m"),
        "torque": _q("500 N*m"),
        "yield_strength": _q("350 MPa"),
    }
    with pytest.raises(ValueError, match="bore_ratio must be in"):
        hollow_shaft_diameter_for_bending_torsion(bore_ratio=1.0, **kw)
    with pytest.raises(ValueError, match="bore_ratio must be in"):
        hollow_shaft_diameter_for_bending_torsion(bore_ratio=-0.1, **kw)


def test_shaft_diameter_for_bending_torsion_scales_and_rejects_bad_inputs():
    # More margin -> larger shaft, growing as the cube root of n.
    base = shaft_diameter_for_bending_torsion(
        bending_moment=_q("300 N*m"), torque=_q("500 N*m"), yield_strength=_q("350 MPa")
    )
    doubled = shaft_diameter_for_bending_torsion(
        bending_moment=_q("300 N*m"),
        torque=_q("500 N*m"),
        yield_strength=_q("350 MPa"),
        required_safety_factor=2.0,
    )
    assert doubled.to("mm").magnitude == pytest.approx(
        base.to("mm").magnitude * 2 ** (1 / 3), rel=1e-9
    )
    with pytest.raises(ValueError, match="yield_strength must be positive"):
        shaft_diameter_for_bending_torsion(
            bending_moment=_q("300 N*m"), torque=_q("500 N*m"), yield_strength=_q("0 MPa")
        )
    with pytest.raises(ValueError, match="required_safety_factor must be positive"):
        shaft_diameter_for_bending_torsion(
            bending_moment=_q("300 N*m"),
            torque=_q("500 N*m"),
            yield_strength=_q("350 MPa"),
            required_safety_factor=0.0,
        )
    with pytest.raises(ValueError, match="bending_moment must be a"):
        shaft_diameter_for_bending_torsion(
            bending_moment=_q("300 mm"), torque=_q("500 N*m"), yield_strength=_q("350 MPa")
        )


def test_polar_second_moment_solid_matches_pi_d4_over_32():
    # d=20 mm: J = pi*20^4/32 = 15708 mm^4.
    j = polar_second_moment_solid(_q("20 mm"))
    assert j.to("mm**4").magnitude == pytest.approx(15707.96, rel=1e-4)


def test_shaft_torsional_stress_matches_worked_example():
    # 50 N*m through a 20 mm solid shaft: tau = 16*T/(pi*d^3)
    #   = 16*50 / (pi*0.02^3) = 31.83 MPa.
    tau = shaft_torsional_stress(torque=_q("50 N*m"), diameter=_q("20 mm"))
    assert tau.to("MPa").magnitude == pytest.approx(31.831, rel=1e-4)


def test_torque_from_power_matches_worked_example():
    # 30 kW at 730 rpm: T = P/omega = 30000/(2*pi*730/60) = 392.4 N*m.
    t = torque_from_power(power=_q("30 kW"), rotational_speed=_q("730 rpm"))
    assert t.to("N*m").magnitude == pytest.approx(392.44, rel=1e-3)
    # rad/s input gives the same torque (both carry the 2*pi).
    same = torque_from_power(power=_q("30 kW"), rotational_speed=_q("76.4454 rad/s"))
    assert same.to("N*m").magnitude == pytest.approx(t.to("N*m").magnitude, rel=1e-4)
    # Torque falls as speed rises for the same power.
    faster = torque_from_power(power=_q("30 kW"), rotational_speed=_q("1460 rpm"))
    assert faster.to("N*m").magnitude == pytest.approx(t.to("N*m").magnitude / 2, rel=1e-6)


def test_torque_from_power_rejects_bad_inputs():
    with pytest.raises(ValueError, match="power must be a"):
        torque_from_power(power=_q("30 N"), rotational_speed=_q("730 rpm"))
    with pytest.raises(ValueError, match="rotational_speed must be positive"):
        torque_from_power(power=_q("30 kW"), rotational_speed=_q("0 rpm"))


def test_shaft_diameter_for_torque_inverts_the_shear_check():
    # 500 N*m within a 40 MPa allowable needs d = (16*T/(pi*tau))^(1/3)
    #   = (16*500000/(pi*40))^(1/3) = 39.92 mm.
    d = shaft_diameter_for_torque(torque=_q("500 N*m"), allowable_shear=_q("40 MPa"))
    assert d.to("mm").magnitude == pytest.approx(39.92, rel=1e-3)
    # A shaft of exactly this diameter is worked to the allowable.
    tau = shaft_torsional_stress(torque=_q("500 N*m"), diameter=d)
    assert tau.to("MPa").magnitude == pytest.approx(40.0, rel=1e-6)


def test_shaft_diameter_for_torque_scales_as_the_cube_root_of_the_margin():
    base = shaft_diameter_for_torque(torque=_q("500 N*m"), allowable_shear=_q("40 MPa"))
    with_sf = shaft_diameter_for_torque(
        torque=_q("500 N*m"), allowable_shear=_q("40 MPa"), required_safety_factor=2.0
    )
    # Diameter scales with the cube root of the required margin.
    assert with_sf.to("mm").magnitude == pytest.approx(
        2.0 ** (1 / 3) * base.to("mm").magnitude, rel=1e-9
    )


def test_shaft_diameter_for_torque_rejects_bad_inputs():
    with pytest.raises(ValueError, match="torque must be a"):
        shaft_diameter_for_torque(torque=_q("500 N"), allowable_shear=_q("40 MPa"))
    with pytest.raises(ValueError, match="allowable_shear must be positive"):
        shaft_diameter_for_torque(torque=_q("500 N*m"), allowable_shear=_q("0 MPa"))
    with pytest.raises(ValueError, match="required_safety_factor must be positive"):
        shaft_diameter_for_torque(
            torque=_q("500 N*m"), allowable_shear=_q("40 MPa"), required_safety_factor=0.0
        )


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


def test_rectangular_tube_enclosed_area_uses_the_median_line():
    # 100 x 60 mm box, 5 mm wall: median sides 95 x 55 -> A_m = 5225 mm^2.
    area = rectangular_tube_enclosed_area(
        width=_q("100 mm"), height=_q("60 mm"), wall_thickness=_q("5 mm")
    )
    assert area.to("mm**2").magnitude == pytest.approx(5225.0)


def test_rectangular_tube_torsional_stress_matches_bredt_worked_example():
    # 1 kN*m through the 100x60x5 mm box: A_m = 5225 mm^2, tau = T/(2*A_m*t)
    #   = 1e6 N*mm / (2*5225*5) = 19.139 MPa (uniform around the wall).
    tau = rectangular_tube_torsional_stress(
        torque=_q("1000 N*m"),
        width=_q("100 mm"),
        height=_q("60 mm"),
        wall_thickness=_q("5 mm"),
    )
    assert tau.to("MPa").magnitude == pytest.approx(19.139, rel=1e-3)


def test_rectangular_tube_twist_angle_matches_bredt_worked_example():
    # Same box over 1 m at G=79.3 GPa: median perimeter s = 2*(95+55) = 300 mm,
    #   theta = T*L*s/(4*A_m^2*G*t) = 6.927e-3 rad = 0.3969 deg.
    theta = rectangular_tube_twist_angle(
        torque=_q("1000 N*m"),
        length=_q("1 m"),
        width=_q("100 mm"),
        height=_q("60 mm"),
        wall_thickness=_q("5 mm"),
        shear_modulus=_q("79.3 GPa"),
    )
    assert theta.to("degree").magnitude == pytest.approx(0.3969, rel=1e-3)


def test_rectangular_tube_rejects_wall_without_a_cavity():
    with pytest.raises(ValueError, match="must be under half of both"):
        rectangular_tube_enclosed_area(
            width=_q("100 mm"), height=_q("60 mm"), wall_thickness=_q("30 mm")
        )
    with pytest.raises(ValueError, match="wall_thickness must be positive"):
        rectangular_tube_enclosed_area(
            width=_q("100 mm"), height=_q("60 mm"), wall_thickness=_q("0 mm")
        )
    with pytest.raises(ValueError, match="torque must be a"):
        rectangular_tube_torsional_stress(
            torque=_q("50 N"), width=_q("100 mm"), height=_q("60 mm"), wall_thickness=_q("5 mm")
        )


def test_thin_open_strip_torsion_constant_is_b_t_cubed_over_three():
    # b=100 mm, t=5 mm strip: J = b*t^3/3 = 100*125/3 = 4166.67 mm^4.
    j = thin_open_strip_torsion_constant(width=_q("100 mm"), thickness=_q("5 mm"))
    assert j.to("mm**4").magnitude == pytest.approx(4166.667, rel=1e-5)


def test_thin_open_strip_torsional_stress_matches_worked_example():
    # 50 N*m on the 100x5 strip: tau = 3T/(b*t^2) = 3*50000/(100*25) = 60 MPa,
    # and this equals the T*t/J identity.
    tau = thin_open_strip_torsional_stress(
        torque=_q("50 N*m"), width=_q("100 mm"), thickness=_q("5 mm")
    )
    assert tau.to("MPa").magnitude == pytest.approx(60.0, rel=1e-4)
    j = thin_open_strip_torsion_constant(width=_q("100 mm"), thickness=_q("5 mm"))
    identity = 50000.0 * 5.0 / j.to("mm**4").magnitude  # T*t/J in N/mm^2
    assert tau.to("MPa").magnitude == pytest.approx(identity, rel=1e-9)


def test_thin_open_strip_twist_matches_worked_example():
    # 50 N*m over 1 m at G=79.3 GPa: theta = T*L/(G*J) = 0.15130 rad = 8.669 deg.
    theta = thin_open_strip_twist_angle(
        torque=_q("50 N*m"),
        length=_q("1 m"),
        width=_q("100 mm"),
        thickness=_q("5 mm"),
        shear_modulus=_q("79.3 GPa"),
    )
    assert theta.to("degree").magnitude == pytest.approx(8.669, rel=1e-3)


def test_thin_open_strip_is_far_weaker_than_the_closed_box_tube():
    # An open slit section resists torsion far worse than the SAME wall closed:
    # for the same torque the open-strip stress dwarfs the closed box-tube stress.
    torque = _q("50 N*m")
    box = rectangular_tube_torsional_stress(
        torque=torque, width=_q("100 mm"), height=_q("60 mm"), wall_thickness=_q("5 mm")
    )
    # Unroll that box wall to a developed strip of width s = 2*(95+55) = 300 mm.
    strip = thin_open_strip_torsional_stress(
        torque=torque, width=_q("300 mm"), thickness=_q("5 mm")
    )
    assert strip.to("MPa").magnitude > 10 * box.to("MPa").magnitude


def test_thin_open_strip_rejects_thickness_over_width():
    with pytest.raises(ValueError, match="long dimension and must be at least"):
        thin_open_strip_torsion_constant(width=_q("5 mm"), thickness=_q("100 mm"))
    with pytest.raises(ValueError, match="must be positive"):
        thin_open_strip_torsion_constant(width=_q("0 mm"), thickness=_q("5 mm"))
    with pytest.raises(ValueError, match="torque must be a"):
        thin_open_strip_torsional_stress(
            torque=_q("50 N"), width=_q("100 mm"), thickness=_q("5 mm")
        )


def test_rectangular_bar_torsion_constant_interpolates_square_and_strip():
    import math

    # Square 20x20: J = a*b^3*(1/3 - 0.21*(1)*(1 - 1/12)) = 0.14083*a^4.
    square = rectangular_bar_torsion_constant(width=_q("20 mm"), thickness=_q("20 mm"))
    assert square.to("mm**4").magnitude == pytest.approx(0.140833 * 20**4, rel=1e-4)
    # The larger side is taken as 'a', so the order of the two arguments is
    # irrelevant.
    swapped = rectangular_bar_torsion_constant(width=_q("20 mm"), thickness=_q("40 mm"))
    upright = rectangular_bar_torsion_constant(width=_q("40 mm"), thickness=_q("20 mm"))
    assert swapped.to("mm**4").magnitude == pytest.approx(upright.to("mm**4").magnitude, rel=1e-12)
    # A slender bar approaches the thin open strip's b*t^3/3 (from just below).
    slender = rectangular_bar_torsion_constant(width=_q("500 mm"), thickness=_q("10 mm"))
    strip = thin_open_strip_torsion_constant(width=_q("500 mm"), thickness=_q("10 mm"))
    ratio = slender.to("mm**4").magnitude / strip.to("mm**4").magnitude
    assert 0.98 < ratio < 1.0
    # Twist theta = T*L/(G*J): a 40x20 bar, 100 N*m over 1 m at G = 80 GPa.
    theta = rectangular_bar_twist_angle(
        torque=_q("100 N*m"),
        length=_q("1 m"),
        width=_q("40 mm"),
        thickness=_q("20 mm"),
        shear_modulus=_q("80 GPa"),
    )
    a, b = 40.0, 20.0
    r = b / a
    j = a * b**3 * (1 / 3 - 0.21 * r * (1 - r**4 / 12))
    assert theta.to("degree").magnitude == pytest.approx(
        math.degrees(100e3 * 1000 / (80e3 * j)), rel=1e-12
    )
    with pytest.raises(ValueError, match="width and thickness must be positive"):
        rectangular_bar_torsion_constant(width=_q("0 mm"), thickness=_q("20 mm"))


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


def test_thin_wall_thickness_for_pressure_inverts_the_hoop_stress():
    # 2 MPa in a 100 mm-radius shell within a 120 MPa allowable needs
    #   t = p*r/sigma = 2*100/120 = 1.667 mm.
    t = thin_wall_thickness_for_pressure(
        pressure=_q("2 MPa"), radius=_q("100 mm"), allowable_stress=_q("120 MPa")
    )
    assert t.to("mm").magnitude == pytest.approx(1.6667, rel=1e-4)
    # A shell with exactly this wall is stressed to the allowable in hoop.
    hoop = thin_wall_cylinder(
        pressure=_q("2 MPa"), radius=_q("100 mm"), wall_thickness=t
    ).hoop_stress
    assert hoop.to("MPa").magnitude == pytest.approx(120.0, rel=1e-6)


def test_thin_wall_thickness_scales_with_the_margin():
    base = thin_wall_thickness_for_pressure(
        pressure=_q("2 MPa"), radius=_q("100 mm"), allowable_stress=_q("120 MPa")
    )
    with_sf = thin_wall_thickness_for_pressure(
        pressure=_q("2 MPa"),
        radius=_q("100 mm"),
        allowable_stress=_q("120 MPa"),
        required_safety_factor=1.5,
    )
    assert with_sf.to("mm").magnitude == pytest.approx(1.5 * base.to("mm").magnitude, rel=1e-9)


def test_thin_wall_thickness_rejects_bad_inputs():
    with pytest.raises(ValueError, match="pressure must be a"):
        thin_wall_thickness_for_pressure(
            pressure=_q("2 N"), radius=_q("100 mm"), allowable_stress=_q("120 MPa")
        )
    with pytest.raises(ValueError, match="allowable_stress must be positive"):
        thin_wall_thickness_for_pressure(
            pressure=_q("2 MPa"), radius=_q("100 mm"), allowable_stress=_q("0 MPa")
        )
    with pytest.raises(ValueError, match="required_safety_factor must be positive"):
        thin_wall_thickness_for_pressure(
            pressure=_q("2 MPa"),
            radius=_q("100 mm"),
            allowable_stress=_q("120 MPa"),
            required_safety_factor=0.0,
        )


def test_thick_wall_cylinder_matches_worked_example():
    # A O50 bore hydraulic barrel with a 10 mm wall (ri = 25, ro = 35) at
    # 60 MPa: bore hoop = p*(ro^2+ri^2)/(ro^2-ri^2) = 60*1850/600 = 185 MPa on
    # a radial -60, so the bore Tresca intensity is 245 MPa; closed-ends
    # longitudinal = 60*625/600 = 62.5 MPa.
    result = thick_wall_cylinder(
        pressure=_q("60 MPa"), radius=_q("25 mm"), wall_thickness=_q("10 mm")
    )
    assert result.hoop_stress.to("MPa").magnitude == pytest.approx(185.0, rel=1e-6)
    assert result.radial_stress.to("MPa").magnitude == pytest.approx(-60.0, rel=1e-6)
    assert result.longitudinal_stress.to("MPa").magnitude == pytest.approx(62.5, rel=1e-6)
    assert result.bore_tresca_stress.to("MPa").magnitude == pytest.approx(245.0, rel=1e-6)
    assert result.yield_safety_factor(_q("417 MPa")) == pytest.approx(417 / 245, rel=1e-6)


def test_thick_wall_bore_von_mises_sits_below_the_tresca_intensity():
    # The bore triad (185, -60, 62.5): von Mises = sqrt(1/2*[(sig1-sig2)^2 +
    # (sig2-sig3)^2 + (sig3-sig1)^2]) = 212.18 MPa, a few percent under the 245
    # Tresca intensity -- the ductile criterion is less conservative but still safe.
    result = thick_wall_cylinder(
        pressure=_q("60 MPa"), radius=_q("25 mm"), wall_thickness=_q("10 mm")
    )
    vm = result.bore_von_mises_stress.to("MPa").magnitude
    assert vm == pytest.approx(212.176, rel=1e-4)
    assert vm < result.bore_tresca_stress.to("MPa").magnitude


def test_asme_cylinder_thickness_matches_the_code_form():
    kw = {"pressure": _q("2 MPa"), "radius": _q("500 mm"), "allowable_stress": _q("138 MPa")}
    # ASME UG-27: t = P*R/(S*E - 0.6*P). Full radiography (E=1) sits just above the
    # bare membrane P*R/S because of the -0.6*P term: 2*500/(138-1.2) = 7.31 mm.
    full = asme_cylinder_thickness(**kw)
    assert full.to("mm").magnitude == pytest.approx(2 * 500 / (138 - 0.6 * 2), rel=1e-9)
    assert full.to("mm").magnitude > 2 * 500 / 138  # thicker than the membrane form
    # A spot-radiographed weld (E=0.85) derates the allowable and needs more wall.
    spot = asme_cylinder_thickness(joint_efficiency=0.85, **kw)
    assert spot.to("mm").magnitude == pytest.approx(8.6133, rel=1e-4)
    assert spot.to("mm").magnitude > full.to("mm").magnitude


def test_asme_cylinder_thickness_rejects_overpressure_and_bad_efficiency():
    with pytest.raises(ValueError, match="joint_efficiency must lie in"):
        asme_cylinder_thickness(
            pressure=_q("2 MPa"),
            radius=_q("500 mm"),
            allowable_stress=_q("138 MPa"),
            joint_efficiency=1.5,
        )
    # When S*E does not clear 0.6*P the thin-wall form has no solution.
    with pytest.raises(ValueError, match="too high for a thin-wall design"):
        asme_cylinder_thickness(
            pressure=_q("300 MPa"), radius=_q("500 mm"), allowable_stress=_q("138 MPa")
        )


def test_thick_wall_open_ended_drops_the_longitudinal_stress():
    kw = {"pressure": _q("60 MPa"), "radius": _q("25 mm"), "wall_thickness": _q("10 mm")}
    closed = thick_wall_cylinder(**kw)
    openc = thick_wall_cylinder(closed_ends=False, **kw)
    # An open-ended cylinder carries no axial pressure load: sigma_long = 0.
    assert openc.longitudinal_stress.to("MPa").magnitude == pytest.approx(0.0, abs=1e-9)
    # Hoop, radial, and the governing Tresca intensity are unchanged...
    assert openc.hoop_stress.to("MPa").magnitude == pytest.approx(
        closed.hoop_stress.to("MPa").magnitude, rel=1e-12
    )
    assert openc.bore_tresca_stress.to("MPa").magnitude == pytest.approx(245.0, rel=1e-9)
    # ...but the von Mises reading rises (the intermediate principal stress is gone):
    # sqrt(1/2*[245^2 + 60^2 + 185^2]) = 221.19 MPa > the 212.18 closed-ends value.
    assert openc.bore_von_mises_stress.to("MPa").magnitude == pytest.approx(221.19, rel=1e-4)
    assert (
        openc.bore_von_mises_stress.to("MPa").magnitude
        > closed.bore_von_mises_stress.to("MPa").magnitude
    )


def test_thick_wall_hoop_drops_by_exactly_the_pressure_across_the_wall():
    # Lame identity: the OD hoop stress is 2*sigma_long, and the bore hoop
    # exceeds it by EXACTLY p — the pressure is carried by the hoop gradient.
    result = thick_wall_cylinder(
        pressure=_q("60 MPa"), radius=_q("25 mm"), wall_thickness=_q("10 mm")
    )
    od_hoop = 2 * result.longitudinal_stress.to("MPa").magnitude
    assert result.hoop_stress.to("MPa").magnitude - od_hoop == pytest.approx(60.0, rel=1e-12)


def test_thick_wall_recovers_the_thin_wall_membrane_and_always_exceeds_it():
    # At r/t = 100 the exact bore hoop sits within ~1% of p*r/t, and it is
    # ALWAYS above it — the thin-wall screen under-reports the bore, which is
    # the direction that matters.
    kw = {"pressure": _q("2 MPa"), "radius": _q("500 mm"), "wall_thickness": _q("5 mm")}
    thick = thick_wall_cylinder(**kw)
    thin = thin_wall_cylinder(**kw)
    thick_hoop = thick.hoop_stress.to("MPa").magnitude
    thin_hoop = thin.hoop_stress.to("MPa").magnitude
    assert thick_hoop == pytest.approx(thin_hoop, rel=2e-2)
    assert thick_hoop > thin_hoop
    stubby = thick_wall_cylinder(
        pressure=_q("2 MPa"), radius=_q("25 mm"), wall_thickness=_q("10 mm")
    )
    assert stubby.hoop_stress.to("MPa").magnitude > 2 * 25 / 10  # thin-wall reading


def test_thick_wall_cylinder_rejects_bad_inputs():
    with pytest.raises(ValueError, match="must be positive"):
        thick_wall_cylinder(pressure=_q("2 MPa"), radius=_q("25 mm"), wall_thickness=_q("0 mm"))
    with pytest.raises(ValueError, match="pressure must be a"):
        thick_wall_cylinder(pressure=_q("2 N"), radius=_q("25 mm"), wall_thickness=_q("5 mm"))


def test_thin_wall_sphere_is_half_the_cylinder_hoop():
    # 2 MPa, 100 mm radius, 5 mm wall: sphere sigma = p*r/2t = 20 MPa, which is
    # half the cylinder hoop (40 MPa) for the same geometry.
    sphere = thin_wall_sphere_stress(
        pressure=_q("2 MPa"), radius=_q("100 mm"), wall_thickness=_q("5 mm")
    )
    assert sphere.to("MPa").magnitude == pytest.approx(20.0, rel=1e-6)
    cyl = thin_wall_cylinder(pressure=_q("2 MPa"), radius=_q("100 mm"), wall_thickness=_q("5 mm"))
    assert sphere.to("MPa").magnitude == pytest.approx(cyl.hoop_stress.to("MPa").magnitude / 2)


def test_thick_wall_sphere_matches_worked_example():
    # Same ri=25, ro=35 bore at 60 MPa: sigma_hoop = p*(2*ri^3+ro^3)/(2*(ro^3-ri^3))
    #   = 60*(2*15625+42875)/(2*27250) = 60*74125/54500 = 81.606 MPa on a radial
    # -60, so the bore Tresca intensity is 3*p*ro^3/(2*(ro^3-ri^3)) = 141.606 MPa.
    result = thick_wall_sphere(
        pressure=_q("60 MPa"), radius=_q("25 mm"), wall_thickness=_q("10 mm")
    )
    assert result.hoop_stress.to("MPa").magnitude == pytest.approx(81.606, rel=1e-4)
    assert result.radial_stress.to("MPa").magnitude == pytest.approx(-60.0, rel=1e-6)
    assert result.bore_tresca_stress.to("MPa").magnitude == pytest.approx(141.606, rel=1e-4)
    assert result.yield_safety_factor(_q("417 MPa")) == pytest.approx(417 / 141.606, rel=1e-4)
    # A sphere works far less hard than a cylinder of the same bore and wall.
    cyl = thick_wall_cylinder(pressure=_q("60 MPa"), radius=_q("25 mm"), wall_thickness=_q("10 mm"))
    assert (
        result.bore_tresca_stress.to("MPa").magnitude < cyl.bore_tresca_stress.to("MPa").magnitude
    )


def test_thick_wall_sphere_recovers_the_membrane_and_always_exceeds_it():
    # At r/t = 100 the exact bore hoop sits within ~1.5% of the p*r/(2t) membrane
    # and is ALWAYS above it — the thin-wall sphere screen under-reports the bore.
    kw = {"pressure": _q("2 MPa"), "radius": _q("500 mm"), "wall_thickness": _q("5 mm")}
    thick = thick_wall_sphere(**kw)
    membrane = thin_wall_sphere_stress(**kw)
    thick_hoop = thick.hoop_stress.to("MPa").magnitude
    mem = membrane.to("MPa").magnitude
    assert thick_hoop == pytest.approx(mem, rel=2e-2)
    assert thick_hoop > mem


def test_thick_wall_sphere_rejects_bad_inputs():
    with pytest.raises(ValueError, match="must be positive"):
        thick_wall_sphere(pressure=_q("2 MPa"), radius=_q("25 mm"), wall_thickness=_q("0 mm"))
    with pytest.raises(ValueError, match="pressure must be a"):
        thick_wall_sphere(pressure=_q("2 N"), radius=_q("25 mm"), wall_thickness=_q("5 mm"))


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


def test_interference_for_contact_pressure_inverts_the_fit():
    # The same geometry: 60 MPa of contact needs the 0.02 mm radial interference.
    delta = interference_for_contact_pressure(
        contact_pressure=_q("60 MPa"),
        interface_diameter=_q("50 mm"),
        hub_outer_diameter=_q("100 mm"),
        hub_modulus=_q("200 GPa"),
        hub_poisson=0.3,
        shaft_modulus=_q("200 GPa"),
        shaft_poisson=0.3,
    )
    assert delta.to("mm").magnitude == pytest.approx(0.02, rel=1e-6)


def test_interference_pressure_round_trips_through_the_fit():
    # Invert a target pressure to an interference, feed it back to interference_fit,
    # and recover the pressure exactly -- including a hollow shaft.
    kw = {
        "interface_diameter": _q("50 mm"),
        "hub_outer_diameter": _q("100 mm"),
        "hub_modulus": _q("200 GPa"),
        "hub_poisson": 0.3,
        "shaft_modulus": _q("120 GPa"),
        "shaft_poisson": 0.33,
        "shaft_bore_diameter": _q("20 mm"),
    }
    delta = interference_for_contact_pressure(contact_pressure=_q("45 MPa"), **kw)
    back = interference_fit(radial_interference=delta, **kw)
    assert back.contact_pressure.to("MPa").magnitude == pytest.approx(45.0, rel=1e-9)


def test_interference_for_contact_pressure_rejects_bad_inputs():
    with pytest.raises(ValueError, match="contact_pressure must be a"):
        interference_for_contact_pressure(
            contact_pressure=_q("60 N"),
            interface_diameter=_q("50 mm"),
            hub_outer_diameter=_q("100 mm"),
            hub_modulus=_q("200 GPa"),
            hub_poisson=0.3,
            shaft_modulus=_q("200 GPa"),
            shaft_poisson=0.3,
        )
    with pytest.raises(ValueError, match="need hub_outer_diameter >"):
        interference_for_contact_pressure(
            contact_pressure=_q("60 MPa"),
            interface_diameter=_q("100 mm"),  # not smaller than the hub OD
            hub_outer_diameter=_q("100 mm"),
            hub_modulus=_q("200 GPa"),
            hub_poisson=0.3,
            shaft_modulus=_q("200 GPa"),
            shaft_poisson=0.3,
        )


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


def test_hertz_effective_modulus_matches_hand_calc():
    # Two steel bodies (E=200 GPa, nu=0.3): 1/E* = 2*(1-0.09)/200000 -> E* = 109890 MPa.
    e_star = hertz_effective_modulus(
        modulus1=_q("200 GPa"), poisson1=0.3, modulus2=_q("200 GPa"), poisson2=0.3
    )
    assert e_star.to("MPa").magnitude == pytest.approx(109890.1, rel=1e-4)
    # A steel body on a rigid (infinitely stiff) one is stiffer than steel-on-steel.
    on_rigid = hertz_effective_modulus(
        modulus1=_q("200 GPa"), poisson1=0.3, modulus2=_q("1e9 GPa"), poisson2=0.3
    )
    assert on_rigid.to("MPa").magnitude > e_star.to("MPa").magnitude
    with pytest.raises(ValueError, match="modulus1 must be a"):
        hertz_effective_modulus(
            modulus1=_q("200 mm"), poisson1=0.3, modulus2=_q("200 GPa"), poisson2=0.3
        )


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
    # The subsurface shear (0.31*p_max = 653 MPa) is what actually governs yield.
    assert c.max_subsurface_shear_stress.to("MPa").magnitude == pytest.approx(
        0.31 * 2106.5, rel=1e-4
    )
    # Screened on the Tresca shear yield Sy/2, the margin is (Sy/2)/(0.31*p_max) =
    # SF 1.53 -- always 0.5/0.31 = 1.61x the crude surface ratio, because a contact
    # sustains p_max up to ~1.6*Sy before it yields below the surface.
    assert c.subsurface_shear_safety_factor(_q("2000 MPa")) == pytest.approx(
        1000 / (0.31 * 2106.5), rel=1e-4
    )
    assert c.subsurface_shear_safety_factor(_q("2000 MPa")) == pytest.approx(
        (0.5 / 0.31) * c.surface_safety_factor(_q("2000 MPa")), rel=1e-6
    )
    # The mean pressure over the circular patch is exactly 2/3 of the peak.
    assert c.mean_contact_pressure.to("MPa").magnitude == pytest.approx(
        (2 / 3) * c.max_contact_pressure.to("MPa").magnitude, rel=1e-12
    )


def test_hertz_line_contact_mean_pressure_is_pi_over_four_of_the_peak():
    from math import pi

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
    # A line contact's elliptical pressure profile makes the mean pi/4 of the peak,
    # fuller than the point contact's 2/3.
    assert c.mean_contact_pressure.to("MPa").magnitude == pytest.approx(
        (pi / 4) * c.max_contact_pressure.to("MPa").magnitude, rel=1e-12
    )
    assert c.mean_contact_pressure.to("MPa").magnitude / c.max_contact_pressure.to(
        "MPa"
    ).magnitude == pytest.approx(0.7854, rel=1e-3)


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
    # Line contact peaks lower below the surface (0.30*p_max) and yields near
    # p_max = 1.67*Sy: the subsurface SF is 0.5/0.30 = 1.67x the surface ratio.
    assert c.max_subsurface_shear_stress.to("MPa").magnitude == pytest.approx(
        0.30 * 374.05, rel=1e-4
    )
    assert c.subsurface_shear_safety_factor(_q("400 MPa")) == pytest.approx(
        200 / (0.30 * 374.05), rel=1e-4
    )


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


def test_required_axial_area_inverts_the_direct_stress_check():
    # 100 kN of tension within a 165 MPa allowable needs A = F/sigma = 606.06 mm^2.
    a = required_axial_area(axial_load=_q("100 kN"), allowable_stress=_q("165 MPa"))
    assert a.to("mm**2").magnitude == pytest.approx(606.06, rel=1e-4)
    # A member of exactly this area is stressed to the allowable.
    sigma = axial_stress(force=_q("100 kN"), area=a)
    assert sigma.to("MPa").magnitude == pytest.approx(165.0, rel=1e-6)


def test_required_axial_area_ignores_load_sign_and_scales_with_margin():
    # Compression sizes the same as tension of equal magnitude (area, not sign).
    tension = required_axial_area(axial_load=_q("100 kN"), allowable_stress=_q("165 MPa"))
    compression = required_axial_area(axial_load=_q("-100 kN"), allowable_stress=_q("165 MPa"))
    assert compression.to("mm**2").magnitude == pytest.approx(
        tension.to("mm**2").magnitude, rel=1e-9
    )
    # Area scales linearly with the required margin.
    with_sf = required_axial_area(
        axial_load=_q("100 kN"), allowable_stress=_q("165 MPa"), required_safety_factor=1.67
    )
    assert with_sf.to("mm**2").magnitude == pytest.approx(
        1.67 * tension.to("mm**2").magnitude, rel=1e-9
    )


def test_required_axial_area_rejects_bad_inputs():
    with pytest.raises(ValueError, match="axial_load must be a"):
        required_axial_area(axial_load=_q("100 mm"), allowable_stress=_q("165 MPa"))
    with pytest.raises(ValueError, match="allowable_stress must be positive"):
        required_axial_area(axial_load=_q("100 kN"), allowable_stress=_q("0 MPa"))
    with pytest.raises(ValueError, match="required_safety_factor must be positive"):
        required_axial_area(
            axial_load=_q("100 kN"), allowable_stress=_q("165 MPa"), required_safety_factor=0.0
        )


def test_cyclic_stress_components_from_max_and_min():
    # sigma_max=200, sigma_min=50 MPa: amplitude 75, mean 125, R = 50/200 = 0.25.
    c = cyclic_stress_components(max_stress=_q("200 MPa"), min_stress=_q("50 MPa"))
    assert c.alternating_stress.to("MPa").magnitude == pytest.approx(75.0, rel=1e-9)
    assert c.mean_stress.to("MPa").magnitude == pytest.approx(125.0, rel=1e-9)
    assert c.stress_ratio == pytest.approx(0.25, rel=1e-9)


def test_cyclic_stress_fully_reversed_and_zero_to_tension():
    # Fully reversed: R = -1, zero mean, amplitude = the peak.
    rev = cyclic_stress_components(max_stress=_q("120 MPa"), min_stress=_q("-120 MPa"))
    assert rev.mean_stress.to("MPa").magnitude == pytest.approx(0.0, abs=1e-9)
    assert rev.alternating_stress.to("MPa").magnitude == pytest.approx(120.0, rel=1e-9)
    assert rev.stress_ratio == pytest.approx(-1.0, rel=1e-9)
    # Zero-to-tension: R = 0, amplitude = mean = half the peak.
    zt = cyclic_stress_components(max_stress=_q("180 MPa"), min_stress=_q("0 MPa"))
    assert zt.stress_ratio == pytest.approx(0.0, abs=1e-12)
    assert zt.alternating_stress.to("MPa").magnitude == pytest.approx(90.0, rel=1e-9)
    assert zt.mean_stress.to("MPa").magnitude == pytest.approx(90.0, rel=1e-9)


def test_cyclic_stress_feeds_the_goodman_criterion():
    # The converter output drops straight into the Goodman screen: sigma_a=75,
    # sigma_m=125; Se=200, Su=400 -> 1/n = 75/200 + 125/400 = 0.6875 -> n = 1.4545.
    c = cyclic_stress_components(max_stress=_q("200 MPa"), min_stress=_q("50 MPa"))
    n = goodman_safety_factor(
        alternating_stress=c.alternating_stress,
        mean_stress=c.mean_stress,
        endurance_limit=_q("200 MPa"),
        ultimate_strength=_q("400 MPa"),
    )
    assert n == pytest.approx(1.0 / (75 / 200 + 125 / 400), rel=1e-9)


def test_cyclic_stress_rejects_non_cycle():
    with pytest.raises(ValueError, match="must exceed min_stress"):
        cyclic_stress_components(max_stress=_q("50 MPa"), min_stress=_q("50 MPa"))
    with pytest.raises(ValueError, match="max_stress must be a"):
        cyclic_stress_components(max_stress=_q("50 N"), min_stress=_q("10 MPa"))


def test_fatigue_notch_factor_bridges_kt_and_sensitivity():
    # Kf = 1 + q*(Kt - 1): Kt=2.5, q=0.8 -> 1 + 0.8*1.5 = 2.2.
    assert fatigue_notch_factor(kt=2.5, notch_sensitivity=0.8) == pytest.approx(2.2, rel=1e-9)
    # q=0 (notch-insensitive) -> Kf = 1; q=1 (fully sensitive) -> Kf = Kt.
    assert fatigue_notch_factor(kt=2.5, notch_sensitivity=0.0) == pytest.approx(1.0)
    assert fatigue_notch_factor(kt=2.5, notch_sensitivity=1.0) == pytest.approx(2.5)


def test_fatigue_notch_factor_amplifies_the_alternating_stress():
    # Kf multiplies the alternating stress before a Goodman screen: a 60 MPa
    # amplitude at Kf=2.2 becomes 132 MPa, cutting the safety factor.
    kf = fatigue_notch_factor(kt=2.5, notch_sensitivity=0.8)
    plain = goodman_safety_factor(
        alternating_stress=_q("60 MPa"),
        mean_stress=_q("40 MPa"),
        endurance_limit=_q("250 MPa"),
        ultimate_strength=_q("500 MPa"),
    )
    notched = goodman_safety_factor(
        alternating_stress=_q(f"{60 * kf} MPa"),
        mean_stress=_q("40 MPa"),
        endurance_limit=_q("250 MPa"),
        ultimate_strength=_q("500 MPa"),
    )
    assert notched < plain


def test_fatigue_notch_factor_rejects_bad_inputs():
    with pytest.raises(ValueError, match="kt must be at least 1"):
        fatigue_notch_factor(kt=0.5, notch_sensitivity=0.8)
    with pytest.raises(ValueError, match=r"notch_sensitivity must lie in \[0, 1\]"):
        fatigue_notch_factor(kt=2.5, notch_sensitivity=1.5)


def test_estimated_endurance_limit_is_half_ultimate_capped():
    # Steel rotating-beam estimate: Se' = 0.5*Su below the cap.
    se = estimated_endurance_limit(ultimate_strength=_q("400 MPa"))
    assert se.to("MPa").magnitude == pytest.approx(200.0, rel=1e-9)
    # High-strength steel: capped at 700 MPa rather than 0.5*Su.
    capped = estimated_endurance_limit(ultimate_strength=_q("1600 MPa"))
    assert capped.to("MPa").magnitude == pytest.approx(700.0, rel=1e-9)
    # Just below the cap boundary (Su = 1400 -> 700) it is still 0.5*Su.
    boundary = estimated_endurance_limit(ultimate_strength=_q("1400 MPa"))
    assert boundary.to("MPa").magnitude == pytest.approx(700.0, rel=1e-9)


def test_estimated_endurance_limit_feeds_a_goodman_screen():
    # The estimate drops straight into the criteria when no measured value exists.
    se = estimated_endurance_limit(ultimate_strength=_q("500 MPa"))  # -> 250 MPa
    n = goodman_safety_factor(
        alternating_stress=_q("60 MPa"),
        mean_stress=_q("40 MPa"),
        endurance_limit=se,
        ultimate_strength=_q("500 MPa"),
    )
    assert n == pytest.approx(1.0 / (60 / 250 + 40 / 500), rel=1e-9)


def test_estimated_endurance_limit_rejects_bad_inputs():
    with pytest.raises(ValueError, match="ultimate_strength must be a"):
        estimated_endurance_limit(ultimate_strength=_q("400 N"))
    with pytest.raises(ValueError, match="ultimate_strength must be positive"):
        estimated_endurance_limit(ultimate_strength=_q("0 MPa"))


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


def test_soderberg_safety_factor_worked_example():
    # sigma_a=100, sigma_m=50 MPa; Se=200, Sy=300 MPa:
    #   1/n = 100/200 + 50/300 = 0.5 + 0.16667 = 0.66667 -> n = 1.5.
    n = soderberg_safety_factor(
        alternating_stress=_q("100 MPa"),
        mean_stress=_q("50 MPa"),
        endurance_limit=_q("200 MPa"),
        yield_strength=_q("300 MPa"),
    )
    assert n == pytest.approx(1.5, rel=1e-6)


def test_soderberg_is_more_conservative_than_goodman():
    # For the same mean stress, drawing to yield (< ultimate) gives a smaller n.
    common = {
        "alternating_stress": _q("100 MPa"),
        "mean_stress": _q("120 MPa"),
        "endurance_limit": _q("200 MPa"),
    }
    good = goodman_safety_factor(ultimate_strength=_q("500 MPa"), **common)
    sod = soderberg_safety_factor(yield_strength=_q("350 MPa"), **common)
    assert sod < good


def test_soderberg_fully_reversed_matches_goodman_endurance_ratio():
    # At zero mean stress both criteria reduce to n = Se / sigma_a.
    kw = {
        "alternating_stress": _q("80 MPa"),
        "mean_stress": _q("0 MPa"),
        "endurance_limit": _q("200 MPa"),
    }
    sod = soderberg_safety_factor(yield_strength=_q("300 MPa"), **kw)
    good = goodman_safety_factor(ultimate_strength=_q("400 MPa"), **kw)
    assert sod == pytest.approx(200 / 80, rel=1e-9)
    assert sod == pytest.approx(good, rel=1e-9)


def test_soderberg_scorecard_honours_no_silent_green():
    from anvilate.scorecard import CheckStatus

    evaluated = soderberg_scorecard(
        "fatigue",
        alternating_stress=_q("50 MPa"),
        mean_stress=_q("20 MPa"),
        endurance_limit=_q("180 MPa"),
        yield_strength=_q("250 MPa"),
        required=1.5,
    )
    assert evaluated.status in (CheckStatus.PASS, CheckStatus.FAIL)
    # No listed endurance limit -> NOT_EVALUATED, never a silent pass.
    gap = soderberg_scorecard(
        "fatigue",
        alternating_stress=_q("50 MPa"),
        mean_stress=_q("20 MPa"),
        endurance_limit=None,
        yield_strength=_q("250 MPa"),
        required=1.5,
    )
    assert gap.status is CheckStatus.NOT_EVALUATED
    assert not gap.passed


def test_soderberg_rejects_negative_amplitude():
    with pytest.raises(ValueError, match="amplitude"):
        soderberg_safety_factor(
            alternating_stress=_q("-10 MPa"),
            mean_stress=_q("0 MPa"),
            endurance_limit=_q("200 MPa"),
            yield_strength=_q("300 MPa"),
        )


def test_gerber_safety_factor_worked_example():
    # sigma_a=100, sigma_m=50 MPa; Se=200, Su=400 MPa. a=0.5, b=0.125:
    #   n = (a/2b^2)[-1 + sqrt(1 + (2b/a)^2)] = 16[-1 + sqrt(1.25)] = 1.8885.
    n = gerber_safety_factor(
        alternating_stress=_q("100 MPa"),
        mean_stress=_q("50 MPa"),
        endurance_limit=_q("200 MPa"),
        ultimate_strength=_q("400 MPa"),
    )
    assert n == pytest.approx(1.8885, rel=1e-4)


def test_gerber_sits_above_goodman_for_a_tensile_mean():
    # The parabola bulges above the Goodman line -> the same numbers give a larger
    # (less conservative) factor than Goodman's n = 1.6.
    common = {
        "alternating_stress": _q("100 MPa"),
        "mean_stress": _q("50 MPa"),
        "endurance_limit": _q("200 MPa"),
        "ultimate_strength": _q("400 MPa"),
    }
    assert gerber_safety_factor(**common) > goodman_safety_factor(**common)


def test_gerber_pure_mean_returns_the_static_ultimate_ratio():
    # sigma_a = 0: the parabola meets the mean axis at S_u -> n = Su/sigma_m.
    n = gerber_safety_factor(
        alternating_stress=_q("0 MPa"),
        mean_stress=_q("100 MPa"),
        endurance_limit=_q("200 MPa"),
        ultimate_strength=_q("400 MPa"),
    )
    assert n == pytest.approx(4.0, rel=1e-9)


def test_gerber_compressive_mean_falls_back_to_endurance_ratio():
    # A compressive mean earns no credit: n = Se / sigma_a.
    n = gerber_safety_factor(
        alternating_stress=_q("80 MPa"),
        mean_stress=_q("-50 MPa"),
        endurance_limit=_q("200 MPa"),
        ultimate_strength=_q("400 MPa"),
    )
    assert n == pytest.approx(200 / 80, rel=1e-9)


def test_gerber_scorecard_honours_no_silent_green():
    from anvilate.scorecard import CheckStatus

    gap = gerber_scorecard(
        "fatigue",
        alternating_stress=_q("50 MPa"),
        mean_stress=_q("20 MPa"),
        endurance_limit=None,
        ultimate_strength=_q("400 MPa"),
        required=1.5,
    )
    assert gap.status is CheckStatus.NOT_EVALUATED
    assert not gap.passed


def test_basquin_cycles_to_failure_inverts_the_stress_for_life():
    # S-N line a=1200 MPa, b=-0.1. The stress at 1e6 cycles is a*N^b =
    # 1200*1e6^-0.1 = 1200*0.2512 = 301.4 MPa, and that stress feeds back to 1e6.
    stress = basquin_stress_for_life(life_cycles=1e6, coefficient=_q("1200 MPa"), exponent=-0.1)
    assert stress.to("MPa").magnitude == pytest.approx(1200 * 1e6**-0.1, rel=1e-9)
    life = basquin_cycles_to_failure(
        stress_amplitude=stress, coefficient=_q("1200 MPa"), exponent=-0.1
    )
    assert life == pytest.approx(1e6, rel=1e-9)
    # A higher stress amplitude spends the fatigue life faster (fewer cycles).
    hotter = basquin_cycles_to_failure(
        stress_amplitude=_q("400 MPa"), coefficient=_q("1200 MPa"), exponent=-0.1
    )
    assert hotter < life


def test_basquin_feeds_the_miner_spectrum():
    # Two amplitudes on the same S-N line give the per-level lives Miner consumes.
    n1 = basquin_cycles_to_failure(
        stress_amplitude=_q("350 MPa"), coefficient=_q("1200 MPa"), exponent=-0.1
    )
    n2 = basquin_cycles_to_failure(
        stress_amplitude=_q("300 MPa"), coefficient=_q("1200 MPa"), exponent=-0.1
    )
    damage = miner_cumulative_damage(applied_cycles=[1e4, 2e4], cycles_to_failure=[n1, n2])
    assert damage == pytest.approx(1e4 / n1 + 2e4 / n2, rel=1e-12)
    assert 0 < damage < 1  # the block survives one pass


def test_basquin_rejects_bad_inputs():
    with pytest.raises(ValueError, match="exponent .* must be negative"):
        basquin_cycles_to_failure(
            stress_amplitude=_q("300 MPa"), coefficient=_q("1200 MPa"), exponent=0.1
        )
    with pytest.raises(ValueError, match="stress_amplitude must be positive"):
        basquin_cycles_to_failure(
            stress_amplitude=_q("0 MPa"), coefficient=_q("1200 MPa"), exponent=-0.1
        )
    with pytest.raises(ValueError, match="life_cycles must be positive"):
        basquin_stress_for_life(life_cycles=0.0, coefficient=_q("1200 MPa"), exponent=-0.1)
    with pytest.raises(ValueError, match="coefficient must be a"):
        basquin_stress_for_life(life_cycles=1e6, coefficient=_q("1200 mm"), exponent=-0.1)


def test_miner_cumulative_damage_sums_the_life_fractions():
    # Two-level spectrum: 20,000 cycles where N=100,000 (D=0.2) plus 30,000 where
    # N=200,000 (D=0.15) -> total damage 0.35 of the fatigue life.
    d = miner_cumulative_damage(
        applied_cycles=[20_000, 30_000],
        cycles_to_failure=[100_000, 200_000],
    )
    assert d == pytest.approx(0.35, rel=1e-12)
    # A part reaches D=1.0 exactly when a single level runs to its S-N life.
    exhausted = miner_cumulative_damage(applied_cycles=[100_000], cycles_to_failure=[100_000])
    assert exhausted == pytest.approx(1.0, rel=1e-12)


def test_miner_spectrum_repeats_to_failure_is_one_over_damage():
    kw = {"applied_cycles": [20_000, 30_000], "cycles_to_failure": [100_000, 200_000]}
    repeats = miner_spectrum_repeats_to_failure(**kw)
    # One pass does D=0.35, so the spectrum survives 1/0.35 = 2.857 repeats.
    assert repeats == pytest.approx(1 / 0.35, rel=1e-12)
    # A spectrum that applies no cycles never fails -> infinite repeats.
    assert miner_spectrum_repeats_to_failure(
        applied_cycles=[0.0, 0.0], cycles_to_failure=[100_000, 200_000]
    ) == float("inf")


def test_miner_rejects_bad_spectra():
    with pytest.raises(ValueError, match="same length"):
        miner_cumulative_damage(applied_cycles=[1.0, 2.0], cycles_to_failure=[100.0])
    with pytest.raises(ValueError, match="at least one stress level"):
        miner_cumulative_damage(applied_cycles=[], cycles_to_failure=[])
    with pytest.raises(ValueError, match="applied_cycles must be non-negative"):
        miner_cumulative_damage(applied_cycles=[-1.0], cycles_to_failure=[100.0])
    with pytest.raises(ValueError, match="cycles_to_failure must be positive"):
        miner_cumulative_damage(applied_cycles=[1.0], cycles_to_failure=[0.0])


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


def test_free_thermal_expansion_is_signed_and_recovers_the_constrained_stress():
    # A 1 m steel bar heated 50 K grows alpha*L*dT = 12e-6*1000*50 = 0.6 mm;
    # cooled the same 50 K it SHRINKS 0.6 mm (the sign a clearance check
    # needs). E times the denied strain delta/L is exactly the constrained
    # thermal stress: 200000 * 0.6/1000 = 120 MPa.
    kw = {
        "length": _q("1 m"),
        "thermal_expansion_coefficient": _q("12e-6 / K"),
    }
    grow = free_thermal_expansion(temperature_change=_q("50 K"), **kw)
    shrink = free_thermal_expansion(temperature_change=_q("-50 K"), **kw)
    assert grow.to("mm").magnitude == pytest.approx(0.6, rel=1e-9)
    assert shrink.to("mm").magnitude == pytest.approx(-0.6, rel=1e-9)
    sigma = constrained_thermal_stress(
        elastic_modulus=_q("200 GPa"),
        thermal_expansion_coefficient=_q("12e-6 / K"),
        temperature_change=_q("50 K"),
    )
    denied_strain = grow.to("mm").magnitude / 1000.0
    assert sigma.to("MPa").magnitude == pytest.approx(200000 * denied_strain, rel=1e-9)


def test_shrink_fit_assembly_temperature_inverts_the_bore_growth():
    # A O40 hub with 59 um of interference plus a 25 um slip allowance needs
    # dT = (0.059 + 0.025)/(11.7e-6 * 40) = 179.5 K above the shaft. Heating
    # the bore by exactly that dT must grow it by exactly delta + c.
    dt = shrink_fit_assembly_temperature(
        interface_diameter=_q("40 mm"),
        diametral_interference=_q("0.059 mm"),
        assembly_clearance=_q("0.025 mm"),
        thermal_expansion_coefficient=_q("11.7e-6 / K"),
    )
    assert dt.to("K").magnitude == pytest.approx(179.49, rel=1e-3)
    growth = free_thermal_expansion(
        length=_q("40 mm"),
        thermal_expansion_coefficient=_q("11.7e-6 / K"),
        temperature_change=dt,
    )
    assert growth.to("mm").magnitude == pytest.approx(0.084, rel=1e-12)


def test_thermal_expansion_rejects_bad_inputs():
    with pytest.raises(ValueError, match="length must be positive"):
        free_thermal_expansion(
            length=_q("0 mm"),
            thermal_expansion_coefficient=_q("12e-6 / K"),
            temperature_change=_q("50 K"),
        )
    with pytest.raises(ValueError, match="diametral_interference must be positive"):
        shrink_fit_assembly_temperature(
            interface_diameter=_q("40 mm"),
            diametral_interference=_q("0 mm"),
            assembly_clearance=_q("25 um"),
            thermal_expansion_coefficient=_q("11.7e-6 / K"),
        )
    with pytest.raises(ValueError, match="assembly_clearance must be non-negative"):
        shrink_fit_assembly_temperature(
            interface_diameter=_q("40 mm"),
            diametral_interference=_q("59 um"),
            assembly_clearance=_q("-1 um"),
            thermal_expansion_coefficient=_q("11.7e-6 / K"),
        )


def test_differential_thermal_stress_worked_example():
    # Aluminum (a=23e-6, E=69 GPa) rigidly joined to steel (a=12e-6, E=200 GPa),
    # each 100 mm^2, heated +100 K: F = (a1-a2)*dT / (1/E1A1 + 1/E2A2) = 5643 N;
    #   the higher-a aluminum is compressed -56.4 MPa, the steel tensioned +56.4.
    r = differential_thermal_stress(
        temperature_change=_q("100 K"),
        thermal_expansion_coefficient_1=_q("23e-6 / K"),
        elastic_modulus_1=_q("69 GPa"),
        area_1=_q("100 mm**2"),
        thermal_expansion_coefficient_2=_q("12e-6 / K"),
        elastic_modulus_2=_q("200 GPa"),
        area_2=_q("100 mm**2"),
    )
    assert r.constraint_force.to("N").magnitude == pytest.approx(5643.4, rel=1e-3)
    assert r.stress_1.to("MPa").magnitude == pytest.approx(-56.434, rel=1e-3)
    assert r.stress_2.to("MPa").magnitude == pytest.approx(56.434, rel=1e-3)
    # The shared force is the same in both members: |sigma_i| = F/A_i.
    assert r.stress_2.to("MPa").magnitude == pytest.approx(
        r.constraint_force.to("N").magnitude / 100, rel=1e-6
    )


def test_differential_thermal_stress_vanishes_for_matched_cte():
    # Same expansion coefficient -> no misfit -> no stress, whatever the moduli.
    r = differential_thermal_stress(
        temperature_change=_q("100 K"),
        thermal_expansion_coefficient_1=_q("12e-6 / K"),
        elastic_modulus_1=_q("69 GPa"),
        area_1=_q("100 mm**2"),
        thermal_expansion_coefficient_2=_q("12e-6 / K"),
        elastic_modulus_2=_q("200 GPa"),
        area_2=_q("50 mm**2"),
    )
    assert r.constraint_force.to("N").magnitude == pytest.approx(0.0, abs=1e-9)
    assert r.stress_1.to("MPa").magnitude == pytest.approx(0.0, abs=1e-9)


def test_differential_thermal_stress_rejects_bad_units():
    with pytest.raises(ValueError, match="temperature_change must be a"):
        differential_thermal_stress(
            temperature_change=_q("100 mm"),
            thermal_expansion_coefficient_1=_q("23e-6 / K"),
            elastic_modulus_1=_q("69 GPa"),
            area_1=_q("100 mm**2"),
            thermal_expansion_coefficient_2=_q("12e-6 / K"),
            elastic_modulus_2=_q("200 GPa"),
            area_2=_q("100 mm**2"),
        )


def test_bimetallic_strip_curvature_and_tip_deflection():
    # Equal 1 mm layers, equal 200 GPa moduli, Delta-alpha = 11e-6/K, 100 K rise.
    # Timoshenko reduces to 1/rho = 3*da*dT/(2h) = 3*11e-6*100/(2*2) = 8.25e-4 /mm.
    layers = {
        "alpha_1": _q("12e-6 / K"),
        "elastic_modulus_1": _q("200 GPa"),
        "thickness_1": _q("1 mm"),
        "alpha_2": _q("23e-6 / K"),
        "elastic_modulus_2": _q("200 GPa"),
        "thickness_2": _q("1 mm"),
        "temperature_change": _q("100 K"),
    }
    curvature = bimetallic_strip_curvature(**layers)
    assert curvature.to("1/mm").magnitude == pytest.approx(3 * 11e-6 * 100 / (2 * 2), rel=1e-12)
    assert curvature.to("1/mm").magnitude == pytest.approx(8.25e-4, rel=1e-6)
    # A cantilever strip: tip deflection delta = (1/rho)*L^2/2.
    tip = bimetallic_strip_tip_deflection(length=_q("50 mm"), **layers)
    assert tip.to("mm").magnitude == pytest.approx(8.25e-4 * 50**2 / 2, rel=1e-12)
    assert tip.to("mm").magnitude == pytest.approx(1.03125, rel=1e-6)
    # Matched CTEs -> no bowing at all.
    flat = bimetallic_strip_curvature(
        alpha_1=_q("15e-6 / K"),
        elastic_modulus_1=_q("200 GPa"),
        thickness_1=_q("1 mm"),
        alpha_2=_q("15e-6 / K"),
        elastic_modulus_2=_q("120 GPa"),
        thickness_2=_q("2 mm"),
        temperature_change=_q("100 K"),
    )
    assert flat.to("1/mm").magnitude == pytest.approx(0.0, abs=1e-15)
    with pytest.raises(ValueError, match="alpha_1 must have units"):
        bimetallic_strip_curvature(
            alpha_1=_q("12 mm"),
            elastic_modulus_1=_q("200 GPa"),
            thickness_1=_q("1 mm"),
            alpha_2=_q("23e-6 / K"),
            elastic_modulus_2=_q("200 GPa"),
            thickness_2=_q("1 mm"),
            temperature_change=_q("100 K"),
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


def test_cantilever_tip_mass_frequency_with_beam_mass_correction():
    from math import pi, sqrt

    kw = {
        "elastic_modulus": _q("200 GPa"),
        "second_moment": _q("1e4 mm**4"),
        "length": _q("100 mm"),
        "tip_mass": _q("0.1 kg"),
    }
    k_si = 3 * 200e3 * 1e4 / 100**3 * 1000  # k = 3EI/L^3 in N/m
    # Massless-beam limit: f = (1/2pi)*sqrt(k/m_tip).
    massless = cantilever_tip_mass_frequency(**kw)
    assert massless.to("Hz").magnitude == pytest.approx(sqrt(k_si / 0.1) / (2 * pi), rel=1e-12)
    # It equals the plain SDOF frequency at that stiffness.
    assert massless.to("Hz").magnitude == pytest.approx(
        natural_frequency(stiffness=_q(f"{k_si} N/m"), mass=_q("0.1 kg")).to("Hz").magnitude,
        rel=1e-12,
    )
    # Including the beam's own mass adds 33/140 of it to the effective mass, which
    # lowers the frequency.
    with_beam = cantilever_tip_mass_frequency(**kw, beam_mass=_q("0.05 kg"))
    m_eff = 0.1 + (33 / 140) * 0.05
    assert with_beam.to("Hz").magnitude == pytest.approx(sqrt(k_si / m_eff) / (2 * pi), rel=1e-12)
    assert with_beam.to("Hz").magnitude < massless.to("Hz").magnitude
    with pytest.raises(ValueError, match="tip_mass must be positive"):
        cantilever_tip_mass_frequency(
            elastic_modulus=_q("200 GPa"),
            second_moment=_q("1e4 mm**4"),
            length=_q("100 mm"),
            tip_mass=_q("0 kg"),
        )


def test_simply_supported_center_mass_frequency_with_beam_mass_correction():
    from math import pi, sqrt

    kw = {
        "elastic_modulus": _q("200 GPa"),
        "second_moment": _q("1e6 mm**4"),
        "length": _q("2000 mm"),
        "center_mass": _q("50 kg"),
    }
    k_si = 48 * 200e3 * 1e6 / 2000**3 * 1000  # k = 48EI/L^3 in N/m
    massless = simply_supported_center_mass_frequency(**kw)
    assert massless.to("Hz").magnitude == pytest.approx(sqrt(k_si / 50) / (2 * pi), rel=1e-12)
    assert massless.to("Hz").magnitude == pytest.approx(
        natural_frequency(stiffness=_q(f"{k_si} N/m"), mass=_q("50 kg")).to("Hz").magnitude,
        rel=1e-12,
    )
    # The beam adds 17/35 of its own mass (a larger share than a cantilever's
    # 33/140, since a simply-supported beam moves more of its length).
    with_beam = simply_supported_center_mass_frequency(**kw, beam_mass=_q("30 kg"))
    m_eff = 50 + (17 / 35) * 30
    assert with_beam.to("Hz").magnitude == pytest.approx(sqrt(k_si / m_eff) / (2 * pi), rel=1e-12)
    assert with_beam.to("Hz").magnitude < massless.to("Hz").magnitude
    with pytest.raises(ValueError, match="center_mass must be positive"):
        simply_supported_center_mass_frequency(
            elastic_modulus=_q("200 GPa"),
            second_moment=_q("1e6 mm**4"),
            length=_q("2000 mm"),
            center_mass=_q("0 kg"),
        )


def test_fixed_fixed_center_mass_frequency_is_twice_the_simply_supported():
    from math import pi, sqrt

    kw = {
        "elastic_modulus": _q("200 GPa"),
        "second_moment": _q("1e6 mm**4"),
        "length": _q("2000 mm"),
        "center_mass": _q("50 kg"),
    }
    k_si = 192 * 200e3 * 1e6 / 2000**3 * 1000  # k = 192EI/L^3, 4x the simply-supported
    ff = fixed_fixed_center_mass_frequency(**kw)
    assert ff.to("Hz").magnitude == pytest.approx(sqrt(k_si / 50) / (2 * pi), rel=1e-12)
    # Four times the stiffness -> twice the (massless) frequency of the SS beam.
    ss = simply_supported_center_mass_frequency(**kw)
    assert ff.to("Hz").magnitude == pytest.approx(2 * ss.to("Hz").magnitude, rel=1e-12)
    # The clamped ends hold more of the beam still: only 13/35 of the beam mass adds.
    with_beam = fixed_fixed_center_mass_frequency(**kw, beam_mass=_q("30 kg"))
    m_eff = 50 + (13 / 35) * 30
    assert with_beam.to("Hz").magnitude == pytest.approx(sqrt(k_si / m_eff) / (2 * pi), rel=1e-12)
    assert with_beam.to("Hz").magnitude < ff.to("Hz").magnitude
    with pytest.raises(ValueError, match="center_mass must be positive"):
        fixed_fixed_center_mass_frequency(
            elastic_modulus=_q("200 GPa"),
            second_moment=_q("1e6 mm**4"),
            length=_q("2000 mm"),
            center_mass=_q("0 kg"),
        )


def test_dunkerley_combines_individual_frequencies():
    # Two discs at 30 and 40 Hz alone: 1/f^2 = 1/900 + 1/1600 -> f = 24 Hz.
    f = dunkerley_fundamental_frequency([_q("30 Hz"), _q("40 Hz")])
    assert f.to("Hz").magnitude == pytest.approx(24.0, rel=1e-6)
    # The combined estimate always falls below the lowest contributor.
    assert f.to("Hz").magnitude < 30.0
    # A single mass returns its own frequency unchanged.
    solo = dunkerley_fundamental_frequency([_q("30 Hz")])
    assert solo.to("Hz").magnitude == pytest.approx(30.0, rel=1e-9)


def test_dunkerley_rejects_bad_inputs():
    with pytest.raises(ValueError, match="non-empty"):
        dunkerley_fundamental_frequency([])
    with pytest.raises(ValueError, match=r"individual_frequencies\[1\] must be a"):
        dunkerley_fundamental_frequency([_q("30 Hz"), _q("40 N")])
    with pytest.raises(ValueError, match="each individual frequency must be positive"):
        dunkerley_fundamental_frequency([_q("0 Hz")])


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


# A 6 mm steel panel: mu = rho*t = 7850*0.006 = 47.1 kg/m^2, D = E*t^3/(12*(1-nu^2))
# = 200e9*2.16e-7/10.92 = 3956.0 N*m, sqrt(D/mu) = 9.1648 m^2/s.
_PLATE_MODAL_KW = {
    "mass_per_area": _q("47.1 kg/m**2"),
    "thickness": _q("6 mm"),
    "elastic_modulus": _q("200 GPa"),
}


def _plate_gamma(frequency, side):
    # Recover the nondimensional eigenvalue gamma = omega*L^2*sqrt(mu/D) from a
    # returned frequency, with the same D the functions build at nu = 0.3.
    mu = 47.1
    rigidity = 200e9 * 0.006**3 / (12 * (1 - 0.3**2))
    return frequency.to("Hz").magnitude * 2 * pi * side**2 * (mu / rigidity) ** 0.5


def test_ss_plate_fundamental_is_the_exact_navier_eigenvalue():
    # Square: gamma = 2*pi^2 exactly; the 500x500x6 panel lands at
    # f = 4*pi*sqrt(D/mu)/b^2... = (pi/2)*(8/m^2)*9.1648 = 115.2 Hz.
    f = simply_supported_plate_fundamental_frequency(
        length=_q("500 mm"), width=_q("500 mm"), **_PLATE_MODAL_KW
    )
    assert _plate_gamma(f, 0.5) == pytest.approx(2 * pi**2, rel=1e-12)
    assert f.to("Hz").magnitude == pytest.approx(115.17, rel=1e-3)


def test_ss_plate_strip_recovers_the_beam_stiffened_by_the_rigidity_factor():
    # A very wide SS plate is the SS beam per unit width, stiffer by exactly
    # 1/sqrt(1-nu^2) through the plate rigidity — the classic plane-strain
    # stiffening. (Rectangular orientation must not matter either.)
    plate = simply_supported_plate_fundamental_frequency(
        length=_q("500 m"), width=_q("500 mm"), **_PLATE_MODAL_KW
    )
    beam = simply_supported_fundamental_frequency(
        mass_per_length=_q("47.1 kg/m"),  # a 1 m wide strip of the panel
        length=_q("500 mm"),
        second_moment=_q("1.8e-8 m**4"),  # t^3/12 per metre of width
        elastic_modulus=_q("200 GPa"),
    )
    ratio = plate.to("Hz").magnitude / beam.to("Hz").magnitude
    assert ratio == pytest.approx(1 / (1 - 0.3**2) ** 0.5, rel=1e-5)
    swapped = simply_supported_plate_fundamental_frequency(
        length=_q("500 mm"), width=_q("500 m"), **_PLATE_MODAL_KW
    )
    assert swapped.to("Hz").magnitude == pytest.approx(plate.to("Hz").magnitude, rel=1e-12)


def test_clamped_plate_fundamental_pins_the_fd_verified_table():
    # Square knot: gamma = 35.982 from our FD biharmonic eigensolve (Leissa
    # publishes 35.992) — 1.82x the SS square. Strip limit: the fixed-fixed
    # beam eigenvalue with the same 1/sqrt(1-nu^2) rigidity stiffening.
    f_sq = clamped_plate_fundamental_frequency(
        length=_q("500 mm"), width=_q("500 mm"), **_PLATE_MODAL_KW
    )
    assert _plate_gamma(f_sq, 0.5) == pytest.approx(35.982, rel=1e-9)
    f_ss = simply_supported_plate_fundamental_frequency(
        length=_q("500 mm"), width=_q("500 mm"), **_PLATE_MODAL_KW
    )
    assert f_sq.to("Hz").magnitude / f_ss.to("Hz").magnitude == pytest.approx(
        35.982 / (2 * pi**2), rel=1e-9
    )
    strip = clamped_plate_fundamental_frequency(
        length=_q("5000 m"), width=_q("500 mm"), **_PLATE_MODAL_KW
    )
    beam = fixed_fixed_fundamental_frequency(
        mass_per_length=_q("47.1 kg/m"),
        length=_q("500 mm"),
        second_moment=_q("1.8e-8 m**4"),
        elastic_modulus=_q("200 GPa"),
    )
    ratio = strip.to("Hz").magnitude / beam.to("Hz").magnitude
    assert ratio == pytest.approx(1 / (1 - 0.3**2) ** 0.5, rel=1e-4)


def test_clamped_plate_interpolates_between_knots():
    # b/a = 0.3 sits between the 0.25 (22.798) and 1/3 (23.196) knots; linear
    # interpolation gives 22.798 + (0.05/(1/3-0.25))*(23.196-22.798) = 23.037.
    f = clamped_plate_fundamental_frequency(
        length=_q("1000 mm"), width=_q("300 mm"), **_PLATE_MODAL_KW
    )
    expected = 22.798 + (0.3 - 0.25) / (1 / 3 - 0.25) * (23.196 - 22.798)
    assert _plate_gamma(f, 0.3) == pytest.approx(expected, rel=1e-9)


def test_circular_plate_fundamentals_solve_the_characteristic_equations():
    # Clamped rim: lambda^2 = 10.21583, the first root of J0*I1 + I0*J1 = 0 —
    # nu-independent. Simply supported rim at nu = 0.3: lambda^2 = 4.93515
    # from J1/J0 + I1/I0 = 2*lambda/(1-nu) (some handbooks print 4.977; our
    # Rayleigh upper bound 4.947 from the exact static shape rules that out).
    # Clamping the rim is worth exactly their ratio, 2.070.
    kw = dict(diameter=_q("500 mm"), **_PLATE_MODAL_KW)
    f_cl = clamped_circular_plate_fundamental_frequency(**kw)
    f_ss = simply_supported_circular_plate_fundamental_frequency(**kw)
    assert _plate_gamma(f_cl, 0.25) == pytest.approx(10.215826, rel=1e-5)
    assert _plate_gamma(f_ss, 0.25) == pytest.approx(4.935149, rel=1e-5)
    assert f_cl.to("Hz").magnitude / f_ss.to("Hz").magnitude == pytest.approx(
        10.215826 / 4.935149, rel=1e-6
    )


def test_annular_plate_fundamental_pins_the_fd_table_and_the_dip():
    # At a table knot the interpolation is exact: b/a = 0.3 on the O500 panel
    # gives gamma = 4.664 simply supported — BELOW the solid plate's 4.9351:
    # a mid-size free hole sheds mass faster than bending stiffness and
    # LOWERS the fundamental. Clamped the same hole raises it (11.424).
    kw = dict(diameter=_q("500 mm"), hole_diameter=_q("150 mm"), **_PLATE_MODAL_KW)
    f_ss = simply_supported_annular_plate_fundamental_frequency(**kw)
    assert _plate_gamma(f_ss, 0.25) == pytest.approx(4.664, rel=1e-9)
    f_solid = simply_supported_circular_plate_fundamental_frequency(
        diameter=_q("500 mm"), **_PLATE_MODAL_KW
    )
    assert f_ss.to("Hz").magnitude < f_solid.to("Hz").magnitude
    f_cl = clamped_annular_plate_fundamental_frequency(**kw)
    assert _plate_gamma(f_cl, 0.25) == pytest.approx(11.424, rel=1e-9)


def test_annular_plate_fundamental_approaches_the_solid_roots():
    # A tiny hole must not move the eigenvalue: the b/a = 0.05 knots sit
    # within 0.5% of the exact solid-plate Bessel roots that open the tables.
    kw = dict(diameter=_q("500 mm"), hole_diameter=_q("25 mm"), **_PLATE_MODAL_KW)
    f_ss = simply_supported_annular_plate_fundamental_frequency(**kw)
    f_cl = clamped_annular_plate_fundamental_frequency(**kw)
    assert _plate_gamma(f_ss, 0.25) == pytest.approx(4.935149, rel=5e-3)
    assert _plate_gamma(f_cl, 0.25) == pytest.approx(10.215826, rel=5e-3)


def test_annular_plate_fundamental_rejects_outside_the_table():
    with pytest.raises(ValueError, match="must lie in"):
        simply_supported_annular_plate_fundamental_frequency(
            diameter=_q("500 mm"), hole_diameter=_q("450 mm"), **_PLATE_MODAL_KW
        )
    with pytest.raises(ValueError, match="hole_diameter must be a"):
        clamped_annular_plate_fundamental_frequency(
            diameter=_q("500 mm"), hole_diameter=_q("150 kPa"), **_PLATE_MODAL_KW
        )


def test_clamped_circular_eigenvalue_is_poisson_independent():
    # nu enters the clamped circle's frequency only through the rigidity D:
    # scaling out sqrt(1/(1-nu^2)) must leave the same eigenvalue.
    f_02 = clamped_circular_plate_fundamental_frequency(
        diameter=_q("500 mm"), poisson_ratio=0.2, **_PLATE_MODAL_KW
    )
    f_04 = clamped_circular_plate_fundamental_frequency(
        diameter=_q("500 mm"), poisson_ratio=0.4, **_PLATE_MODAL_KW
    )
    ratio = f_04.to("Hz").magnitude / f_02.to("Hz").magnitude
    assert ratio == pytest.approx(((1 - 0.2**2) / (1 - 0.4**2)) ** 0.5, rel=1e-9)


def test_plate_fundamental_rejects_bad_inputs():
    good = dict(length=_q("500 mm"), width=_q("500 mm"), **_PLATE_MODAL_KW)
    with pytest.raises(ValueError, match="mass_per_area must be a"):
        simply_supported_plate_fundamental_frequency(**{**good, "mass_per_area": _q("47.1 kg/m")})
    with pytest.raises(ValueError, match="poisson_ratio must lie in"):
        clamped_plate_fundamental_frequency(**good, poisson_ratio=0.5)
    with pytest.raises(ValueError, match="length and width must be positive"):
        simply_supported_plate_fundamental_frequency(**{**good, "width": _q("0 mm")})
    with pytest.raises(ValueError, match="diameter must be positive"):
        clamped_circular_plate_fundamental_frequency(diameter=_q("-500 mm"), **_PLATE_MODAL_KW)


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


def test_plate_center_patch_degenerates_to_the_uniform_plate():
    # A patch covering the whole plate is term-for-term the uniform series.
    kw = {
        "pressure": _q("50 kPa"),
        "length": _q("500 mm"),
        "width": _q("400 mm"),
        "thickness": _q("6 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    patch = simply_supported_plate_center_patch_load(
        patch_length=_q("500 mm"), patch_width=_q("400 mm"), **kw
    )
    uniform = simply_supported_plate_uniform_load(**kw)
    assert patch.max_bending_stress.to("MPa").magnitude == pytest.approx(
        uniform.max_bending_stress.to("MPa").magnitude, rel=1e-12
    )
    assert patch.max_deflection.to("mm").magnitude == pytest.approx(
        uniform.max_deflection.to("mm").magnitude, rel=1e-12
    )


def test_plate_center_patch_matches_worked_example_and_beats_smearing():
    # A 5 kN machine foot (0.5 MPa over its true 100x100 footprint) centred on
    # a 500x500x6 panel: sigma = 177.0 MPa, w = 3.433 mm — 4.4x the stress and
    # 2.7x the deflection the same 5 kN smeared over the panel reports
    # (39.9 MPa / 1.284 mm). Smearing a footprint is dangerously green.
    patch = simply_supported_plate_center_patch_load(
        pressure=_q("0.5 MPa"),
        patch_length=_q("100 mm"),
        patch_width=_q("100 mm"),
        length=_q("500 mm"),
        width=_q("500 mm"),
        thickness=_q("6 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert patch.max_bending_stress.to("MPa").magnitude == pytest.approx(177.009, rel=1e-4)
    assert patch.max_deflection.to("mm").magnitude == pytest.approx(3.43274, rel=1e-4)
    smeared = simply_supported_plate_uniform_load(
        pressure=_q("0.02 MPa"),  # the same 5 kN over the whole 500x500
        length=_q("500 mm"),
        width=_q("500 mm"),
        thickness=_q("6 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert (
        patch.max_bending_stress.to("MPa").magnitude
        > 4 * smeared.max_bending_stress.to("MPa").magnitude
    )


def test_plate_center_patch_approaches_the_point_load_deflection():
    # Shrinking the patch at fixed total P: the centre deflection approaches
    # the classic point-load value 0.0116*P*a^2/D for a square SS plate (the
    # stress keeps growing — the log singularity — so only deflection has a
    # point limit).
    result = simply_supported_plate_center_patch_load(
        pressure=_q("2 MPa"),  # 5 kN over 50x50
        patch_length=_q("50 mm"),
        patch_width=_q("50 mm"),
        length=_q("500 mm"),
        width=_q("500 mm"),
        thickness=_q("6 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    rigidity = 200000 * 6**3 / (12 * (1 - 0.09))
    point = 0.0116 * 5000 * 500**2 / rigidity
    assert result.max_deflection.to("mm").magnitude == pytest.approx(point, rel=3e-2)


def test_plate_center_patch_rejects_an_oversize_patch():
    with pytest.raises(ValueError, match="must fit inside the plate"):
        simply_supported_plate_center_patch_load(
            pressure=_q("0.5 MPa"),
            patch_length=_q("600 mm"),
            patch_width=_q("100 mm"),
            length=_q("500 mm"),
            width=_q("500 mm"),
            thickness=_q("6 mm"),
            elastic_modulus=_q("200 GPa"),
        )


def test_clamped_square_plate_matches_the_handbook_coefficients():
    # The same 500 x 500 x 6 mm cover with all edges built in (Roark Table
    # 11.4, nu = 0.3): sigma = 0.3078*q*b^2/t^2 = 106.9 MPa at the edge
    # midpoint and w = 0.0138*q*b^4/(E*t^3) = 0.998 mm — about 3.2x stiffer
    # than simply supported. (Both coefficients independently confirmed by a
    # finite-difference biharmonic solve: alpha to <0.5%, beta to ~1%.)
    kw = {
        "pressure": _q("50 kPa"),
        "length": _q("500 mm"),
        "width": _q("500 mm"),
        "thickness": _q("6 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    result = clamped_plate_uniform_load(**kw)
    q, b, t = 0.05, 500.0, 6.0
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(
        0.3078 * q * b**2 / t**2, rel=1e-9
    )
    assert result.max_deflection.to("mm").magnitude == pytest.approx(
        0.0138 * q * b**4 / (200000 * t**3), rel=1e-9
    )
    ss = simply_supported_plate_uniform_load(**kw)
    assert result.max_deflection.to("mm").magnitude < ss.max_deflection.to("mm").magnitude


def test_clamped_long_plate_approaches_the_fixed_fixed_strip():
    # A 20:1 plate is a unit-width fixed-fixed beam: M = q*b^2/12 exactly
    # (beta = 0.5) and w = q*b^4/(384*D) (alpha = 12*(1-0.09)/384 = 0.02844).
    # The interpolated table must land within 1% of both, and the result must
    # be orientation-blind.
    kw = {
        "pressure": _q("50 kPa"),
        "thickness": _q("6 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    strip = clamped_plate_uniform_load(length=_q("10 m"), width=_q("500 mm"), **kw)
    q, b, t = 0.05, 500.0, 6.0
    assert strip.max_bending_stress.to("MPa").magnitude == pytest.approx(
        0.5 * q * b**2 / t**2, rel=1e-2
    )
    assert strip.max_deflection.to("mm").magnitude == pytest.approx(
        (12 * (1 - 0.09) / 384) * q * b**4 / (200000 * t**3), rel=1e-2
    )
    swapped = clamped_plate_uniform_load(length=_q("500 mm"), width=_q("10 m"), **kw)
    assert strip.max_bending_stress.to("MPa").magnitude == pytest.approx(
        swapped.max_bending_stress.to("MPa").magnitude, rel=1e-12
    )


def test_clamped_plate_rejects_bad_inputs():
    with pytest.raises(ValueError, match="pressure must be a"):
        clamped_plate_uniform_load(
            pressure=_q("50 N"),
            length=_q("500 mm"),
            width=_q("500 mm"),
            thickness=_q("6 mm"),
            elastic_modulus=_q("200 GPa"),
        )


def test_circular_plate_matches_worked_example():
    # An O500 x 6 mm simply-supported steel blank under 50 kPa (nu = 0.3,
    # D = 3.956e6 N*mm): sigma = 3*(3.3)*0.05*250^2/(8*36) = 107.42 MPa;
    # w = (5.3/1.3)*0.05*250^4/(64*D) = 3.145 mm. Both confirmed against a
    # numeric check of the exact closed-form w(r) (moments + edge conditions).
    result = simply_supported_circular_plate_uniform_load(
        pressure=_q("50 kPa"),
        diameter=_q("500 mm"),
        thickness=_q("6 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(107.422, rel=1e-4)
    assert result.max_deflection.to("mm").magnitude == pytest.approx(3.1451, rel=1e-4)


def test_clamped_circular_plate_trades_deflection_for_edge_stress():
    # Clamping the rim cuts the deflection by exactly (5+nu)/(1+nu) = 4.077
    # and the peak stress by exactly (3+nu)/2 = 1.65 — the deflection win is
    # bigger than the stress win, but the stress moves to the weld at the rim.
    kw = {
        "pressure": _q("50 kPa"),
        "diameter": _q("500 mm"),
        "thickness": _q("6 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    ss = simply_supported_circular_plate_uniform_load(**kw)
    clamped = clamped_circular_plate_uniform_load(**kw)
    nu = 0.3
    assert ss.max_deflection.to("mm").magnitude == pytest.approx(
        (5 + nu) / (1 + nu) * clamped.max_deflection.to("mm").magnitude, rel=1e-12
    )
    assert ss.max_bending_stress.to("MPa").magnitude == pytest.approx(
        (3 + nu) / 2 * clamped.max_bending_stress.to("MPa").magnitude, rel=1e-12
    )


def test_clamped_circular_cover_thickness_inverts_the_rim_stress():
    # 1 MPa on a 300 mm clamped cover within a 100 MPa allowable needs
    #   t = R*sqrt(3*q/(4*sigma)) = 150*sqrt(0.0075) = 12.99 mm.
    t = clamped_circular_plate_thickness_for_pressure(
        pressure=_q("1 MPa"), diameter=_q("300 mm"), allowable_stress=_q("100 MPa")
    )
    assert t.to("mm").magnitude == pytest.approx(12.990, rel=1e-4)
    # A cover of exactly this thickness is worked to the allowable at the rim.
    stress = clamped_circular_plate_uniform_load(
        pressure=_q("1 MPa"), diameter=_q("300 mm"), thickness=t, elastic_modulus=_q("200 GPa")
    ).max_bending_stress
    assert stress.to("MPa").magnitude == pytest.approx(100.0, rel=1e-6)


def test_clamped_circular_cover_thickness_scales_with_sqrt_margin():
    base = clamped_circular_plate_thickness_for_pressure(
        pressure=_q("1 MPa"), diameter=_q("300 mm"), allowable_stress=_q("100 MPa")
    )
    with_sf = clamped_circular_plate_thickness_for_pressure(
        pressure=_q("1 MPa"),
        diameter=_q("300 mm"),
        allowable_stress=_q("100 MPa"),
        required_safety_factor=2.0,
    )
    # Thickness scales with the square root of the required margin.
    assert with_sf.to("mm").magnitude == pytest.approx(2.0**0.5 * base.to("mm").magnitude, rel=1e-9)


def test_clamped_circular_cover_thickness_rejects_bad_inputs():
    with pytest.raises(ValueError, match="pressure must be a"):
        clamped_circular_plate_thickness_for_pressure(
            pressure=_q("1 N"), diameter=_q("300 mm"), allowable_stress=_q("100 MPa")
        )
    with pytest.raises(ValueError, match="allowable_stress must be positive"):
        clamped_circular_plate_thickness_for_pressure(
            pressure=_q("1 MPa"), diameter=_q("300 mm"), allowable_stress=_q("0 MPa")
        )
    with pytest.raises(ValueError, match="required_safety_factor must be positive"):
        clamped_circular_plate_thickness_for_pressure(
            pressure=_q("1 MPa"),
            diameter=_q("300 mm"),
            allowable_stress=_q("100 MPa"),
            required_safety_factor=0.0,
        )


def test_circular_plate_rejects_bad_inputs():
    kw = {
        "diameter": _q("500 mm"),
        "thickness": _q("6 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    with pytest.raises(ValueError, match="pressure must be a"):
        clamped_circular_plate_uniform_load(pressure=_q("50 N"), **kw)
    with pytest.raises(ValueError, match="poisson_ratio must lie in"):
        simply_supported_circular_plate_uniform_load(pressure=_q("50 kPa"), poisson_ratio=0.5, **kw)


def test_circular_plate_central_point_load_deflection():
    from math import pi

    kw = {
        "force": _q("10 kN"),
        "diameter": _q("500 mm"),
        "thickness": _q("10 mm"),
        "elastic_modulus": _q("200 GPa"),
    }
    nu = 0.3
    rigidity = 200e3 * 10.0**3 / (12 * (1 - nu**2))  # N*mm
    clamped = clamped_circular_plate_center_load_deflection(**kw)
    ss = simply_supported_circular_plate_center_load_deflection(**kw)
    # w_clamped = P*R^2/(16*pi*D); w_ss = P*R^2*(3+nu)/(16*pi*D*(1+nu)).
    assert clamped.to("mm").magnitude == pytest.approx(
        10000.0 * 250.0**2 / (16 * pi * rigidity), rel=1e-12
    )
    assert clamped.to("mm").magnitude == pytest.approx(0.67890, rel=1e-4)
    assert ss.to("mm").magnitude == pytest.approx(
        10000.0 * 250.0**2 * (3 + nu) / (16 * pi * rigidity * (1 + nu)), rel=1e-12
    )
    # The simply-supported plate deflects (3+nu)/(1+nu) times the clamped one.
    assert ss.to("mm").magnitude == pytest.approx(
        (3 + nu) / (1 + nu) * clamped.to("mm").magnitude, rel=1e-12
    )
    with pytest.raises(ValueError, match="force must be a"):
        clamped_circular_plate_center_load_deflection(
            force=_q("10 MPa"),
            diameter=_q("500 mm"),
            thickness=_q("10 mm"),
            elastic_modulus=_q("200 GPa"),
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


_ANNULAR_KW = {
    "pressure": _q("50 kPa"),
    "diameter": _q("500 mm"),
    "thickness": _q("6 mm"),
    "elastic_modulus": _q("200 GPa"),
}


def test_annular_plate_matches_the_fd_verified_worked_case():
    # O500 x 6 (E = 200 GPa) at 50 kPa with a O100 free-edged hole (b/a = 0.2),
    # both verified against an independent finite-difference solve of the
    # axisymmetric plate ODE (w to 1e-4, moments to <1%). Simply supported the
    # governing moment is the TANGENTIAL bending at the hole edge: 190.3 MPa
    # and 3.677 mm — 1.77x the solid plate's stress. Clamped, the rim radial
    # moment still governs (63.3 MPa, close to the solid rim's 65.1) and the
    # hole mainly costs deflection.
    ss = simply_supported_annular_plate_uniform_load(hole_diameter=_q("100 mm"), **_ANNULAR_KW)
    assert ss.max_bending_stress.to("MPa").magnitude == pytest.approx(190.32, rel=1e-3)
    assert ss.max_deflection.to("mm").magnitude == pytest.approx(3.677, rel=1e-3)
    clamped = clamped_annular_plate_uniform_load(hole_diameter=_q("100 mm"), **_ANNULAR_KW)
    assert clamped.max_bending_stress.to("MPa").magnitude == pytest.approx(63.34, rel=1e-3)
    assert clamped.max_deflection.to("mm").magnitude == pytest.approx(0.7925, rel=1e-3)
    solid_rim = 3 * 0.05 * 250**2 / (4 * 6**2)
    assert clamped.max_bending_stress.to("MPa").magnitude < solid_rim


def test_annular_plate_recovers_the_solid_deflection_but_doubles_the_stress():
    # Shrinking the hole recovers the solid plate's deflection, but the
    # hole-edge hoop moment approaches exactly TWICE the solid centre stress —
    # the equibiaxial small-hole bending concentration. A tiny undeclared
    # hole is a 2x stress the solid-plate screen never sees.
    solid = simply_supported_circular_plate_uniform_load(**_ANNULAR_KW)
    tiny = simply_supported_annular_plate_uniform_load(hole_diameter=_q("0.5 mm"), **_ANNULAR_KW)
    assert tiny.max_deflection.to("mm").magnitude == pytest.approx(
        solid.max_deflection.to("mm").magnitude, rel=1e-3
    )
    ratio = (
        tiny.max_bending_stress.to("MPa").magnitude / solid.max_bending_stress.to("MPa").magnitude
    )
    assert ratio == pytest.approx(2.0, rel=1e-3)


def test_annular_plate_rejects_bad_holes():
    with pytest.raises(ValueError, match="must be smaller than the plate"):
        simply_supported_annular_plate_uniform_load(hole_diameter=_q("500 mm"), **_ANNULAR_KW)
    with pytest.raises(ValueError, match="must be smaller than the plate"):
        clamped_annular_plate_uniform_load(hole_diameter=_q("0 mm"), **_ANNULAR_KW)
    with pytest.raises(ValueError, match="hole_diameter must be a"):
        simply_supported_annular_plate_uniform_load(hole_diameter=_q("100 kPa"), **_ANNULAR_KW)
    with pytest.raises(ValueError, match="poisson_ratio must lie in"):
        clamped_annular_plate_uniform_load(
            hole_diameter=_q("100 mm"), poisson_ratio=0.7, **_ANNULAR_KW
        )


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


def test_two_rotor_torsional_natural_frequency():
    from math import pi, sqrt

    # I_eq = I1*I2/(I1+I2) = 0.1*0.4/0.5 = 0.08 kg*m^2; k_t = 5000 N*m/rad.
    # f_n = sqrt(5000/0.08)/(2*pi) = 39.79 Hz.
    fn = two_rotor_torsional_natural_frequency(
        torsional_stiffness=_q("5000 N*m"),
        polar_mass_moment_1=_q("0.1 kg*m**2"),
        polar_mass_moment_2=_q("0.4 kg*m**2"),
    )
    assert fn.to("Hz").magnitude == pytest.approx(sqrt(5000 / 0.08) / (2 * pi), rel=1e-12)
    assert fn.to("Hz").magnitude == pytest.approx(39.789, rel=1e-4)
    # As one inertia grows without bound the reduced inertia -> the smaller one,
    # recovering the fixed-end single-disc frequency at I1.
    huge = two_rotor_torsional_natural_frequency(
        torsional_stiffness=_q("5000 N*m"),
        polar_mass_moment_1=_q("0.1 kg*m**2"),
        polar_mass_moment_2=_q("1e9 kg*m**2"),
    )
    single = torsional_natural_frequency(
        torsional_stiffness=_q("5000 N*m"), polar_mass_moment=_q("0.1 kg*m**2")
    )
    assert huge.to("Hz").magnitude == pytest.approx(single.to("Hz").magnitude, rel=1e-6)
    with pytest.raises(ValueError, match="both polar mass moments must be positive"):
        two_rotor_torsional_natural_frequency(
            torsional_stiffness=_q("5000 N*m"),
            polar_mass_moment_1=_q("0 kg*m**2"),
            polar_mass_moment_2=_q("0.4 kg*m**2"),
        )


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


def test_annular_disc_polar_mass_moment():
    # I = m*(D^2 + d^2)/8: 10 kg, 0.4 m outer, 0.2 m inner -> 0.25 kg*m^2.
    i = annular_disc_polar_mass_moment(
        mass=_q("10 kg"), outer_diameter=_q("0.4 m"), inner_diameter=_q("0.2 m")
    )
    assert i.to("kg*m**2").magnitude == pytest.approx(10 * (0.4**2 + 0.2**2) / 8, rel=1e-12)
    assert i.to("kg*m**2").magnitude == pytest.approx(0.25, rel=1e-12)
    # A vanishing bore recovers the solid disc's m*D^2/8.
    solid_limit = annular_disc_polar_mass_moment(
        mass=_q("10 kg"), outer_diameter=_q("0.4 m"), inner_diameter=_q("0 m")
    )
    assert solid_limit.to("kg*m**2").magnitude == pytest.approx(
        solid_disc_polar_mass_moment(mass=_q("10 kg"), diameter=_q("0.4 m"))
        .to("kg*m**2")
        .magnitude,
        rel=1e-12,
    )
    # Boring out the same mass concentrates it at large radius -> more inertia than
    # the solid disc of that mass and outer diameter.
    assert i.to("kg*m**2").magnitude > solid_limit.to("kg*m**2").magnitude
    with pytest.raises(ValueError, match="inner_diameter .* must be non-negative and below"):
        annular_disc_polar_mass_moment(
            mass=_q("10 kg"), outer_diameter=_q("0.2 m"), inner_diameter=_q("0.4 m")
        )


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


def test_von_mises_and_tresca_principal_on_the_thick_wall_bore():
    # The thick-wall cylinder bore is a genuine triaxial state that the plane
    # forms cannot hold: hoop 185, radial -60, longitudinal 62.5 MPa.
    triad = {"sigma_1": _q("185 MPa"), "sigma_2": _q("-60 MPa"), "sigma_3": _q("62.5 MPa")}
    # Tresca = max - min = 185 - (-60) = 245 MPa (matches bore_tresca_stress).
    tresca = tresca_principal(**triad)
    assert tresca.to("MPa").magnitude == pytest.approx(245.0, rel=1e-9)
    # von Mises = sqrt(0.5*[(185+60)^2 + (-60-62.5)^2 + (62.5-185)^2]) = 212.18 MPa.
    vm = von_mises_principal(**triad)
    assert vm.to("MPa").magnitude == pytest.approx(212.18, rel=1e-4)
    assert vm.to("MPa").magnitude < tresca.to("MPa").magnitude  # vM never above Tresca


def test_von_mises_principal_matches_the_plane_form_when_one_principal_is_zero():
    # With sigma_3 = 0 the triaxial von Mises collapses onto the plane-stress
    # result computed from the same two in-plane principals.
    s1, s2 = principal_stresses_plane(
        sigma_x=_q("100 MPa"), sigma_y=_q("40 MPa"), tau_xy=_q("30 MPa")
    )
    triaxial = von_mises_principal(sigma_1=s1, sigma_2=s2, sigma_3=_q("0 MPa"))
    plane = von_mises_plane_stress(sigma_x=_q("100 MPa"), sigma_y=_q("40 MPa"), tau_xy=_q("30 MPa"))
    assert triaxial.to("MPa").magnitude == pytest.approx(plane.to("MPa").magnitude, rel=1e-9)


def test_von_mises_principal_is_zero_for_hydrostatic_stress():
    # Pure hydrostatic (equal triaxial) stress causes no distortion -> von Mises 0,
    # while Tresca is also 0 (max = min). The classic von Mises property.
    triad = {"sigma_1": _q("80 MPa"), "sigma_2": _q("80 MPa"), "sigma_3": _q("80 MPa")}
    assert von_mises_principal(**triad).to("MPa").magnitude == pytest.approx(0.0, abs=1e-9)
    assert tresca_principal(**triad).to("MPa").magnitude == pytest.approx(0.0, abs=1e-9)


def test_triaxial_forms_reject_non_stress_inputs():
    with pytest.raises(ValueError, match="sigma_1 must be a"):
        von_mises_principal(sigma_1=_q("5 mm"), sigma_2=_q("0 MPa"), sigma_3=_q("0 MPa"))
    with pytest.raises(ValueError, match="sigma_3 must be a"):
        tresca_principal(sigma_1=_q("5 MPa"), sigma_2=_q("0 MPa"), sigma_3=_q("1 N"))


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


def test_short_shoe_brake_self_energizing_lever_statics():
    # F=1 kN at c=300 mm, shoe normal at b=100 mm, friction drag at a=40 mm,
    # mu=0.35. Self-energizing: N = F*c/(b - mu*a) = 300000/86 = 3488.4 N.
    energized = short_shoe_normal_force(
        actuation_force=_q("1 kN"),
        force_arm=_q("300 mm"),
        normal_arm=_q("100 mm"),
        friction_arm=_q("40 mm"),
        friction_coefficient=0.35,
        self_energizing=True,
    )
    assert energized.to("N").magnitude == pytest.approx(300000.0 / 86.0, rel=1e-12)
    # Reversed drum rotation fights the lever: N = F*c/(b + mu*a) = 2631.6 N --
    # the same hand force brakes measurably harder in the energizing direction.
    opposed = short_shoe_normal_force(
        actuation_force=_q("1 kN"),
        force_arm=_q("300 mm"),
        normal_arm=_q("100 mm"),
        friction_arm=_q("40 mm"),
        friction_coefficient=0.35,
        self_energizing=False,
    )
    assert opposed.to("N").magnitude == pytest.approx(300000.0 / 114.0, rel=1e-12)
    assert energized.to("N").magnitude > opposed.to("N").magnitude
    # Torque is the friction drag at the drum radius: T = mu*N*D/2.
    torque = short_shoe_brake_torque(
        normal_force=energized, drum_diameter=_q("300 mm"), friction_coefficient=0.35
    )
    assert torque.to("N*m").magnitude == pytest.approx(0.35 * (300000.0 / 86.0) * 0.15, rel=1e-12)
    # With mu=0 there is no energizing effect and both directions agree at F*c/b.
    neutral = short_shoe_normal_force(
        actuation_force=_q("1 kN"),
        force_arm=_q("300 mm"),
        normal_arm=_q("100 mm"),
        friction_arm=_q("40 mm"),
        friction_coefficient=0.0,
        self_energizing=True,
    )
    assert neutral.to("N").magnitude == pytest.approx(3000.0, rel=1e-12)


def test_short_shoe_brake_self_locking_geometry():
    # b=30 mm on a=100 mm locks at mu >= 0.3; a mu=0.35 lining grabs.
    assert short_shoe_is_self_locking(
        normal_arm=_q("30 mm"), friction_arm=_q("100 mm"), friction_coefficient=0.35
    )
    assert not short_shoe_is_self_locking(
        normal_arm=_q("100 mm"), friction_arm=_q("40 mm"), friction_coefficient=0.35
    )
    # The force solve refuses the locking geometry rather than returning a
    # negative "force".
    with pytest.raises(ValueError, match="self-locking geometry"):
        short_shoe_normal_force(
            actuation_force=_q("1 kN"),
            force_arm=_q("300 mm"),
            normal_arm=_q("30 mm"),
            friction_arm=_q("100 mm"),
            friction_coefficient=0.35,
            self_energizing=True,
        )
    # The de-energizing direction of the same geometry is fine (b + mu*a).
    released = short_shoe_normal_force(
        actuation_force=_q("1 kN"),
        force_arm=_q("300 mm"),
        normal_arm=_q("30 mm"),
        friction_arm=_q("100 mm"),
        friction_coefficient=0.35,
        self_energizing=False,
    )
    assert released.to("N").magnitude == pytest.approx(300000.0 / 65.0, rel=1e-12)
    with pytest.raises(ValueError, match="normal_arm must be positive"):
        short_shoe_is_self_locking(
            normal_arm=_q("0 mm"), friction_arm=_q("100 mm"), friction_coefficient=0.35
        )
    with pytest.raises(ValueError, match="normal_force must be a"):
        short_shoe_brake_torque(
            normal_force=_q("3 mm"), drum_diameter=_q("300 mm"), friction_coefficient=0.35
        )


def test_curved_beam_winkler_stresses_and_neutral_axis_shift():
    from math import log

    # 20 mm wide, ri=50 / ro=100 (h=50), opened by 500 N*m: the neutral axis
    # sits at rn = h/ln(ro/ri) = 72.135 mm, e = 2.865 mm inside the centroid.
    result = rectangular_curved_beam_stress(
        moment=_q("500 N*m"),
        inner_radius=_q("50 mm"),
        outer_radius=_q("100 mm"),
        width=_q("20 mm"),
    )
    rn = 50.0 / log(2.0)
    e = 75.0 - rn
    assert result.neutral_radius.to("mm").magnitude == pytest.approx(rn, rel=1e-12)
    assert result.eccentricity.to("mm").magnitude == pytest.approx(e, rel=1e-12)
    # sigma_i = M*(rn - ri)/(A*e*ri): the bore works at 77.3 MPa where the
    # straight-beam formula 6M/(b*h^2) claims only 60 -- hooks crack inside.
    inner = 500e3 * (rn - 50.0) / (1000.0 * e * 50.0)
    outer = 500e3 * (rn - 100.0) / (1000.0 * e * 100.0)
    assert result.inner_stress.to("MPa").magnitude == pytest.approx(inner, rel=1e-12)
    assert result.inner_stress.to("MPa").magnitude == pytest.approx(77.259, rel=1e-4)
    assert result.outer_stress.to("MPa").magnitude == pytest.approx(outer, rel=1e-12)
    assert result.outer_stress.to("MPa").magnitude == pytest.approx(-48.630, rel=1e-4)
    # The bore always works harder than the back.
    assert abs(result.inner_stress.magnitude) > abs(result.outer_stress.magnitude)
    assert result.inner_stress.magnitude > 6.0 * 500e3 / (20.0 * 50.0**2)


def test_curved_beam_stress_field_satisfies_equilibrium():
    from math import log

    # Integrate the hyperbolic field sigma(r) = M*(rn-r)/(A*e*r) directly:
    # the net axial force must vanish and the moment about the CENTROID must
    # recover the applied M (Winkler's two defining conditions).
    ri, ro, b, m = 50.0, 100.0, 20.0, 500e3
    h = ro - ri
    rn = h / log(ro / ri)
    rc = (ri + ro) / 2.0
    e = rc - rn
    area = b * h
    n = 400_000
    dr = h / n
    force = 0.0
    moment_about_centroid = 0.0
    for i in range(n):
        r = ri + (i + 0.5) * dr
        sigma = m * (rn - r) / (area * e * r)
        force += sigma * b * dr
        moment_about_centroid += sigma * (r - rc) * b * dr
    # Zero net force (the rn definition) and |moment| = M about the centroid.
    assert abs(force) < 1e-6 * m / h
    assert -moment_about_centroid == pytest.approx(m, rel=1e-9)


def test_curved_beam_recovers_the_straight_beam_as_curvature_flattens():
    # Same 20x50 section bent by 500 N*m at rc/h = 200: both fibres approach
    # the straight-beam +/- 6M/(b*h^2) = 60 MPa, inner from above.
    result = rectangular_curved_beam_stress(
        moment=_q("500 N*m"),
        inner_radius=_q("9975 mm"),
        outer_radius=_q("10025 mm"),
        width=_q("20 mm"),
    )
    straight = 6.0 * 500e3 / (20.0 * 50.0**2)
    assert result.inner_stress.to("MPa").magnitude == pytest.approx(straight, rel=2e-3)
    assert result.outer_stress.to("MPa").magnitude == pytest.approx(-straight, rel=2e-3)
    assert result.inner_stress.to("MPa").magnitude > straight
    with pytest.raises(ValueError, match="inner_radius must be positive"):
        rectangular_curved_beam_stress(
            moment=_q("500 N*m"),
            inner_radius=_q("0 mm"),
            outer_radius=_q("100 mm"),
            width=_q("20 mm"),
        )
    with pytest.raises(ValueError, match="must exceed inner_radius"):
        rectangular_curved_beam_stress(
            moment=_q("500 N*m"),
            inner_radius=_q("100 mm"),
            outer_radius=_q("100 mm"),
            width=_q("20 mm"),
        )


def test_marin_endurance_limit_discounts_the_specimen_value():
    # A machined 1045 shaft: Se' = 0.5*Su = 283 MPa (estimate), then Marin
    # ka=0.787 (machined fit at Su=565), kb=0.879 (25 mm), kc=1 (bending):
    # Se = 0.787*0.879*283 = 195.8 MPa -- the real part keeps ~69%.
    se_prime = estimated_endurance_limit(ultimate_strength=_q("565 MPa"))
    assert se_prime.to("MPa").magnitude == pytest.approx(282.5, rel=1e-12)
    corrected = marin_endurance_limit(
        base_endurance_limit=se_prime,
        surface_factor=0.787,
        size_factor=0.879,
        load_factor=1.0,
    )
    assert corrected.to("MPa").magnitude == pytest.approx(0.787 * 0.879 * 282.5, rel=1e-12)
    # All factors default to 1: no correction returns the input value.
    untouched = marin_endurance_limit(base_endurance_limit=se_prime)
    assert untouched.to("MPa").magnitude == pytest.approx(282.5, rel=1e-12)
    # Torsion discounts further via kc.
    torsion = marin_endurance_limit(
        base_endurance_limit=se_prime,
        surface_factor=0.787,
        size_factor=0.879,
        load_factor=0.59,
    )
    assert torsion.to("MPa").magnitude == pytest.approx(
        0.59 * corrected.to("MPa").magnitude, rel=1e-12
    )
    with pytest.raises(ValueError, match="size_factor must be positive"):
        marin_endurance_limit(base_endurance_limit=se_prime, size_factor=0.0)
    with pytest.raises(ValueError, match="base_endurance_limit must be a"):
        marin_endurance_limit(base_endurance_limit=_q("283 mm"))


def test_differential_band_brake_lever_force_and_self_locking():
    from math import exp, pi

    # T1=2 kN, mu=0.25, 270-degree wrap: T2 = T1/e^(mu*beta) = 615.7 N. A
    # simple band brake (tight end on the pivot, b=0) needs F = T2*a/L =
    # 615.7*0.2/0.8 = 153.9 N of hand force.
    wrap = 3.0 * pi / 2.0
    simple = differential_band_brake_actuation_force(
        tight_tension=_q("2 kN"),
        slack_arm=_q("200 mm"),
        tight_arm=_q("0 mm"),
        lever_length=_q("800 mm"),
        friction_coefficient=0.25,
        wrap_angle=wrap,
    )
    t2 = 2000.0 / exp(0.25 * wrap)
    assert simple.to("N").magnitude == pytest.approx(t2 * 0.2 / 0.8, rel=1e-12)
    # Anchoring the tight end 50 mm past the pivot makes it pull the band on:
    # F = (T2*a - T1*b)/L = (123.1 - 100)/0.8 = 28.9 N -- a fifth the force.
    differential = differential_band_brake_actuation_force(
        tight_tension=_q("2 kN"),
        slack_arm=_q("200 mm"),
        tight_arm=_q("50 mm"),
        lever_length=_q("800 mm"),
        friction_coefficient=0.25,
        wrap_angle=wrap,
    )
    assert differential.to("N").magnitude == pytest.approx(
        (t2 * 0.2 - 2000.0 * 0.05) / 0.8, rel=1e-12
    )
    assert differential.to("N").magnitude < simple.to("N").magnitude
    assert not differential_band_brake_is_self_locking(
        slack_arm=_q("200 mm"),
        tight_arm=_q("50 mm"),
        friction_coefficient=0.25,
        wrap_angle=wrap,
    )
    # Pushing the tight arm to 70 mm crosses a <= b*e^(mu*beta): the returned
    # force goes NEGATIVE (the band winds itself tight) and the predicate flags.
    locked = differential_band_brake_actuation_force(
        tight_tension=_q("2 kN"),
        slack_arm=_q("200 mm"),
        tight_arm=_q("70 mm"),
        lever_length=_q("800 mm"),
        friction_coefficient=0.25,
        wrap_angle=wrap,
    )
    assert locked.to("N").magnitude < 0
    assert differential_band_brake_is_self_locking(
        slack_arm=_q("200 mm"),
        tight_arm=_q("70 mm"),
        friction_coefficient=0.25,
        wrap_angle=wrap,
    )
    with pytest.raises(ValueError, match="tight_arm must be non-negative"):
        differential_band_brake_actuation_force(
            tight_tension=_q("2 kN"),
            slack_arm=_q("200 mm"),
            tight_arm=_q("-5 mm"),
            lever_length=_q("800 mm"),
            friction_coefficient=0.25,
            wrap_angle=wrap,
        )
    with pytest.raises(ValueError, match="slack_arm must be positive"):
        differential_band_brake_is_self_locking(
            slack_arm=_q("0 mm"),
            tight_arm=_q("50 mm"),
            friction_coefficient=0.25,
            wrap_angle=wrap,
        )


def test_belleville_washer_almen_laszlo_curve():
    from math import log, pi

    # De=40/Di=20 (C=2 -> K1=0.6889), t=2, cone height h=1, steel: at y=0.5 mm
    # F = 4*E*y/((1-nu^2)*K1*De^2) * [(h-y)(h-y/2)+t^2] = 1797 N.
    kwargs = {
        "thickness": _q("2 mm"),
        "cone_height": _q("1 mm"),
        "outer_diameter": _q("40 mm"),
        "inner_diameter": _q("20 mm"),
        "elastic_modulus": _q("206 GPa"),
    }
    k1 = (6.0 / (pi * log(2.0))) * (0.5) ** 2
    force = belleville_washer_force(deflection=_q("0.5 mm"), **kwargs)
    expected = 4.0 * 206000.0 * 0.5 / (0.91 * k1 * 1600.0) * ((0.5) * (0.75) + 4.0)
    assert force.to("N").magnitude == pytest.approx(expected, rel=1e-12)
    assert force.to("N").magnitude == pytest.approx(1797.1, rel=1e-4)
    # The flat load is the y=h endpoint of the same curve (only t^2 survives).
    flat = belleville_flat_load(**kwargs)
    at_h = belleville_washer_force(deflection=_q("1 mm"), **kwargs)
    assert flat.to("N").magnitude == pytest.approx(at_h.to("N").magnitude, rel=1e-12)
    assert flat.to("N").magnitude == pytest.approx(3286.2, rel=1e-4)
    # A shallow disc (h/t = 0.1) is essentially a linear spring.
    shallow = {**kwargs, "cone_height": _q("0.2 mm")}
    f1 = belleville_washer_force(deflection=_q("0.1 mm"), **shallow)
    f2 = belleville_washer_force(deflection=_q("0.2 mm"), **shallow)
    assert f2.to("N").magnitude / f1.to("N").magnitude == pytest.approx(2.0, rel=5e-3)


def test_belleville_washer_plateau_appears_at_root_two():
    # Below h/t = sqrt(2) the load climbs all the way to flat; above it the
    # curve has an interior maximum (the constant-force/snap-through regime).
    def curve(t_mm: float, h_mm: float) -> list[float]:
        return [
            belleville_washer_force(
                deflection=_q(f"{h_mm * i / 200} mm"),
                thickness=_q(f"{t_mm} mm"),
                cone_height=_q(f"{h_mm} mm"),
                outer_diameter=_q("40 mm"),
                inner_diameter=_q("20 mm"),
                elastic_modulus=_q("206 GPa"),
            )
            .to("N")
            .magnitude
            for i in range(1, 201)
        ]

    monotone = curve(2.0, 2.0)  # h/t = 1 < sqrt(2)
    assert all(b > a for a, b in zip(monotone, monotone[1:], strict=False))
    regressive = curve(1.0, 2.0)  # h/t = 2 > sqrt(2)
    assert max(regressive) > regressive[-1]  # interior peak above the flat load
    with pytest.raises(ValueError, match=r"deflection must lie in"):
        belleville_washer_force(
            deflection=_q("3 mm"),
            thickness=_q("2 mm"),
            cone_height=_q("1 mm"),
            outer_diameter=_q("40 mm"),
            inner_diameter=_q("20 mm"),
            elastic_modulus=_q("206 GPa"),
        )
    with pytest.raises(ValueError, match="must exceed inner_diameter"):
        belleville_flat_load(
            thickness=_q("2 mm"),
            cone_height=_q("1 mm"),
            outer_diameter=_q("20 mm"),
            inner_diameter=_q("20 mm"),
            elastic_modulus=_q("206 GPa"),
        )


def test_gear_train_value_simple_compound_and_idler():
    # A 20 t pinion driving a 40 t gear: 2:1 down, one external mesh reverses.
    assert gear_train_value(driver_teeth=[20], driven_teeth=[40]) == pytest.approx(-0.5)
    # Two-stage compound train (20/40)*(30/60) = 0.25; two reversals cancel.
    e = gear_train_value(driver_teeth=[20, 30], driven_teeth=[40, 60])
    assert e == pytest.approx(0.25)
    # An idler appears in both lists: magnitude cancels to 20/30, but its extra
    # external mesh keeps the direction — that is what an idler is for.
    with_idler = gear_train_value(driver_teeth=[20, 40], driven_teeth=[40, 30])
    assert with_idler == pytest.approx(20 / 30)
    assert gear_train_value(driver_teeth=[20], driven_teeth=[30]) == pytest.approx(-20 / 30)
    # An internal (ring) mesh does not reverse.
    assert gear_train_value(
        driver_teeth=[20], driven_teeth=[40], internal_meshes=1
    ) == pytest.approx(0.5)


def test_gear_train_value_rejects_bad_inputs():
    with pytest.raises(ValueError, match="non-empty and equal length"):
        gear_train_value(driver_teeth=[20, 30], driven_teeth=[40])
    with pytest.raises(ValueError, match="non-empty and equal length"):
        gear_train_value(driver_teeth=[], driven_teeth=[])
    with pytest.raises(ValueError, match="positive whole number of teeth"):
        gear_train_value(driver_teeth=[20.5], driven_teeth=[40])
    with pytest.raises(ValueError, match="positive whole number of teeth"):
        gear_train_value(driver_teeth=[20], driven_teeth=[0])
    with pytest.raises(ValueError, match=r"internal_meshes must lie in \[0, 1\]"):
        gear_train_value(driver_teeth=[20], driven_teeth=[40], internal_meshes=2)


def test_planetary_planet_teeth_and_assembly():
    # N_p = (N_r - N_s)/2: a 30/90 sun/ring takes 30-tooth planets.
    assert planetary_planet_teeth(sun_teeth=30, ring_teeth=90) == 30
    # An odd difference leaves no whole-tooth planet — the set cannot be cut.
    with pytest.raises(ValueError, match="no whole-tooth planet fits"):
        planetary_planet_teeth(sun_teeth=30, ring_teeth=105)
    # Equal spacing needs (N_s + N_r) divisible by the planet count.
    assert planetary_can_assemble(sun_teeth=30, ring_teeth=90, planet_count=3)
    assert planetary_can_assemble(sun_teeth=30, ring_teeth=90, planet_count=4)
    assert not planetary_can_assemble(sun_teeth=30, ring_teeth=91, planet_count=3)
    with pytest.raises(ValueError, match="ring_teeth must exceed sun_teeth"):
        planetary_planet_teeth(sun_teeth=90, ring_teeth=30)
    with pytest.raises(ValueError, match="ring_teeth must exceed sun_teeth"):
        planetary_can_assemble(sun_teeth=90, ring_teeth=30, planet_count=3)


def test_planetary_speed_solves_the_willis_equation_each_way():
    teeth = {"sun_teeth": 30, "ring_teeth": 90}
    # Ring held, sun driven — the classic (1 + N_r/N_s):1 = 4:1 reducer,
    # carrier turning the same way as the sun.
    wc = planetary_speed(sun_speed=_q("1200 rpm"), ring_speed=_q("0 rpm"), **teeth)
    assert wc.to("rpm").magnitude == pytest.approx(300.0, rel=1e-9)
    # Carrier held, the train is an ordinary pair through the planets:
    # omega_r = -(N_s/N_r) * omega_s, and it matches gear_train_value with the
    # planet cancelling as an idler across one external + one internal mesh.
    wr = planetary_speed(sun_speed=_q("900 rpm"), carrier_speed=_q("0 rpm"), **teeth)
    assert wr.to("rpm").magnitude == pytest.approx(-300.0, rel=1e-9)
    e = gear_train_value(driver_teeth=[30, 30], driven_teeth=[30, 90], internal_meshes=1)
    assert wr.to("rpm").magnitude == pytest.approx(900 * e, rel=1e-9)
    # Sun held, ring driven: omega_c = N_r*omega_r/(N_r + N_s).
    wc2 = planetary_speed(sun_speed=_q("0 rpm"), ring_speed=_q("120 rpm"), **teeth)
    assert wc2.to("rpm").magnitude == pytest.approx(90.0, rel=1e-9)
    # Solving for the member just held recovers it: plug two results back in.
    ws = planetary_speed(carrier_speed=wc, ring_speed=_q("0 rpm"), **teeth)
    assert ws.to("rpm").magnitude == pytest.approx(1200.0, rel=1e-9)
    # Two members locked together lock the third: the train turns as a block.
    locked = planetary_speed(sun_speed=_q("500 rpm"), carrier_speed=_q("500 rpm"), **teeth)
    assert locked.to("rpm").magnitude == pytest.approx(500.0, rel=1e-9)
    # rad/s in, signed rpm out.
    wc3 = planetary_speed(sun_speed=_q("125.66370614359172 rad/s"), ring_speed=_q("0 rpm"), **teeth)
    assert wc3.to("rpm").magnitude == pytest.approx(300.0, rel=1e-6)


def test_planetary_speed_rejects_bad_inputs():
    with pytest.raises(ValueError, match="exactly one of sun_speed"):
        planetary_speed(sun_teeth=30, ring_teeth=90, sun_speed=_q("100 rpm"))
    with pytest.raises(ValueError, match="exactly one of sun_speed"):
        planetary_speed(
            sun_teeth=30,
            ring_teeth=90,
            sun_speed=_q("100 rpm"),
            carrier_speed=_q("50 rpm"),
            ring_speed=_q("0 rpm"),
        )
    with pytest.raises(ValueError, match="sun_speed must be a rotational-speed"):
        planetary_speed(sun_teeth=30, ring_teeth=90, sun_speed=_q("100 N"), ring_speed=_q("0 rpm"))
    with pytest.raises(ValueError, match="ring_teeth must exceed sun_teeth"):
        planetary_speed(
            sun_teeth=90, ring_teeth=30, sun_speed=_q("100 rpm"), ring_speed=_q("0 rpm")
        )
    with pytest.raises(ValueError, match="positive whole number of teeth"):
        planetary_speed(sun_teeth=0, ring_teeth=90, sun_speed=_q("100 rpm"), ring_speed=_q("0 rpm"))


def test_trapezoidal_curved_beam_reduces_to_rectangle_when_widths_match():
    # b_i = b_o collapses the trapezoid r_n integral to h/ln(ro/ri): the
    # trapezoidal solver must reproduce the rectangular one term for term.
    kw = {"inner_radius": _q("50 mm"), "outer_radius": _q("100 mm")}
    rect = rectangular_curved_beam_stress(moment=_q("500 N*m"), width=_q("20 mm"), **kw)
    trap = trapezoidal_curved_beam_stress(
        moment=_q("500 N*m"), inner_width=_q("20 mm"), outer_width=_q("20 mm"), **kw
    )
    assert trap.neutral_radius.to("mm").magnitude == pytest.approx(
        rect.neutral_radius.to("mm").magnitude, rel=1e-12
    )
    assert trap.inner_stress.to("MPa").magnitude == pytest.approx(
        rect.inner_stress.to("MPa").magnitude, rel=1e-12
    )
    assert trap.outer_stress.to("MPa").magnitude == pytest.approx(
        rect.outer_stress.to("MPa").magnitude, rel=1e-12
    )


def test_trapezoidal_curved_beam_hook_section_satisfies_equilibrium():
    from math import log

    # A crane-hook trapezoid: wide bore b_i=40, tapered back b_o=20, ri=50/ro=100,
    # opened by 500 N*m. Integrate sigma(r) over the varying width b(r) directly
    # and confirm Winkler's two conditions: zero net force, moment=M about rc.
    ri, ro, bi, bo, m = 50.0, 100.0, 40.0, 20.0, 500e3
    h = ro - ri
    area = h * (bi + bo) / 2.0
    rc = ri + h * (bi + 2.0 * bo) / (3.0 * (bi + bo))
    integral = ((bi * ro - bo * ri) / h) * log(ro / ri) - (bi - bo)
    rn = area / integral
    e = rc - rn
    result = trapezoidal_curved_beam_stress(
        moment=_q("500 N*m"),
        inner_radius=_q("50 mm"),
        outer_radius=_q("100 mm"),
        inner_width=_q("40 mm"),
        outer_width=_q("20 mm"),
    )
    assert result.neutral_radius.to("mm").magnitude == pytest.approx(rn, rel=1e-12)
    assert result.eccentricity.to("mm").magnitude == pytest.approx(e, rel=1e-12)
    # Numerically integrate with the linearly tapering width b(r).
    n = 400_000
    dr = h / n
    force = 0.0
    moment_about_centroid = 0.0
    for i in range(n):
        r = ri + (i + 0.5) * dr
        width = bi + (bo - bi) * (r - ri) / h
        sigma = m * (rn - r) / (area * e * r)
        force += sigma * width * dr
        moment_about_centroid += sigma * (r - rc) * width * dr
    assert abs(force) < 1e-6 * m / h
    assert -moment_about_centroid == pytest.approx(m, rel=1e-9)
    # The wide bore works hardest -- the whole point of the hook taper.
    assert abs(result.inner_stress.magnitude) > abs(result.outer_stress.magnitude)
    assert result.inner_stress.magnitude > 0 > result.outer_stress.magnitude


def test_trapezoidal_curved_beam_rejects_bad_widths():
    kw = {"inner_radius": _q("50 mm"), "outer_radius": _q("100 mm"), "moment": _q("500 N*m")}
    with pytest.raises(ValueError, match="at most one may be zero"):
        trapezoidal_curved_beam_stress(inner_width=_q("0 mm"), outer_width=_q("0 mm"), **kw)
    with pytest.raises(ValueError, match="at most one may be zero"):
        trapezoidal_curved_beam_stress(inner_width=_q("-10 mm"), outer_width=_q("20 mm"), **kw)
    # A pure triangle (one width zero) is allowed.
    tri = trapezoidal_curved_beam_stress(inner_width=_q("40 mm"), outer_width=_q("0 mm"), **kw)
    assert tri.inner_stress.magnitude > 0


def test_circular_curved_beam_stress_and_equilibrium():
    from math import pi, sqrt

    # A round bar (chain-link style): ri=50, ro=90 -> d=40, c=20, rc=70.
    # r_n = (rc + sqrt(rc^2 - c^2))/2, opened by 300 N*m.
    ri, ro, m = 50.0, 90.0, 300e3
    c = (ro - ri) / 2.0
    rc = (ri + ro) / 2.0
    rn = (rc + sqrt(rc**2 - c**2)) / 2.0
    e = rc - rn
    area = pi * c**2
    result = circular_curved_beam_stress(
        moment=_q("300 N*m"), inner_radius=_q("50 mm"), outer_radius=_q("90 mm")
    )
    assert result.neutral_radius.to("mm").magnitude == pytest.approx(rn, rel=1e-12)
    assert result.eccentricity.to("mm").magnitude == pytest.approx(e, rel=1e-12)
    inner = m * (rn - ri) / (area * e * ri)
    outer = m * (rn - ro) / (area * e * ro)
    assert result.inner_stress.to("MPa").magnitude == pytest.approx(inner, rel=1e-12)
    assert result.outer_stress.to("MPa").magnitude == pytest.approx(outer, rel=1e-12)
    # Integrate over the circular width b(r) = 2*sqrt(c^2 - (r - rc)^2): both
    # Winkler conditions must hold, which pins the closed-form r_n as correct.
    n = 400_000
    dr = (ro - ri) / n
    force = 0.0
    moment_about_centroid = 0.0
    for i in range(n):
        r = ri + (i + 0.5) * dr
        width = 2.0 * sqrt(max(c**2 - (r - rc) ** 2, 0.0))
        sigma = m * (rn - r) / (area * e * r)
        force += sigma * width * dr
        moment_about_centroid += sigma * (r - rc) * width * dr
    assert abs(force) < 1e-4 * m / (ro - ri)
    assert -moment_about_centroid == pytest.approx(m, rel=1e-4)
    assert abs(result.inner_stress.magnitude) > abs(result.outer_stress.magnitude)


def test_circular_curved_beam_rejects_bad_radii():
    with pytest.raises(ValueError, match="inner_radius must be positive"):
        circular_curved_beam_stress(
            moment=_q("300 N*m"), inner_radius=_q("0 mm"), outer_radius=_q("90 mm")
        )
    with pytest.raises(ValueError, match="must exceed inner_radius"):
        circular_curved_beam_stress(
            moment=_q("300 N*m"), inner_radius=_q("90 mm"), outer_radius=_q("90 mm")
        )


def test_planetary_torque_split_is_fixed_by_the_tooth_counts():
    # Sun 30 / ring 90: the ideal split is T_s : T_r : T_c = 30 : 90 : -120.
    # Drive the sun with 100 N*m -> ring reacts 300, carrier delivers -400.
    result = planetary_torques(
        sun_teeth=30, ring_teeth=90, input_member="sun", input_torque=_q("100 N*m")
    )
    assert result.sun_torque.to("N*m").magnitude == pytest.approx(100.0, rel=1e-12)
    assert result.ring_torque.to("N*m").magnitude == pytest.approx(300.0, rel=1e-12)
    assert result.carrier_torque.to("N*m").magnitude == pytest.approx(-400.0, rel=1e-12)
    # The three external torques balance the case: they sum to zero.
    total = (
        result.sun_torque.to("N*m").magnitude
        + result.ring_torque.to("N*m").magnitude
        + result.carrier_torque.to("N*m").magnitude
    )
    assert total == pytest.approx(0.0, abs=1e-9)
    # The carrier is the summing member: largest magnitude, opposite sign.
    assert abs(result.carrier_torque.magnitude) > abs(result.ring_torque.magnitude)
    assert abs(result.carrier_torque.magnitude) > abs(result.sun_torque.magnitude)


def test_planetary_torque_split_matches_the_speed_ratio_by_power():
    # Ideal power balance ties torque to speed: the sun-in/carrier-out reducer
    # multiplies torque by exactly the reciprocal of its speed ratio.
    teeth = {"sun_teeth": 30, "ring_teeth": 90}
    wc = planetary_speed(sun_speed=_q("1200 rpm"), ring_speed=_q("0 rpm"), **teeth)
    speed_ratio = wc.to("rpm").magnitude / 1200.0  # 300/1200 = 0.25
    torques = planetary_torques(input_member="sun", input_torque=_q("100 N*m"), **teeth)
    # |T_carrier| / |T_sun| = 1 / speed_ratio (4:1), the loss-free lever.
    assert abs(torques.carrier_torque.to("N*m").magnitude) / 100.0 == pytest.approx(
        1.0 / speed_ratio, rel=1e-12
    )
    # Driving the ring instead scales everything through its tooth count.
    ring_driven = planetary_torques(input_member="ring", input_torque=_q("300 N*m"), **teeth)
    assert ring_driven.sun_torque.to("N*m").magnitude == pytest.approx(100.0, rel=1e-12)
    assert ring_driven.carrier_torque.to("N*m").magnitude == pytest.approx(-400.0, rel=1e-12)


def test_planetary_torques_rejects_bad_inputs():
    with pytest.raises(ValueError, match="input_member must be one of"):
        planetary_torques(
            sun_teeth=30, ring_teeth=90, input_member="planet", input_torque=_q("100 N*m")
        )
    with pytest.raises(ValueError, match="input_torque must be a"):
        planetary_torques(sun_teeth=30, ring_teeth=90, input_member="sun", input_torque=_q("100 N"))
    with pytest.raises(ValueError, match="ring_teeth must exceed sun_teeth"):
        planetary_torques(
            sun_teeth=90, ring_teeth=30, input_member="sun", input_torque=_q("100 N*m")
        )


def test_reverted_train_coaxial_constraint():
    # A reverted train needs both stages to span the same centre distance:
    # N_p1 + N_g1 == N_p2 + N_g2. 20/60 then 24/56 both total 80 -> coaxial,
    # and the two-stage ratio is (20/60)*(24/56) = 1/7.
    assert reverted_train_is_coaxial(
        first_pinion_teeth=20,
        first_gear_teeth=60,
        second_pinion_teeth=24,
        second_gear_teeth=56,
    )
    ratio = gear_train_value(driver_teeth=[20, 24], driven_teeth=[60, 56])
    assert ratio == pytest.approx((20 / 60) * (24 / 56))
    # Same ratios but a stage-two pair totalling 84, not 80: the output shaft
    # lands off-axis and the train will not revert.
    assert not reverted_train_is_coaxial(
        first_pinion_teeth=20,
        first_gear_teeth=60,
        second_pinion_teeth=28,
        second_gear_teeth=56,
    )
    with pytest.raises(ValueError, match="positive whole number of teeth"):
        reverted_train_is_coaxial(
            first_pinion_teeth=0,
            first_gear_teeth=60,
            second_pinion_teeth=24,
            second_gear_teeth=56,
        )


def test_bevel_gear_force_resolution_splits_the_separating_load():
    from math import atan2, cos, degrees, radians, sin, tan

    # A 20/40 right-angle bevel pair: the pinion's pitch cone is
    # gamma = atan(20/40) = 26.565 deg.
    gamma_deg = bevel_pitch_cone_angle(pinion_teeth=20, gear_teeth=40)
    assert gamma_deg == pytest.approx(degrees(atan2(20, 40)), rel=1e-12)
    assert gamma_deg == pytest.approx(26.565, rel=1e-4)
    wt = _q("2000 N")
    wr = bevel_gear_radial_load(tangential_load=wt, pressure_angle=20, pitch_cone_angle=gamma_deg)
    wa = bevel_gear_axial_load(tangential_load=wt, pressure_angle=20, pitch_cone_angle=gamma_deg)
    gamma = radians(gamma_deg)
    sep = 2000 * tan(radians(20))
    assert wr.to("N").magnitude == pytest.approx(sep * cos(gamma), rel=1e-12)
    assert wa.to("N").magnitude == pytest.approx(sep * sin(gamma), rel=1e-12)
    # The radial and thrust components resolve to the same separating force.
    combined = (wr.to("N").magnitude ** 2 + wa.to("N").magnitude ** 2) ** 0.5
    assert combined == pytest.approx(sep, rel=1e-12)
    # A flat cone (gamma = 0) is a spur gear: all radial, no thrust.
    spur_wr = bevel_gear_radial_load(tangential_load=wt, pressure_angle=20, pitch_cone_angle=0)
    spur_wa = bevel_gear_axial_load(tangential_load=wt, pressure_angle=20, pitch_cone_angle=0)
    assert spur_wr.to("N").magnitude == pytest.approx(sep, rel=1e-12)
    assert spur_wa.to("N").magnitude == pytest.approx(0.0, abs=1e-9)
    # The pinion's and gear's cone angles are complementary (sum to 90 deg).
    gear_gamma = bevel_pitch_cone_angle(pinion_teeth=40, gear_teeth=20)
    assert gamma_deg + gear_gamma == pytest.approx(90.0, rel=1e-12)


def test_bevel_gear_rejects_bad_inputs():
    with pytest.raises(ValueError, match="positive whole number of teeth"):
        bevel_pitch_cone_angle(pinion_teeth=0, gear_teeth=40)
    with pytest.raises(ValueError, match=r"pressure_angle \(degrees\) must lie in"):
        bevel_gear_radial_load(tangential_load=_q("2000 N"), pressure_angle=0, pitch_cone_angle=20)
    with pytest.raises(ValueError, match=r"pitch_cone_angle \(degrees\) must lie in"):
        bevel_gear_axial_load(tangential_load=_q("2000 N"), pressure_angle=20, pitch_cone_angle=90)


def test_worm_drive_ratio_lead_angle_efficiency_and_self_locking():
    from math import atan2, cos, degrees, pi, radians, tan

    # A single-start worm on a 40-tooth wheel reduces 40:1 in one mesh.
    assert worm_gear_ratio(worm_starts=1, gear_teeth=40) == pytest.approx(40.0)
    assert worm_gear_ratio(worm_starts=2, gear_teeth=40) == pytest.approx(20.0)
    # Lead angle: L = N_W*p_x = 20 mm wrapped around a 50 mm worm.
    lam_deg = worm_lead_angle(
        worm_starts=2, axial_pitch=_q("10 mm"), worm_pitch_diameter=_q("50 mm")
    )
    assert lam_deg == pytest.approx(degrees(atan2(20.0, pi * 50.0)), rel=1e-12)
    assert lam_deg == pytest.approx(7.256, rel=1e-3)
    # Efficiency (worm driving) at lambda=15 deg, mu=0.05, phi_n=14.5 deg.
    eta = worm_gear_efficiency(lead_angle=15, friction_coefficient=0.05, normal_pressure_angle=14.5)
    lam = radians(15)
    phi = radians(14.5)
    ref = (cos(phi) - 0.05 * tan(lam)) / (cos(phi) + 0.05 / tan(lam))
    assert eta == pytest.approx(ref, rel=1e-12)
    assert eta == pytest.approx(0.8268, rel=1e-3)
    # A frictionless mesh is perfectly efficient.
    assert worm_gear_efficiency(lead_angle=15, friction_coefficient=0.0) == pytest.approx(1.0)
    # A higher lead angle raises efficiency (multi-start worms drive harder).
    assert worm_gear_efficiency(lead_angle=25, friction_coefficient=0.05) > eta


def test_worm_self_locking_mirrors_the_lead_versus_friction_battle():
    # Fine lead (2.5 deg), modest friction (0.05): friction beats the lead ->
    # self-locking (mu >= cos(phi_n)*tan(lambda)).
    assert worm_is_self_locking(lead_angle=2.5, friction_coefficient=0.05)
    # Open the lead to 15 deg and the same friction can no longer hold it.
    assert not worm_is_self_locking(lead_angle=15, friction_coefficient=0.05)
    # A self-locking worm runs below 50% efficiency -- the price of holding load.
    eta = worm_gear_efficiency(lead_angle=2.5, friction_coefficient=0.05)
    assert eta < 0.5


def test_worm_drive_rejects_bad_inputs():
    with pytest.raises(ValueError, match="worm_starts must be a positive whole number"):
        worm_gear_ratio(worm_starts=0, gear_teeth=40)
    with pytest.raises(ValueError, match="gear_teeth must be a positive whole number"):
        worm_gear_ratio(worm_starts=1, gear_teeth=40.5)
    with pytest.raises(ValueError, match="axial_pitch must be positive"):
        worm_lead_angle(worm_starts=1, axial_pitch=_q("0 mm"), worm_pitch_diameter=_q("50 mm"))
    with pytest.raises(ValueError, match=r"lead_angle \(degrees\) must lie in"):
        worm_gear_efficiency(lead_angle=0, friction_coefficient=0.05)
    with pytest.raises(ValueError, match="friction_coefficient must be non-negative"):
        worm_is_self_locking(lead_angle=15, friction_coefficient=-0.1)


def test_composite_curved_beam_single_strip_reproduces_the_rectangle():
    # One strip is a plain rectangle: the composite must match term for term.
    rect = rectangular_curved_beam_stress(
        moment=_q("500 N*m"),
        inner_radius=_q("50 mm"),
        outer_radius=_q("100 mm"),
        width=_q("20 mm"),
    )
    comp = composite_curved_beam_stress(
        moment=_q("500 N*m"),
        strips=[(_q("20 mm"), _q("50 mm"), _q("100 mm"))],
    )
    assert comp.neutral_radius.to("mm").magnitude == pytest.approx(
        rect.neutral_radius.to("mm").magnitude, rel=1e-12
    )
    assert comp.inner_stress.to("MPa").magnitude == pytest.approx(
        rect.inner_stress.to("MPa").magnitude, rel=1e-12
    )
    assert comp.outer_stress.to("MPa").magnitude == pytest.approx(
        rect.outer_stress.to("MPa").magnitude, rel=1e-12
    )
    # Splitting the same rectangle into two stacked strips changes nothing.
    split = composite_curved_beam_stress(
        moment=_q("500 N*m"),
        strips=[
            (_q("20 mm"), _q("50 mm"), _q("75 mm")),
            (_q("20 mm"), _q("75 mm"), _q("100 mm")),
        ],
    )
    assert split.inner_stress.to("MPa").magnitude == pytest.approx(
        rect.inner_stress.to("MPa").magnitude, rel=1e-12
    )


def test_composite_curved_beam_t_section_satisfies_equilibrium():
    from math import log

    # A T-section curved beam: a wide flange (b=60, 10 mm deep) at the bore and a
    # narrow web (b=20, 40 mm deep) behind it, ri=50, opened by 800 N*m.
    strips = [(60.0, 50.0, 60.0), (20.0, 60.0, 100.0)]
    m = 800e3
    area = sum(b * (ro - ri) for b, ri, ro in strips)
    integral = sum(b * log(ro / ri) for b, ri, ro in strips)
    first_moment = sum(b * (ro - ri) * (ri + ro) / 2.0 for b, ri, ro in strips)
    rn = area / integral
    rc = first_moment / area
    e = rc - rn
    result = composite_curved_beam_stress(
        moment=_q("800 N*m"),
        strips=[
            (_q("60 mm"), _q("50 mm"), _q("60 mm")),
            (_q("20 mm"), _q("60 mm"), _q("100 mm")),
        ],
    )
    assert result.neutral_radius.to("mm").magnitude == pytest.approx(rn, rel=1e-12)
    assert result.eccentricity.to("mm").magnitude == pytest.approx(e, rel=1e-12)
    # Integrate the field over the piecewise-constant width: Winkler's two
    # conditions (zero net force, moment = M about the centroid) must hold, which
    # validates the composite r_n and r_c from first principles.
    ri_all, ro_all = 50.0, 100.0
    n = 400_000
    dr = (ro_all - ri_all) / n
    force = 0.0
    moment_about_centroid = 0.0
    for i in range(n):
        r = ri_all + (i + 0.5) * dr
        width = 60.0 if r < 60.0 else 20.0
        sigma = m * (rn - r) / (area * e * r)
        force += sigma * width * dr
        moment_about_centroid += sigma * (r - rc) * width * dr
    assert abs(force) < 1e-6 * m / (ro_all - ri_all)
    assert -moment_about_centroid == pytest.approx(m, rel=1e-6)
    # Bore in tension, back in compression, matching the hand calc.
    assert result.inner_stress.to("MPa").magnitude == pytest.approx(59.44, rel=1e-3)
    assert result.outer_stress.to("MPa").magnitude == pytest.approx(-62.15, rel=1e-3)
    # With the flange at the bore, the neutral axis shifts inward and the *back*
    # fibre works hardest -- the opposite of the plain rectangle.
    assert abs(result.outer_stress.magnitude) > abs(result.inner_stress.magnitude)


def test_composite_curved_beam_rejects_bad_strips():
    with pytest.raises(ValueError, match="at least one"):
        composite_curved_beam_stress(moment=_q("500 N*m"), strips=[])
    with pytest.raises(ValueError, match="radially contiguous"):
        composite_curved_beam_stress(
            moment=_q("500 N*m"),
            strips=[
                (_q("60 mm"), _q("50 mm"), _q("60 mm")),
                (_q("20 mm"), _q("70 mm"), _q("100 mm")),  # gap 60 -> 70
            ],
        )
    with pytest.raises(ValueError, match="width must be positive"):
        composite_curved_beam_stress(
            moment=_q("500 N*m"), strips=[(_q("0 mm"), _q("50 mm"), _q("100 mm"))]
        )


def test_worm_tangential_force_from_the_power_balance():
    from math import radians, tan

    # W_Wt = W_Gt*tan(lambda)/eta: friction raises the input force by 1/eta.
    wgt = _q("4000 N")
    lam = 15.0
    eta = worm_gear_efficiency(
        lead_angle=lam, friction_coefficient=0.05, normal_pressure_angle=14.5
    )
    wwt = worm_tangential_force(gear_tangential_load=wgt, lead_angle=lam, friction_coefficient=0.05)
    assert wwt.to("N").magnitude == pytest.approx(4000 * tan(radians(lam)) / eta, rel=1e-12)
    # A frictionless mesh needs exactly W_Gt*tan(lambda) -- the pure geometry.
    frictionless = worm_tangential_force(
        gear_tangential_load=wgt, lead_angle=lam, friction_coefficient=0.0
    )
    assert frictionless.to("N").magnitude == pytest.approx(4000 * tan(radians(lam)), rel=1e-12)
    # Friction always costs more input force than the frictionless floor.
    assert wwt.to("N").magnitude > frictionless.to("N").magnitude
    with pytest.raises(ValueError, match="gear_tangential_load must be a"):
        worm_tangential_force(
            gear_tangential_load=_q("4000 N*m"), lead_angle=lam, friction_coefficient=0.05
        )


def test_worm_separating_force_from_the_tooth_normal_force():
    from math import cos, radians, sin

    # W_r = W_Gt*sin(phi_n)/(cos(phi_n)*cos(lambda) - mu*sin(lambda)).
    lam, phi_n, mu = 15.0, 20.0, 0.05
    wr = worm_separating_force(
        gear_tangential_load=_q("1000 N"),
        lead_angle=lam,
        friction_coefficient=mu,
        normal_pressure_angle=phi_n,
    )
    expected = (
        1000
        * sin(radians(phi_n))
        / (cos(radians(phi_n)) * cos(radians(lam)) - mu * sin(radians(lam)))
    )
    assert wr.to("N").magnitude == pytest.approx(expected, rel=1e-12)
    assert wr.to("N").magnitude == pytest.approx(382.26, rel=1e-3)
    # The force triple is consistent with the module's efficiency (already tested
    # elsewhere); a zero-pressure-angle tooth separates nothing.
    zero = worm_separating_force(
        gear_tangential_load=_q("1000 N"),
        lead_angle=lam,
        friction_coefficient=mu,
        normal_pressure_angle=0.0,
    )
    assert zero.to("N").magnitude == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(ValueError, match="gear_tangential_load must be a"):
        worm_separating_force(
            gear_tangential_load=_q("1000 N*m"), lead_angle=lam, friction_coefficient=mu
        )


def test_chain_length_in_pitches_and_chordal_speed_variation():
    from math import cos, pi

    # A 17/34 sprocket pair, 25.4 mm pitch (ANSI #80), 600 mm centres.
    # C_p = 600/25.4 = 23.622 pitches; the formula gives the exact link count.
    lp = chain_length_in_pitches(
        small_sprocket_teeth=17,
        large_sprocket_teeth=34,
        center_distance=_q("600 mm"),
        chain_pitch=_q("25.4 mm"),
    )
    cp = 600.0 / 25.4
    expected = 2.0 * cp + (17 + 34) / 2.0 + ((34 - 17) / (2.0 * pi)) ** 2 / cp
    assert lp == pytest.approx(expected, rel=1e-12)
    assert lp == pytest.approx(73.05, rel=1e-3)  # rounds up to 74 (even) links
    # An equal-sprocket drive drops the ((N2-N1)/2pi)^2 term entirely.
    equal = chain_length_in_pitches(
        small_sprocket_teeth=20,
        large_sprocket_teeth=20,
        center_distance=_q("508 mm"),
        chain_pitch=_q("25.4 mm"),
    )
    assert equal == pytest.approx(2.0 * (508.0 / 25.4) + 20.0, rel=1e-12)
    # Chordal action: 1 - cos(pi/N), falling fast with tooth count.
    assert chordal_speed_variation(sprocket_teeth=11) == pytest.approx(1 - cos(pi / 11), rel=1e-12)
    assert chordal_speed_variation(sprocket_teeth=11) == pytest.approx(0.0405, rel=1e-2)
    assert chordal_speed_variation(sprocket_teeth=17) == pytest.approx(0.0170, rel=1e-2)
    # More teeth run smoother.
    assert chordal_speed_variation(sprocket_teeth=23) < chordal_speed_variation(sprocket_teeth=17)


def test_chain_drive_rejects_bad_inputs():
    with pytest.raises(ValueError, match="positive whole number of teeth"):
        chain_length_in_pitches(
            small_sprocket_teeth=0,
            large_sprocket_teeth=34,
            center_distance=_q("600 mm"),
            chain_pitch=_q("25.4 mm"),
        )
    with pytest.raises(ValueError, match="chain_pitch must be positive"):
        chain_length_in_pitches(
            small_sprocket_teeth=17,
            large_sprocket_teeth=34,
            center_distance=_q("600 mm"),
            chain_pitch=_q("0 mm"),
        )
    with pytest.raises(ValueError, match="center_distance must be a"):
        chain_length_in_pitches(
            small_sprocket_teeth=17,
            large_sprocket_teeth=34,
            center_distance=_q("600 N"),
            chain_pitch=_q("25.4 mm"),
        )
    with pytest.raises(ValueError, match="positive whole number of teeth"):
        chordal_speed_variation(sprocket_teeth=17.5)


def test_chain_speed_is_teeth_times_pitch_times_speed():
    from math import pi

    # v = N*p*n: a 17-tooth #80 (25.4 mm) sprocket at 300 rpm.
    v = chain_speed(sprocket_teeth=17, chain_pitch=_q("25.4 mm"), rotational_speed=_q("300 rpm"))
    rev_per_s = 300.0 / 60.0
    assert v.to("m/s").magnitude == pytest.approx(17 * 0.0254 * rev_per_s, rel=1e-9)
    assert v.to("m/s").magnitude == pytest.approx(2.159, rel=1e-3)
    # rad/s in gives the same answer (300 rpm = 31.4159 rad/s).
    v_rad = chain_speed(
        sprocket_teeth=17,
        chain_pitch=_q("25.4 mm"),
        rotational_speed=_q(f"{300 * 2 * pi / 60} rad/s"),
    )
    assert v_rad.to("m/s").magnitude == pytest.approx(v.to("m/s").magnitude, rel=1e-9)
    # It scales linearly with tooth count and pitch.
    assert chain_speed(
        sprocket_teeth=34, chain_pitch=_q("25.4 mm"), rotational_speed=_q("300 rpm")
    ).to("m/s").magnitude == pytest.approx(2 * v.to("m/s").magnitude, rel=1e-9)
    with pytest.raises(ValueError, match="rotational_speed must be a rotational-speed"):
        chain_speed(sprocket_teeth=17, chain_pitch=_q("25.4 mm"), rotational_speed=_q("300 N"))
    with pytest.raises(ValueError, match="rotational_speed must be positive"):
        chain_speed(sprocket_teeth=17, chain_pitch=_q("25.4 mm"), rotational_speed=_q("0 rpm"))


def test_cam_shm_profile_kinematics_and_finite_end_acceleration():
    from math import pi

    kw = {"rise": _q("20 mm"), "rise_angle": 90.0, "cam_speed": _q("600 rpm")}
    ell = 0.020
    beta = pi / 2.0
    omega = 600 * 2 * pi / 60.0
    # Start of the rise: no lift, no velocity, but a FINITE acceleration -- the
    # SHM jerk step that knocks a high-speed cam.
    start = cam_follower_motion(profile="shm", cam_angle=0.0, **kw)
    assert start.displacement.to("mm").magnitude == pytest.approx(0.0, abs=1e-12)
    assert start.velocity.to("m/s").magnitude == pytest.approx(0.0, abs=1e-12)
    a_start = (ell / 2.0) * (pi / beta) ** 2 * omega**2
    assert start.acceleration.to("m/s**2").magnitude == pytest.approx(a_start, rel=1e-9)
    assert start.acceleration.to("m/s**2").magnitude > 100.0
    # Midpoint: half the lift, peak velocity, zero acceleration.
    mid = cam_follower_motion(profile="shm", cam_angle=45.0, **kw)
    assert mid.displacement.to("mm").magnitude == pytest.approx(10.0, rel=1e-9)
    assert mid.velocity.to("m/s").magnitude == pytest.approx(
        (ell / 2.0) * (pi / beta) * omega, rel=1e-9
    )
    assert mid.acceleration.to("m/s**2").magnitude == pytest.approx(0.0, abs=1e-9)
    # End of the rise reaches the full lift.
    end = cam_follower_motion(profile="shm", cam_angle=90.0, **kw)
    assert end.displacement.to("mm").magnitude == pytest.approx(20.0, rel=1e-9)


def test_cam_cycloidal_profile_has_zero_acceleration_at_both_ends():
    from math import pi

    kw = {"rise": _q("20 mm"), "rise_angle": 90.0, "cam_speed": _q("600 rpm")}
    ell = 0.020
    beta = pi / 2.0
    omega = 600 * 2 * pi / 60.0
    # The cycloidal signature: acceleration eases to zero at start AND end, so it
    # mates to a dwell without a jump -- unlike SHM.
    start = cam_follower_motion(profile="cycloidal", cam_angle=0.0, **kw)
    end = cam_follower_motion(profile="cycloidal", cam_angle=90.0, **kw)
    assert start.acceleration.to("m/s**2").magnitude == pytest.approx(0.0, abs=1e-9)
    assert start.velocity.to("m/s").magnitude == pytest.approx(0.0, abs=1e-9)
    assert end.acceleration.to("m/s**2").magnitude == pytest.approx(0.0, abs=1e-9)
    assert end.velocity.to("m/s").magnitude == pytest.approx(0.0, abs=1e-9)
    assert end.displacement.to("mm").magnitude == pytest.approx(20.0, rel=1e-9)
    # Midpoint: half lift and peak velocity 2x the average slope (L/beta)*omega.
    mid = cam_follower_motion(profile="cycloidal", cam_angle=45.0, **kw)
    assert mid.displacement.to("mm").magnitude == pytest.approx(10.0, rel=1e-9)
    assert mid.velocity.to("m/s").magnitude == pytest.approx(2.0 * (ell / beta) * omega, rel=1e-9)
    # Cycloidal peaks acceleration higher than SHM (the price of smooth ends):
    # 2*pi*L/beta^2 * omega^2 at theta = beta/4.
    peak = cam_follower_motion(profile="cycloidal", cam_angle=22.5, **kw)
    assert peak.acceleration.to("m/s**2").magnitude == pytest.approx(
        (ell / beta**2) * 2.0 * pi * omega**2, rel=1e-9
    )
    shm_peak = (ell / 2.0) * (pi / beta) ** 2 * omega**2
    assert peak.acceleration.to("m/s**2").magnitude > shm_peak


def test_cam_follower_motion_rejects_bad_inputs():
    kw = {"rise": _q("20 mm"), "rise_angle": 90.0, "cam_speed": _q("600 rpm")}
    with pytest.raises(ValueError, match="profile must be one of"):
        cam_follower_motion(profile="polynomial", cam_angle=45.0, **kw)
    with pytest.raises(ValueError, match=r"cam_angle \(degrees\) must lie in"):
        cam_follower_motion(profile="shm", cam_angle=120.0, **kw)
    with pytest.raises(ValueError, match="rise_angle .* must be positive"):
        cam_follower_motion(
            profile="shm", cam_angle=0.0, rise=_q("20 mm"), rise_angle=0.0, cam_speed=_q("600 rpm")
        )
    with pytest.raises(ValueError, match="cam_speed must be a rotational-speed"):
        cam_follower_motion(
            profile="shm", cam_angle=45.0, rise=_q("20 mm"), rise_angle=90.0, cam_speed=_q("600 N")
        )
    with pytest.raises(ValueError, match="rise must be a"):
        cam_follower_motion(
            profile="shm", cam_angle=45.0, rise=_q("20 N"), rise_angle=90.0, cam_speed=_q("600 rpm")
        )


def test_cam_pressure_angle_and_base_circle_effect():
    from math import atan2, degrees

    # tan(phi) = (ds/dtheta - e)/(sqrt(r_b^2 - e^2) + s): on-centre follower,
    # ds/dtheta = 30 mm/rad, s = 10 mm, r_b = 40 mm -> ~30.96 deg.
    phi = cam_pressure_angle(
        lift_gradient=_q("30 mm"),
        follower_displacement=_q("10 mm"),
        base_circle_radius=_q("40 mm"),
    )
    assert phi.to("degree").magnitude == pytest.approx(degrees(atan2(30, 50)), rel=1e-12)
    assert phi.to("degree").magnitude == pytest.approx(30.964, rel=1e-3)
    # A larger base circle lowers the pressure angle (the usual fix for jamming).
    bigger = cam_pressure_angle(
        lift_gradient=_q("30 mm"),
        follower_displacement=_q("10 mm"),
        base_circle_radius=_q("80 mm"),
    )
    assert bigger.to("degree").magnitude < phi.to("degree").magnitude
    # A positive offset in the lift direction reduces the pressure angle on the rise.
    offset = cam_pressure_angle(
        lift_gradient=_q("30 mm"),
        follower_displacement=_q("10 mm"),
        base_circle_radius=_q("40 mm"),
        offset=_q("10 mm"),
    )
    assert offset.to("degree").magnitude < phi.to("degree").magnitude
    with pytest.raises(ValueError, match="offset .* must be smaller than the base_circle_radius"):
        cam_pressure_angle(
            lift_gradient=_q("30 mm"),
            follower_displacement=_q("10 mm"),
            base_circle_radius=_q("40 mm"),
            offset=_q("40 mm"),
        )


def test_cam_parabolic_profile_has_the_lowest_constant_acceleration():
    from math import pi

    kw = {"rise": _q("20 mm"), "rise_angle": 90.0, "cam_speed": _q("600 rpm")}
    ell = 0.020
    beta = pi / 2.0
    omega = 600 * 2 * pi / 60.0
    a_const = 4.0 * ell / beta**2 * omega**2
    # First half: constant +4L/beta^2 acceleration; velocity ramps linearly.
    quarter = cam_follower_motion(profile="parabolic", cam_angle=22.5, **kw)
    assert quarter.acceleration.to("m/s**2").magnitude == pytest.approx(a_const, rel=1e-9)
    assert quarter.displacement.to("mm").magnitude == pytest.approx(
        2.0 * 20.0 * 0.25**2, rel=1e-9
    )  # 2*L*u^2 at u=0.25 -> 2.5 mm
    # Midpoint: half lift, peak velocity 2L/beta*omega, acceleration flips sign.
    mid = cam_follower_motion(profile="parabolic", cam_angle=45.0, **kw)
    assert mid.displacement.to("mm").magnitude == pytest.approx(10.0, rel=1e-9)
    assert mid.velocity.to("m/s").magnitude == pytest.approx(2.0 * ell / beta * omega, rel=1e-9)
    # Second half: constant -4L/beta^2 deceleration.
    three_q = cam_follower_motion(profile="parabolic", cam_angle=67.5, **kw)
    assert three_q.acceleration.to("m/s**2").magnitude == pytest.approx(-a_const, rel=1e-9)
    # End reaches the full lift with zero velocity.
    end = cam_follower_motion(profile="parabolic", cam_angle=90.0, **kw)
    assert end.displacement.to("mm").magnitude == pytest.approx(20.0, rel=1e-9)
    assert end.velocity.to("m/s").magnitude == pytest.approx(0.0, abs=1e-9)
    # Parabolic peak acceleration is the lowest of the three profiles.
    shm_peak = (ell / 2.0) * (pi / beta) ** 2 * omega**2
    cyc_peak = (ell / beta**2) * 2.0 * pi * omega**2
    assert a_const < shm_peak < cyc_peak


def test_cam_poly345_profile_is_smooth_at_both_ends():
    from math import pi

    kw = {"rise": _q("20 mm"), "rise_angle": 90.0, "cam_speed": _q("600 rpm")}
    ell = 0.020
    beta = pi / 2.0
    omega = 600 * 2 * pi / 60.0
    # The 3-4-5 polynomial has zero velocity AND acceleration at both ends,
    # like cycloidal but with a polynomial (bounded-jerk) form.
    start = cam_follower_motion(profile="poly345", cam_angle=0.0, **kw)
    end = cam_follower_motion(profile="poly345", cam_angle=90.0, **kw)
    assert start.displacement.to("mm").magnitude == pytest.approx(0.0, abs=1e-12)
    assert start.velocity.to("m/s").magnitude == pytest.approx(0.0, abs=1e-12)
    assert start.acceleration.to("m/s**2").magnitude == pytest.approx(0.0, abs=1e-12)
    assert end.displacement.to("mm").magnitude == pytest.approx(20.0, rel=1e-9)
    assert end.velocity.to("m/s").magnitude == pytest.approx(0.0, abs=1e-9)
    assert end.acceleration.to("m/s**2").magnitude == pytest.approx(0.0, abs=1e-9)
    # Midpoint: half lift, and acceleration crosses zero there.
    mid = cam_follower_motion(profile="poly345", cam_angle=45.0, **kw)
    assert mid.displacement.to("mm").magnitude == pytest.approx(10.0, rel=1e-9)
    assert mid.acceleration.to("m/s**2").magnitude == pytest.approx(0.0, abs=1e-9)
    # Its peak acceleration sits between SHM and cycloidal (~5.77 L/beta^2 omega^2).
    peak = 0.0
    step = 0
    while step <= 90:
        a = abs(
            cam_follower_motion(profile="poly345", cam_angle=float(step), **kw)
            .acceleration.to("m/s**2")
            .magnitude
        )
        peak = max(peak, a)
        step += 1
    shm_peak = (ell / 2.0) * (pi / beta) ** 2 * omega**2
    cyc_peak = (ell / beta**2) * 2.0 * pi * omega**2
    assert shm_peak < peak < cyc_peak
    assert peak == pytest.approx(5.7735 * ell / beta**2 * omega**2, rel=1e-3)


def test_geneva_mechanism_geometry():
    from math import cos, pi, sin

    # A 4-slot Geneva indexes 90 deg per engagement.
    assert geneva_index_angle(slots=4) == pytest.approx(90.0)
    assert geneva_index_angle(slots=6) == pytest.approx(60.0)
    # Crank r = c*sin(pi/n), driven r = c*cos(pi/n): equal at n=4.
    rc = geneva_crank_radius(slots=4, center_distance=_q("100 mm"))
    rd = geneva_driven_radius(slots=4, center_distance=_q("100 mm"))
    assert rc.to("mm").magnitude == pytest.approx(100 * sin(pi / 4), rel=1e-12)
    assert rc.to("mm").magnitude == pytest.approx(70.711, rel=1e-4)
    assert rd.to("mm").magnitude == pytest.approx(rc.to("mm").magnitude, rel=1e-12)
    # More slots: the crank radius shrinks, the driven radius grows.
    rc6 = geneva_crank_radius(slots=6, center_distance=_q("100 mm"))
    rd6 = geneva_driven_radius(slots=6, center_distance=_q("100 mm"))
    assert rc6.to("mm").magnitude == pytest.approx(50.0, rel=1e-9)  # c*sin(30) = 50
    assert rd6.to("mm").magnitude == pytest.approx(100 * cos(pi / 6), rel=1e-12)
    assert rc6.to("mm").magnitude < rd6.to("mm").magnitude
    # The two radii are the legs of the right-angle engagement triangle.
    combined = (rc.to("mm").magnitude ** 2 + rd.to("mm").magnitude ** 2) ** 0.5
    assert combined == pytest.approx(100.0, rel=1e-12)


def test_geneva_rejects_too_few_slots():
    with pytest.raises(ValueError, match="whole number ≥ 3"):
        geneva_index_angle(slots=2)
    with pytest.raises(ValueError, match="whole number ≥ 3"):
        geneva_crank_radius(slots=4.5, center_distance=_q("100 mm"))
    with pytest.raises(ValueError, match="center_distance must be positive"):
        geneva_crank_radius(slots=4, center_distance=_q("0 mm"))
    with pytest.raises(ValueError, match="center_distance must be a"):
        geneva_driven_radius(slots=4, center_distance=_q("100 N"))


def test_slider_crank_displacement_spans_the_stroke():
    from math import sqrt

    kw = {"crank_radius": _q("50 mm"), "rod_length": _q("200 mm")}
    # TDC: zero displacement. BDC: the full stroke 2r = 100 mm.
    assert slider_crank_displacement(crank_angle=0.0, **kw).to("mm").magnitude == pytest.approx(
        0.0, abs=1e-12
    )
    assert slider_crank_displacement(crank_angle=180.0, **kw).to("mm").magnitude == pytest.approx(
        100.0, rel=1e-12
    )
    # At 90 deg: x = r + L - sqrt(L^2 - r^2).
    mid = slider_crank_displacement(crank_angle=90.0, **kw).to("mm").magnitude
    assert mid == pytest.approx(50.0 + 200.0 - sqrt(200.0**2 - 50.0**2), rel=1e-12)
    assert mid == pytest.approx(56.351, rel=1e-4)
    # The finite rod makes the first half-stroke longer than the second at 90 deg:
    # more than half the stroke is covered by the first quarter-turn.
    assert mid > 50.0


def test_slider_crank_velocity_is_zero_at_dead_centres():
    from math import cos, radians, sin, sqrt

    kw = {"crank_radius": _q("50 mm"), "rod_length": _q("200 mm"), "crank_speed": _q("1000 rpm")}
    # Velocity vanishes at both dead centres (the piston reverses there).
    assert slider_crank_velocity(crank_angle=0.0, **kw).to("m/s").magnitude == pytest.approx(
        0.0, abs=1e-12
    )
    assert slider_crank_velocity(crank_angle=180.0, **kw).to("m/s").magnitude == pytest.approx(
        0.0, abs=1e-9
    )
    # At 90 deg the cos term drops and v = omega*r.
    omega = 1000 * 2 * 3.141592653589793 / 60.0
    v90 = slider_crank_velocity(crank_angle=90.0, **kw).to("m/s").magnitude
    assert v90 == pytest.approx(omega * 0.050, rel=1e-9)
    # The exact form matches a direct evaluation at an arbitrary angle.
    theta = radians(60.0)
    root = sqrt(200.0**2 - (50.0 * sin(theta)) ** 2)
    ref = omega * 50.0 * sin(theta) * (1.0 + 50.0 * cos(theta) / root) / 1000.0
    v60 = slider_crank_velocity(crank_angle=60.0, **kw).to("m/s").magnitude
    assert v60 == pytest.approx(ref, rel=1e-12)


def test_slider_crank_rejects_short_rod_and_bad_inputs():
    with pytest.raises(ValueError, match="rod_length must exceed crank_radius"):
        slider_crank_displacement(
            crank_radius=_q("200 mm"), rod_length=_q("100 mm"), crank_angle=45.0
        )
    with pytest.raises(ValueError, match="crank_radius must be positive"):
        slider_crank_displacement(
            crank_radius=_q("0 mm"), rod_length=_q("200 mm"), crank_angle=45.0
        )
    with pytest.raises(ValueError, match="crank_speed must be a rotational-speed"):
        slider_crank_velocity(
            crank_radius=_q("50 mm"),
            rod_length=_q("200 mm"),
            crank_angle=45.0,
            crank_speed=_q("1000 N"),
        )


def test_slider_crank_acceleration_peaks_at_top_dead_centre():
    from math import radians

    kw = {"crank_radius": _q("50 mm"), "rod_length": _q("200 mm"), "crank_speed": _q("1000 rpm")}
    omega = 1000 * 2 * 3.141592653589793 / 60.0
    r, length = 0.050, 0.200
    # TDC: a = r*omega^2*(1 + r/L), the maximum (and the shaking-force peak).
    a_tdc = slider_crank_acceleration(crank_angle=0.0, **kw).to("m/s**2").magnitude
    assert a_tdc == pytest.approx(r * omega**2 * (1.0 + r / length), rel=1e-12)
    # BDC: a = -r*omega^2*(1 - r/L), smaller in magnitude -- the finite-rod asymmetry.
    a_bdc = slider_crank_acceleration(crank_angle=180.0, **kw).to("m/s**2").magnitude
    assert a_bdc == pytest.approx(-r * omega**2 * (1.0 - r / length), rel=1e-12)
    assert abs(a_tdc) > abs(a_bdc)
    # Independent check: finite-difference the velocity (dv/dt = dv/dtheta * omega)
    # at an arbitrary angle and confirm the closed-form acceleration matches.
    h = 1e-4  # degrees
    v_plus = slider_crank_velocity(crank_angle=70.0 + h, **kw).to("m/s").magnitude
    v_minus = slider_crank_velocity(crank_angle=70.0 - h, **kw).to("m/s").magnitude
    dv_dtheta = (v_plus - v_minus) / (2.0 * radians(h))
    fd_accel = dv_dtheta * omega
    a_70 = slider_crank_acceleration(crank_angle=70.0, **kw).to("m/s**2").magnitude
    assert a_70 == pytest.approx(fd_accel, rel=1e-6)
    with pytest.raises(ValueError, match="crank_speed must be a rotational-speed"):
        slider_crank_acceleration(
            crank_radius=_q("50 mm"),
            rod_length=_q("200 mm"),
            crank_angle=45.0,
            crank_speed=_q("1000 N"),
        )


def test_slider_crank_piston_side_thrust_from_rod_obliquity():
    from math import sqrt

    kw = {"crank_radius": _q("25 mm"), "rod_length": _q("100 mm")}  # L/r = 4
    # At theta = 90 deg the rod obliquity is largest: sin(phi) = r/L = 1/4, so the
    # side thrust is F*tan(phi) = F/sqrt(L^2/r^2 - 1) = F/sqrt(15).
    side = slider_crank_piston_side_thrust(axial_force=_q("1000 N"), crank_angle=90.0, **kw)
    assert side.to("N").magnitude == pytest.approx(1000 / sqrt(15), rel=1e-12)
    assert side.to("N").magnitude == pytest.approx(258.20, rel=1e-3)
    # The rod is aligned with the bore at the dead centres, so no side thrust.
    assert slider_crank_piston_side_thrust(axial_force=_q("1000 N"), crank_angle=0.0, **kw).to(
        "N"
    ).magnitude == pytest.approx(0.0, abs=1e-12)
    assert slider_crank_piston_side_thrust(axial_force=_q("1000 N"), crank_angle=180.0, **kw).to(
        "N"
    ).magnitude == pytest.approx(0.0, abs=1e-9)
    # A longer connecting rod (larger L/r) reduces the side thrust.
    longer = slider_crank_piston_side_thrust(
        axial_force=_q("1000 N"),
        crank_radius=_q("25 mm"),
        rod_length=_q("200 mm"),
        crank_angle=90.0,
    )
    assert longer.to("N").magnitude < side.to("N").magnitude
    with pytest.raises(ValueError, match="axial_force must be a"):
        slider_crank_piston_side_thrust(axial_force=_q("1000 N*m"), crank_angle=90.0, **kw)


def test_fourbar_grashof_classification():
    # Same four lengths, different shortest position -> different mechanism.
    # 30/90/80 sides with a 100 frame: s+l = 30+100 = 130 < 90+80 = 170 -> Grashof.
    crank_rocker = fourbar_type(
        ground=_q("100 mm"),
        input_link=_q("30 mm"),
        coupler=_q("90 mm"),
        output_link=_q("80 mm"),
    )
    assert crank_rocker == "crank-rocker"  # shortest is the input side link
    # Move the 30 mm link to the frame: both side links now rotate fully.
    double_crank = fourbar_type(
        ground=_q("30 mm"),
        input_link=_q("100 mm"),
        coupler=_q("90 mm"),
        output_link=_q("80 mm"),
    )
    assert double_crank == "double-crank"
    # Move the 30 mm link to the coupler: neither input nor output completes a turn.
    double_rocker = fourbar_type(
        ground=_q("100 mm"),
        input_link=_q("90 mm"),
        coupler=_q("30 mm"),
        output_link=_q("80 mm"),
    )
    assert double_rocker == "double-rocker"
    # s + l == p + q is the change-point case (10+9 == 8+... ): 11/9/7/... tuned.
    change = fourbar_type(
        ground=_q("10 mm"),
        input_link=_q("9 mm"),
        coupler=_q("8 mm"),
        output_link=_q("7 mm"),
    )
    assert change == "change-point"  # 7+10 == 8+9
    # s + l > p + q: no link rotates fully.
    triple = fourbar_type(
        ground=_q("11 mm"),
        input_link=_q("9 mm"),
        coupler=_q("7 mm"),
        output_link=_q("6 mm"),
    )
    assert triple == "triple-rocker"  # 6+11 = 17 > 7+9 = 16
    # is_grashof agrees: True through the change-point, False for the triple-rocker.
    assert is_grashof(
        ground=_q("100 mm"),
        input_link=_q("30 mm"),
        coupler=_q("90 mm"),
        output_link=_q("80 mm"),
    )
    assert is_grashof(
        ground=_q("10 mm"), input_link=_q("9 mm"), coupler=_q("8 mm"), output_link=_q("7 mm")
    )
    assert not is_grashof(
        ground=_q("11 mm"), input_link=_q("9 mm"), coupler=_q("7 mm"), output_link=_q("6 mm")
    )


def test_fourbar_rejects_non_closable_and_bad_inputs():
    # The longest link exceeds the sum of the other three: cannot close.
    with pytest.raises(ValueError, match="closable four-bar"):
        fourbar_type(
            ground=_q("100 mm"),
            input_link=_q("20 mm"),
            coupler=_q("15 mm"),
            output_link=_q("10 mm"),
        )
    with pytest.raises(ValueError, match="link length must be positive"):
        is_grashof(
            ground=_q("0 mm"), input_link=_q("30 mm"), coupler=_q("90 mm"), output_link=_q("80 mm")
        )
    with pytest.raises(ValueError, match="link must be a"):
        is_grashof(
            ground=_q("100 N"),
            input_link=_q("30 mm"),
            coupler=_q("90 mm"),
            output_link=_q("80 mm"),
        )


def test_fourbar_transmission_angle_law_of_cosines():
    from math import acos, cos, degrees, radians, sqrt

    kw = {
        "ground": _q("100 mm"),
        "input_link": _q("40 mm"),
        "coupler": _q("100 mm"),
        "output_link": _q("40 mm"),
    }
    # Parallelogram linkage: at input 90 deg the transmission angle is exactly 90.
    assert fourbar_transmission_angle(input_angle=90.0, **kw) == pytest.approx(90.0, rel=1e-9)
    # At an arbitrary input angle it matches a direct law-of-cosines evaluation.
    theta = radians(120.0)
    diag = sqrt(100.0**2 + 40.0**2 - 2.0 * 100.0 * 40.0 * cos(theta))
    ref = degrees(acos((100.0**2 + 40.0**2 - diag**2) / (2.0 * 100.0 * 40.0)))
    assert fourbar_transmission_angle(input_angle=120.0, **kw) == pytest.approx(ref, rel=1e-12)
    # A crank-rocker's transmission angle stays away from 0/180 in its mid-range
    # but degrades toward the extremes -- here it is healthiest near mid-travel.
    mid = fourbar_transmission_angle(
        ground=_q("100 mm"),
        input_link=_q("30 mm"),
        coupler=_q("90 mm"),
        output_link=_q("80 mm"),
        input_angle=90.0,
    )
    assert 40.0 < mid < 140.0


def test_fourbar_transmission_angle_rejects_unreachable_pose():
    # A crank-rocker cannot make a full input turn: some input angles are
    # unreachable, and the diagonal then exceeds coupler + output.
    with pytest.raises(ValueError, match="cannot assemble at input_angle"):
        # At 180 deg the input points away from the output pivot, so the diagonal
        # r1 + r2 = 180 mm outreaches coupler + output = 70 mm.
        fourbar_transmission_angle(
            ground=_q("100 mm"),
            input_link=_q("80 mm"),
            coupler=_q("30 mm"),
            output_link=_q("40 mm"),
            input_angle=180.0,
        )


def test_scotch_yoke_is_pure_simple_harmonic_motion():
    kw = {"crank_radius": _q("50 mm")}
    vkw = {"crank_radius": _q("50 mm"), "crank_speed": _q("1000 rpm")}
    omega = 1000 * 2 * 3.141592653589793 / 60.0
    # Displacement 0 -> 2r over half a turn.
    assert scotch_yoke_displacement(crank_angle=0.0, **kw).to("mm").magnitude == pytest.approx(
        0.0, abs=1e-12
    )
    assert scotch_yoke_displacement(crank_angle=90.0, **kw).to("mm").magnitude == pytest.approx(
        50.0, rel=1e-12
    )
    assert scotch_yoke_displacement(crank_angle=180.0, **kw).to("mm").magnitude == pytest.approx(
        100.0, rel=1e-12
    )
    # Velocity: zero at dead centres, omega*r at mid-stroke.
    assert scotch_yoke_velocity(crank_angle=0.0, **vkw).to("m/s").magnitude == pytest.approx(
        0.0, abs=1e-12
    )
    assert scotch_yoke_velocity(crank_angle=90.0, **vkw).to("m/s").magnitude == pytest.approx(
        omega * 0.050, rel=1e-12
    )
    # Acceleration: a pure cosine with EQUAL peak magnitude at both dead centres --
    # the symmetry the finite-rod slider-crank lacks.
    a_tdc = scotch_yoke_acceleration(crank_angle=0.0, **vkw).to("m/s**2").magnitude
    a_bdc = scotch_yoke_acceleration(crank_angle=180.0, **vkw).to("m/s**2").magnitude
    assert a_tdc == pytest.approx(omega**2 * 0.050, rel=1e-12)
    assert a_bdc == pytest.approx(-a_tdc, rel=1e-12)


def test_scotch_yoke_is_the_infinite_rod_slider_crank_limit():
    # As the connecting rod grows the slider-crank velocity approaches the scotch
    # yoke's pure sinusoid: a huge rod makes them agree closely at 70 deg.
    sy = scotch_yoke_velocity(
        crank_radius=_q("50 mm"), crank_angle=70.0, crank_speed=_q("1000 rpm")
    )
    sc = slider_crank_velocity(
        crank_radius=_q("50 mm"),
        rod_length=_q("500000 mm"),
        crank_angle=70.0,
        crank_speed=_q("1000 rpm"),
    )
    assert sc.to("m/s").magnitude == pytest.approx(sy.to("m/s").magnitude, rel=1e-4)


def test_scotch_yoke_rejects_bad_inputs():
    with pytest.raises(ValueError, match="crank_radius must be positive"):
        scotch_yoke_displacement(crank_radius=_q("0 mm"), crank_angle=45.0)
    with pytest.raises(ValueError, match="crank_speed must be a rotational-speed"):
        scotch_yoke_velocity(crank_radius=_q("50 mm"), crank_angle=45.0, crank_speed=_q("1000 N"))


def test_gear_train_efficiency_compounds_the_mesh_losses():
    # Losses compound: four 98%-efficient meshes keep 0.98^4 ~= 92.2%.
    assert gear_train_efficiency(mesh_efficiencies=[0.98, 0.98, 0.98, 0.98]) == pytest.approx(
        0.98**4, rel=1e-12
    )
    assert gear_train_efficiency(mesh_efficiencies=[0.98] * 4) == pytest.approx(0.9224, rel=1e-3)
    # A single perfect mesh keeps everything; one poor worm mesh dominates.
    assert gear_train_efficiency(mesh_efficiencies=[1.0]) == pytest.approx(1.0)
    assert gear_train_efficiency(mesh_efficiencies=[0.99, 0.45]) == pytest.approx(0.4455, rel=1e-4)
    with pytest.raises(ValueError, match="at least one mesh"):
        gear_train_efficiency(mesh_efficiencies=[])
    with pytest.raises(ValueError, match=r"each mesh efficiency must lie in \(0, 1\]"):
        gear_train_efficiency(mesh_efficiencies=[0.98, 1.2])
    with pytest.raises(ValueError, match=r"each mesh efficiency must lie in \(0, 1\]"):
        gear_train_efficiency(mesh_efficiencies=[0.0])


def test_perry_robertson_perfect_column_recovers_yield_or_euler():
    from math import pi, sqrt

    E = _q("200 GPa")
    sy = _q("250 MPa")
    # Perfect column (eta = 0): fails at min(sigma_y, sigma_euler).
    # Slender (lambda=150): sigma_e = pi^2*E/lambda^2 = 87.7 MPa < 250 -> Euler governs.
    se_slender = pi**2 * 200000.0 / 150.0**2
    slender = perry_robertson_stress(
        yield_strength=sy, elastic_modulus=E, slenderness_ratio=150.0, imperfection_factor=0.0
    )
    assert slender.to("MPa").magnitude == pytest.approx(se_slender, rel=1e-9)
    assert slender.to("MPa").magnitude == pytest.approx(87.73, rel=1e-3)
    # Stocky (lambda=30): sigma_e = 2193 MPa >> 250 -> yield governs.
    stocky = perry_robertson_stress(
        yield_strength=sy, elastic_modulus=E, slenderness_ratio=30.0, imperfection_factor=0.0
    )
    assert stocky.to("MPa").magnitude == pytest.approx(250.0, rel=1e-6)
    # An imperfection (eta > 0) knocks the capacity below the perfect value, and
    # matches a direct evaluation of the interaction quadratic's lower root.
    se = pi**2 * 200000.0 / 100.0**2
    b = 250.0 + 1.2 * se
    ref = 0.5 * (b - sqrt(b**2 - 4.0 * 250.0 * se))
    imperfect = perry_robertson_stress(
        yield_strength=sy, elastic_modulus=E, slenderness_ratio=100.0, imperfection_factor=0.2
    )
    assert imperfect.to("MPa").magnitude == pytest.approx(ref, rel=1e-12)
    perfect = perry_robertson_stress(
        yield_strength=sy, elastic_modulus=E, slenderness_ratio=100.0, imperfection_factor=0.0
    )
    assert imperfect.to("MPa").magnitude < perfect.to("MPa").magnitude


def test_perry_robertson_rejects_bad_inputs():
    with pytest.raises(ValueError, match="slenderness_ratio must be positive"):
        perry_robertson_stress(
            yield_strength=_q("250 MPa"),
            elastic_modulus=_q("200 GPa"),
            slenderness_ratio=0.0,
            imperfection_factor=0.2,
        )
    with pytest.raises(ValueError, match="imperfection_factor must be non-negative"):
        perry_robertson_stress(
            yield_strength=_q("250 MPa"),
            elastic_modulus=_q("200 GPa"),
            slenderness_ratio=100.0,
            imperfection_factor=-0.1,
        )


def test_rotating_rim_hoop_stress_and_burst_speed_round_trip():
    steel = _q("7850 kg/m**3")
    # sigma = rho*v^2: a 0.3 m steel rim at 3000 rpm (v = 94.25 m/s).
    sigma = rotating_rim_hoop_stress(
        density=steel, mean_radius=_q("0.3 m"), rotational_speed=_q("3000 rpm")
    )
    v = (3000 * 2 * 3.141592653589793 / 60.0) * 0.3
    assert sigma.to("MPa").magnitude == pytest.approx(7850 * v**2 / 1e6, rel=1e-9)
    assert sigma.to("MPa").magnitude == pytest.approx(69.73, rel=1e-3)
    # Stress rides on rim SPEED, not thickness: it is independent of the rim mass.
    # Doubling the radius at the same rpm quadruples the stress (v doubles).
    bigger = rotating_rim_hoop_stress(
        density=steel, mean_radius=_q("0.6 m"), rotational_speed=_q("3000 rpm")
    )
    assert bigger.to("MPa").magnitude == pytest.approx(4.0 * sigma.to("MPa").magnitude, rel=1e-9)
    # Burst speed inverts it: the hoop stress at the burst speed equals the allowable.
    burst = rotating_rim_burst_speed(
        allowable_stress=_q("200 MPa"), density=steel, mean_radius=_q("0.3 m")
    )
    assert burst.to("rpm").magnitude == pytest.approx(5080.8, rel=1e-3)
    at_burst = rotating_rim_hoop_stress(
        density=steel, mean_radius=_q("0.3 m"), rotational_speed=burst
    )
    assert at_burst.to("MPa").magnitude == pytest.approx(200.0, rel=1e-9)


def test_rotating_rim_rejects_bad_inputs():
    with pytest.raises(ValueError, match="rotational_speed must be positive"):
        rotating_rim_hoop_stress(
            density=_q("7850 kg/m**3"), mean_radius=_q("0.3 m"), rotational_speed=_q("0 rpm")
        )
    with pytest.raises(ValueError, match="density must be a"):
        rotating_rim_hoop_stress(
            density=_q("7850 kg"), mean_radius=_q("0.3 m"), rotational_speed=_q("3000 rpm")
        )
    with pytest.raises(ValueError, match="mean_radius must be positive"):
        rotating_rim_burst_speed(
            allowable_stress=_q("200 MPa"), density=_q("7850 kg/m**3"), mean_radius=_q("0 m")
        )


def test_parabolic_cable_sag_and_max_tension():
    from math import sqrt

    kw = {"weight_per_length": _q("10 N/m"), "span": _q("100 m")}
    # d = w*L^2/(8H): 10 N/m over 100 m at 5000 N -> 2.5 m sag.
    sag = parabolic_cable_sag(horizontal_tension=_q("5000 N"), **kw)
    assert sag.to("m").magnitude == pytest.approx(10 * 100**2 / (8 * 5000), rel=1e-12)
    assert sag.to("m").magnitude == pytest.approx(2.5, rel=1e-12)
    # A taut cable is a high-tension cable: doubling H halves the sag.
    tauter = parabolic_cable_sag(horizontal_tension=_q("10000 N"), **kw)
    assert tauter.to("m").magnitude == pytest.approx(1.25, rel=1e-12)
    # T_max = sqrt(H^2 + (wL/2)^2), always above H.
    tmax = parabolic_cable_max_tension(horizontal_tension=_q("5000 N"), **kw)
    assert tmax.to("N").magnitude == pytest.approx(sqrt(5000**2 + (10 * 100 / 2) ** 2), rel=1e-12)
    assert tmax.to("N").magnitude == pytest.approx(5024.94, rel=1e-4)
    assert tmax.to("N").magnitude > 5000.0


def test_parabolic_cable_rejects_bad_inputs():
    with pytest.raises(ValueError, match="horizontal_tension must be positive"):
        parabolic_cable_sag(
            weight_per_length=_q("10 N/m"), span=_q("100 m"), horizontal_tension=_q("0 N")
        )
    with pytest.raises(ValueError, match="span must be positive"):
        parabolic_cable_sag(
            weight_per_length=_q("10 N/m"), span=_q("0 m"), horizontal_tension=_q("5000 N")
        )
    with pytest.raises(ValueError, match="weight_per_length must be a"):
        parabolic_cable_max_tension(
            weight_per_length=_q("10 N"), span=_q("100 m"), horizontal_tension=_q("5000 N")
        )


def test_parabolic_cable_length_exceeds_the_span():
    # S = L + 8d^2/(3L): 100 m span with 2.5 m sag -> 100.167 m of cable.
    s = parabolic_cable_length(span=_q("100 m"), sag=_q("2.5 m"))
    assert s.to("m").magnitude == pytest.approx(100.0 + 8 * 2.5**2 / (3 * 100.0), rel=1e-12)
    assert s.to("m").magnitude == pytest.approx(100.1667, rel=1e-4)
    assert s.to("m").magnitude > 100.0
    # The extra length grows with the square of the sag: doubling sag quadruples it.
    s2 = parabolic_cable_length(span=_q("100 m"), sag=_q("5 m"))
    assert (s2.to("m").magnitude - 100.0) == pytest.approx(
        4.0 * (s.to("m").magnitude - 100.0), rel=1e-12
    )
    with pytest.raises(ValueError, match="sag must be positive"):
        parabolic_cable_length(span=_q("100 m"), sag=_q("0 m"))


def test_catenary_matches_hyperbolic_forms_and_the_shallow_parabola():
    from math import cosh, sinh

    kw = {
        "weight_per_length": _q("10 N/m"),
        "span": _q("100 m"),
        "horizontal_tension": _q("1000 N"),
    }
    a = 1000.0 / 10.0  # catenary parameter H/w = 100 m
    x = 50.0  # half-span
    sag = catenary_sag(**kw)
    arc = catenary_arc_length(**kw)
    tmax = catenary_max_tension(**kw)
    assert sag.to("m").magnitude == pytest.approx(a * (cosh(x / a) - 1.0), rel=1e-12)
    assert sag.to("m").magnitude == pytest.approx(12.7626, rel=1e-4)
    assert arc.to("m").magnitude == pytest.approx(2.0 * a * sinh(x / a), rel=1e-12)
    # Peak tension is H + w*d exactly (the horizontal pull plus the hung weight).
    assert tmax.to("N").magnitude == pytest.approx(1000.0 + 10.0 * sag.to("m").magnitude, rel=1e-12)
    # In the shallow-sag limit the catenary collapses onto the parabola: a taut
    # cable (large H) sags almost exactly w*L^2/(8H).
    taut = {
        "weight_per_length": _q("10 N/m"),
        "span": _q("100 m"),
        "horizontal_tension": _q("100 kN"),
    }
    cat = catenary_sag(**taut).to("m").magnitude
    par = parabolic_cable_sag(**taut).to("m").magnitude
    assert cat == pytest.approx(par, rel=1e-3)
    with pytest.raises(ValueError, match="horizontal_tension must be positive"):
        catenary_sag(weight_per_length=_q("10 N/m"), span=_q("100 m"), horizontal_tension=_q("0 N"))


def test_spur_gear_contact_ratio_and_pressure_angle_effect():
    from math import cos, pi, radians, sin, sqrt

    # 20-tooth pinion, 40-tooth gear, module 1, 20 deg pressure angle, standard
    # full-depth (addendum = module). Recompute the standard formula directly.
    def cr(n1, n2, m, phi_deg):
        phi = radians(phi_deg)
        r1, r2 = m * n1 / 2, m * n2 / 2
        ra1, ra2 = r1 + m, r2 + m
        rb1, rb2 = r1 * cos(phi), r2 * cos(phi)
        z = sqrt(ra1**2 - rb1**2) + sqrt(ra2**2 - rb2**2) - (r1 + r2) * sin(phi)
        return z / (pi * m * cos(phi))

    mc = spur_gear_contact_ratio(
        module=_q("1 mm"), pinion_teeth=20, gear_teeth=40, pressure_angle=20.0
    )
    assert mc == pytest.approx(cr(20, 40, 1.0, 20.0), rel=1e-12)
    assert mc == pytest.approx(1.635, rel=1e-3)
    # Contact ratio must exceed 1 for continuous meshing.
    assert mc > 1.0
    # A larger pressure angle shortens the line of action and lowers the ratio.
    mc25 = spur_gear_contact_ratio(
        module=_q("1 mm"), pinion_teeth=20, gear_teeth=40, pressure_angle=25.0
    )
    assert mc25 < mc
    # Contact ratio is scale-free in the module (only the tooth counts and angle
    # matter): a 2 mm module gives the same ratio.
    mc2 = spur_gear_contact_ratio(
        module=_q("2 mm"), pinion_teeth=20, gear_teeth=40, pressure_angle=20.0
    )
    assert mc2 == pytest.approx(mc, rel=1e-12)


def test_spur_gear_contact_ratio_rejects_bad_inputs():
    with pytest.raises(ValueError, match="positive whole number of teeth"):
        spur_gear_contact_ratio(
            module=_q("1 mm"), pinion_teeth=0, gear_teeth=40, pressure_angle=20.0
        )
    with pytest.raises(ValueError, match=r"pressure_angle \(degrees\) must lie in"):
        spur_gear_contact_ratio(
            module=_q("1 mm"), pinion_teeth=20, gear_teeth=40, pressure_angle=0.0
        )
    with pytest.raises(ValueError, match="module must be positive"):
        spur_gear_contact_ratio(
            module=_q("0 mm"), pinion_teeth=20, gear_teeth=40, pressure_angle=20.0
        )


def test_minimum_teeth_to_avoid_undercut_matches_textbook_values():
    from math import ceil, radians, sin

    # Standard full-depth: 20 deg -> 18, 14.5 deg -> 32, 25 deg -> 12.
    assert minimum_teeth_to_avoid_undercut(pressure_angle=20.0) == 18
    assert minimum_teeth_to_avoid_undercut(pressure_angle=14.5) == 32
    assert minimum_teeth_to_avoid_undercut(pressure_angle=25.0) == 12
    # It is the ceiling of the exact 2k/sin^2(phi).
    assert minimum_teeth_to_avoid_undercut(pressure_angle=20.0) == ceil(
        2.0 / sin(radians(20.0)) ** 2
    )
    # A larger pressure angle allows fewer teeth; a stub tooth (k < 1) fewer still.
    assert minimum_teeth_to_avoid_undercut(pressure_angle=25.0) < minimum_teeth_to_avoid_undercut(
        pressure_angle=20.0
    )
    assert minimum_teeth_to_avoid_undercut(
        pressure_angle=20.0, addendum_coefficient=0.8
    ) < minimum_teeth_to_avoid_undercut(pressure_angle=20.0)
    with pytest.raises(ValueError, match=r"pressure_angle \(degrees\) must lie in"):
        minimum_teeth_to_avoid_undercut(pressure_angle=0.0)
    with pytest.raises(ValueError, match="addendum_coefficient must be positive"):
        minimum_teeth_to_avoid_undercut(pressure_angle=20.0, addendum_coefficient=0.0)


def test_involute_function_and_base_tangent_length():
    from math import cos, pi, radians, tan

    # inv(20 deg) = tan(20) - 20*pi/180 ~ 0.014904.
    inv20 = involute_function(pressure_angle=20.0)
    assert inv20 == pytest.approx(tan(radians(20)) - radians(20), rel=1e-12)
    assert inv20 == pytest.approx(0.0149044, rel=1e-5)
    # Base tangent length W_k = m*cos(phi)*[(k-0.5)*pi + z*inv(phi)] for a standard
    # m=2, z=20, 20 deg gear spanned over k=3 teeth: ~15.32 mm.
    w = base_tangent_length(module=_q("2 mm"), teeth=20, teeth_spanned=3, pressure_angle=20.0)
    phi = radians(20)
    expected = 2 * cos(phi) * ((3 - 0.5) * pi + 20 * (tan(phi) - phi))
    assert w.to("mm").magnitude == pytest.approx(expected, rel=1e-12)
    assert w.to("mm").magnitude == pytest.approx(15.3209, rel=1e-4)
    # Spanning one more tooth adds exactly one base pitch p_b = pi*m*cos(phi).
    w4 = base_tangent_length(module=_q("2 mm"), teeth=20, teeth_spanned=4, pressure_angle=20.0)
    assert (w4.to("mm").magnitude - w.to("mm").magnitude) == pytest.approx(
        pi * 2 * cos(phi), rel=1e-12
    )
    with pytest.raises(ValueError, match="teeth_spanned .* must be below teeth"):
        base_tangent_length(module=_q("2 mm"), teeth=20, teeth_spanned=20, pressure_angle=20.0)
    with pytest.raises(ValueError, match=r"pressure_angle \(degrees\) must lie in"):
        involute_function(pressure_angle=95.0)


def test_involute_angle_inverts_the_involute_function():
    # The Newton inverse recovers the angle to machine precision across the range.
    for deg in (10.0, 20.0, 25.0, 30.0, 45.0):
        value = involute_function(pressure_angle=deg)
        assert involute_angle(involute_value=value) == pytest.approx(deg, rel=1e-9)
    # inv(0) = 0 -> phi = 0.
    assert involute_angle(involute_value=0.0) == 0.0
    with pytest.raises(ValueError, match="involute_value must be non-negative"):
        involute_angle(involute_value=-0.01)


def test_gear_tooth_thickness_at_radius_thins_from_pitch_to_tip():
    from math import pi

    kw = {"module": _q("2 mm"), "teeth": 20, "pressure_angle": 20.0}
    # At the pitch radius (m*z/2 = 20 mm) it returns the reference thickness pi*m/2.
    at_pitch = gear_tooth_thickness_at_radius(radius=_q("20 mm"), **kw)
    assert at_pitch.to("mm").magnitude == pytest.approx(pi * 2 / 2, rel=1e-12)
    # At the tip (r = 22 mm) the tooth is thinner (the top land).
    at_tip = gear_tooth_thickness_at_radius(radius=_q("22 mm"), **kw)
    assert at_tip.to("mm").magnitude < at_pitch.to("mm").magnitude
    assert at_tip.to("mm").magnitude == pytest.approx(1.3898, rel=1e-3)
    # Inside the base circle there is no involute flank.
    with pytest.raises(ValueError, match="must be at least the base radius"):
        gear_tooth_thickness_at_radius(radius=_q("18 mm"), **kw)


def test_operating_pressure_angle_and_profile_shift():
    from math import acos, cos, radians, tan

    pair = {"module": _q("2 mm"), "pinion_teeth": 20, "gear_teeth": 40, "pressure_angle": 20.0}
    # cos(phi_w) = a*cos(phi)/a_w, a = m*(z1+z2)/2 = 60 mm; a_w = 61 mm -> ~22.44 deg.
    phi_w = operating_pressure_angle(operating_center_distance=_q("61 mm"), **pair)
    a = 2 * (20 + 40) / 2
    assert phi_w == pytest.approx(
        acos(a * cos(radians(20)) / 61) * 180 / 3.141592653589793, rel=1e-9
    )
    assert phi_w == pytest.approx(22.439, rel=1e-3)
    # At the standard centre the operating angle is the reference angle and the
    # required profile-shift sum is zero.
    assert operating_pressure_angle(operating_center_distance=_q("60 mm"), **pair) == pytest.approx(
        20.0, rel=1e-9
    )
    assert profile_shift_sum_for_center_distance(
        operating_center_distance=_q("60 mm"), **pair
    ) == pytest.approx(0.0, abs=1e-9)
    # Spreading the centres to 61 mm needs x1+x2 ~ 0.53.
    x_sum = profile_shift_sum_for_center_distance(operating_center_distance=_q("61 mm"), **pair)

    def inv(x):
        return tan(x) - x

    expected = (inv(radians(phi_w)) - inv(radians(20))) * 60 / (2 * tan(radians(20)))
    assert x_sum == pytest.approx(expected, rel=1e-9)
    assert x_sum == pytest.approx(0.5298, rel=1e-3)
    # Too small a centre distance overlaps the base circles.
    with pytest.raises(ValueError, match="below the base centre"):
        operating_pressure_angle(operating_center_distance=_q("50 mm"), **pair)


def test_helical_gear_axial_thrust_and_radial_load():
    from math import cos, radians, tan

    wt = _q("2000 N")
    # Axial thrust W_a = W_t*tan(psi): 30 deg helix -> 1154.7 N of thrust.
    wa = helical_gear_axial_thrust(tangential_load=wt, helix_angle=30.0)
    assert wa.to("N").magnitude == pytest.approx(2000 * tan(radians(30)), rel=1e-12)
    assert wa.to("N").magnitude == pytest.approx(1154.7, rel=1e-3)
    # A spur gear (psi = 0) makes no thrust; a steeper helix makes more.
    assert helical_gear_axial_thrust(tangential_load=wt, helix_angle=0.0).to(
        "N"
    ).magnitude == pytest.approx(0.0, abs=1e-12)
    assert (
        helical_gear_axial_thrust(tangential_load=wt, helix_angle=40.0).to("N").magnitude
        > wa.to("N").magnitude
    )
    # Radial load W_r = W_t*tan(phi_n)/cos(psi).
    wr = helical_gear_radial_load(tangential_load=wt, normal_pressure_angle=20.0, helix_angle=30.0)
    assert wr.to("N").magnitude == pytest.approx(
        2000 * tan(radians(20)) / cos(radians(30)), rel=1e-12
    )
    assert wr.to("N").magnitude == pytest.approx(840.4, rel=1e-3)
    # At psi = 0 the radial load reduces to the spur-gear value W_t*tan(phi_n).
    wr_spur = helical_gear_radial_load(
        tangential_load=wt, normal_pressure_angle=20.0, helix_angle=0.0
    )
    assert wr_spur.to("N").magnitude == pytest.approx(
        gear_radial_load(tangential_load=wt, pressure_angle=20.0).to("N").magnitude, rel=1e-12
    )


def test_helical_gear_rejects_bad_angles():
    with pytest.raises(ValueError, match=r"helix_angle \(degrees\) must lie in"):
        helical_gear_axial_thrust(tangential_load=_q("2000 N"), helix_angle=90.0)
    with pytest.raises(ValueError, match=r"pressure_angle \(degrees\) must lie in"):
        helical_gear_radial_load(
            tangential_load=_q("2000 N"), normal_pressure_angle=0.0, helix_angle=30.0
        )
    with pytest.raises(ValueError, match="tangential_load must be a"):
        helical_gear_axial_thrust(tangential_load=_q("2000 N*m"), helix_angle=30.0)


def test_helical_virtual_teeth_exceeds_the_actual_count():
    from math import cos, radians

    # N_v = N/cos^3(psi): a 20-tooth gear at a 30 deg helix cuts like a ~31-tooth
    # spur, so it is stronger in bending than its real count suggests.
    nv = helical_virtual_teeth(actual_teeth=20, helix_angle=30.0)
    assert nv == pytest.approx(20 / cos(radians(30)) ** 3, rel=1e-12)
    assert nv == pytest.approx(30.79, rel=1e-3)
    assert nv > 20
    # A spur gear (psi = 0) has virtual count equal to its actual count.
    assert helical_virtual_teeth(actual_teeth=20, helix_angle=0.0) == pytest.approx(20.0, rel=1e-12)
    # A steeper helix raises the virtual count further.
    assert helical_virtual_teeth(actual_teeth=20, helix_angle=45.0) > nv
    with pytest.raises(ValueError, match="positive whole number of teeth"):
        helical_virtual_teeth(actual_teeth=0, helix_angle=30.0)
    with pytest.raises(ValueError, match=r"helix_angle \(degrees\) must lie in"):
        helical_virtual_teeth(actual_teeth=20, helix_angle=90.0)


def test_elliptical_hole_stress_concentration_inglis():
    # Circular hole (a = b): the classic K_t = 3.
    kt_circle = elliptical_hole_stress_concentration(
        semi_axis_across_load=_q("5 mm"), semi_axis_along_load=_q("5 mm")
    )
    assert kt_circle == pytest.approx(3.0, rel=1e-12)
    # Stretched across the load (a = 2b): K_t = 1 + 2*2 = 5.
    kt_wide = elliptical_hole_stress_concentration(
        semi_axis_across_load=_q("10 mm"), semi_axis_along_load=_q("5 mm")
    )
    assert kt_wide == pytest.approx(5.0, rel=1e-12)
    assert kt_wide > kt_circle
    # A hole aligned with the load (a < b) is gentler, but never below 1.
    kt_slender = elliptical_hole_stress_concentration(
        semi_axis_across_load=_q("2 mm"), semi_axis_along_load=_q("10 mm")
    )
    assert kt_slender == pytest.approx(1.4, rel=1e-12)
    # A crack-like slit (b -> 0) drives K_t up without limit.
    kt_crack = elliptical_hole_stress_concentration(
        semi_axis_across_load=_q("10 mm"), semi_axis_along_load=_q("0.1 mm")
    )
    assert kt_crack == pytest.approx(201.0, rel=1e-12)
    # It composes with concentrated_stress: peak = K_t * nominal.
    peak = concentrated_stress(nominal_stress=_q("50 MPa"), kt=kt_circle)
    assert peak.to("MPa").magnitude == pytest.approx(150.0, rel=1e-12)


def test_elliptical_hole_rejects_bad_inputs():
    with pytest.raises(ValueError, match="semi_axis_across_load must be positive"):
        elliptical_hole_stress_concentration(
            semi_axis_across_load=_q("0 mm"), semi_axis_along_load=_q("5 mm")
        )
    with pytest.raises(ValueError, match="semi_axis_along_load must be a"):
        elliptical_hole_stress_concentration(
            semi_axis_across_load=_q("5 mm"), semi_axis_along_load=_q("5 N")
        )


def test_stress_intensity_and_critical_crack_length_round_trip():
    from math import pi, sqrt

    # K_I = Y*sigma*sqrt(pi*a): 100 MPa, 5 mm central crack, Y=1.
    ki = stress_intensity_factor(remote_stress=_q("100 MPa"), crack_length=_q("5 mm"))
    assert ki.to("MPa*m**0.5").magnitude == pytest.approx(100 * sqrt(pi * 0.005), rel=1e-12)
    assert ki.to("MPa*m**0.5").magnitude == pytest.approx(12.533, rel=1e-3)
    # An edge crack (Y=1.12) is more severe than a central one.
    ki_edge = stress_intensity_factor(
        remote_stress=_q("100 MPa"), crack_length=_q("5 mm"), geometry_factor=1.12
    )
    assert ki_edge.to("MPa*m**0.5").magnitude == pytest.approx(
        1.12 * ki.to("MPa*m**0.5").magnitude, rel=1e-12
    )
    # a_c = (K_IC/(Y*sigma))^2/pi: a 50 MPa-sqrt(m) steel at 100 MPa tolerates ~79.6 mm.
    ac = critical_crack_length(fracture_toughness=_q("50 MPa*m**0.5"), remote_stress=_q("100 MPa"))
    assert ac.to("mm").magnitude == pytest.approx((50 / 100) ** 2 / pi * 1000, rel=1e-12)
    assert ac.to("mm").magnitude == pytest.approx(79.58, rel=1e-3)
    # Round trip: the stress intensity at the critical length equals the toughness.
    ki_at_ac = stress_intensity_factor(remote_stress=_q("100 MPa"), crack_length=ac)
    assert ki_at_ac.to("MPa*m**0.5").magnitude == pytest.approx(50.0, rel=1e-9)
    # Halving the stress quadruples the tolerable crack length.
    ac_low = critical_crack_length(
        fracture_toughness=_q("50 MPa*m**0.5"), remote_stress=_q("50 MPa")
    )
    assert ac_low.to("mm").magnitude == pytest.approx(4 * ac.to("mm").magnitude, rel=1e-12)


def test_fracture_rejects_bad_inputs():
    with pytest.raises(ValueError, match="crack_length must be positive"):
        stress_intensity_factor(remote_stress=_q("100 MPa"), crack_length=_q("0 mm"))
    with pytest.raises(ValueError, match="geometry_factor must be positive"):
        stress_intensity_factor(
            remote_stress=_q("100 MPa"), crack_length=_q("5 mm"), geometry_factor=0.0
        )
    with pytest.raises(ValueError, match="fracture_toughness must be a"):
        critical_crack_length(fracture_toughness=_q("50 MPa"), remote_stress=_q("100 MPa"))


def test_paris_law_growth_rate_and_integrated_life():
    from math import pi, sqrt

    # da/dN = C*(Y*ds*sqrt(pi*a))^m at a 1 mm crack, C=1e-11, m=3.
    rate = paris_law_crack_growth_rate(
        stress_range=_q("100 MPa"),
        crack_length=_q("1 mm"),
        paris_coefficient=1e-11,
        paris_exponent=3.0,
    )
    dk = 1.0 * 100.0 * sqrt(pi * 0.001)
    assert rate.to("m").magnitude == pytest.approx(1e-11 * dk**3, rel=1e-12)
    assert rate.to("m").magnitude == pytest.approx(1.7609e-9, rel=1e-3)
    # The integrated life from 1 mm to 10 mm matches the closed form and a
    # numeric integration of the same rate (cross-check).
    n = paris_law_cycles_to_failure(
        stress_range=_q("100 MPa"),
        initial_crack_length=_q("1 mm"),
        final_crack_length=_q("10 mm"),
        paris_coefficient=1e-11,
        paris_exponent=3.0,
    )
    exponent = 1.0 - 3.0 / 2.0
    expected = (0.01**exponent - 0.001**exponent) / (
        1e-11 * (1.0 * 100.0 * sqrt(pi)) ** 3.0 * exponent
    )
    assert n == pytest.approx(expected, rel=1e-12)
    assert n == pytest.approx(776634.0, rel=1e-4)
    # Numeric trapezoid of dN = da/(da/dN) over the same span.
    steps = 20000
    a0, af = 0.001, 0.01
    h = (af - a0) / steps
    total = 0.0
    for i in range(steps + 1):
        a = a0 + i * h
        rate_i = 1e-11 * (1.0 * 100.0 * sqrt(pi * a)) ** 3.0
        total += (0.5 if i in (0, steps) else 1.0) / rate_i
    assert n == pytest.approx(total * h, rel=1e-3)


def test_paris_law_rejects_bad_inputs():
    with pytest.raises(ValueError, match="paris_coefficient must be positive"):
        paris_law_crack_growth_rate(
            stress_range=_q("100 MPa"),
            crack_length=_q("1 mm"),
            paris_coefficient=0.0,
            paris_exponent=3.0,
        )
    with pytest.raises(ValueError, match="differ from 2"):
        paris_law_cycles_to_failure(
            stress_range=_q("100 MPa"),
            initial_crack_length=_q("1 mm"),
            final_crack_length=_q("10 mm"),
            paris_coefficient=1e-11,
            paris_exponent=2.0,
        )
    with pytest.raises(ValueError, match="final_crack_length must exceed"):
        paris_law_cycles_to_failure(
            stress_range=_q("100 MPa"),
            initial_crack_length=_q("10 mm"),
            final_crack_length=_q("1 mm"),
            paris_coefficient=1e-11,
            paris_exponent=3.0,
        )


def test_cylinder_external_pressure_buckling_rides_on_the_cube_of_thinness():
    # p_cr = E*t^3/(4*r^3*(1-nu^2)): a 2 mm steel tube at 100 mm mean radius.
    p = cylinder_external_pressure_buckling(
        elastic_modulus=_q("200 GPa"), wall_thickness=_q("2 mm"), mean_radius=_q("100 mm")
    )
    expected = 200e3 * 2.0**3 / (4.0 * 100.0**3 * (1 - 0.3**2))  # MPa (E in MPa, lengths mm)
    assert p.to("MPa").magnitude == pytest.approx(expected, rel=1e-12)
    assert p.to("MPa").magnitude == pytest.approx(0.4396, rel=1e-3)
    # It rides on the CUBE of the thickness ratio: doubling the wall gives 8x.
    thicker = cylinder_external_pressure_buckling(
        elastic_modulus=_q("200 GPa"), wall_thickness=_q("4 mm"), mean_radius=_q("100 mm")
    )
    assert thicker.to("MPa").magnitude == pytest.approx(8.0 * p.to("MPa").magnitude, rel=1e-12)
    # And falls with the cube of the radius: a bigger tube collapses far sooner.
    bigger = cylinder_external_pressure_buckling(
        elastic_modulus=_q("200 GPa"), wall_thickness=_q("2 mm"), mean_radius=_q("200 mm")
    )
    assert bigger.to("MPa").magnitude == pytest.approx(p.to("MPa").magnitude / 8.0, rel=1e-12)
    # It also matches the equivalent 2E(t/D)^3/(1-nu^2) form.
    alt = 2 * 200e3 * (2.0 / 200.0) ** 3 / (1 - 0.3**2)
    assert p.to("MPa").magnitude == pytest.approx(alt, rel=1e-12)


def test_cylinder_external_pressure_buckling_rejects_bad_inputs():
    with pytest.raises(ValueError, match="wall_thickness must be positive"):
        cylinder_external_pressure_buckling(
            elastic_modulus=_q("200 GPa"), wall_thickness=_q("0 mm"), mean_radius=_q("100 mm")
        )
    with pytest.raises(ValueError, match=r"poisson must lie in \[0, 0.5\)"):
        cylinder_external_pressure_buckling(
            elastic_modulus=_q("200 GPa"),
            wall_thickness=_q("2 mm"),
            mean_radius=_q("100 mm"),
            poisson=0.5,
        )
    with pytest.raises(ValueError, match="elastic_modulus must be a"):
        cylinder_external_pressure_buckling(
            elastic_modulus=_q("200 mm"), wall_thickness=_q("2 mm"), mean_radius=_q("100 mm")
        )


def test_thermal_shock_stress_adds_the_biaxial_factor():
    kw = {
        "elastic_modulus": _q("70 GPa"),
        "thermal_expansion_coefficient": _q("9e-6 1/K"),
        "temperature_change": _q("200 K"),
    }
    # sigma = E*alpha*dT/(1-nu): glass quenched 200 K, nu=0.22.
    shock = thermal_shock_stress(**kw, poisson=0.22)
    base = 70e3 * 9e-6 * 200  # E*alpha*dT in MPa
    assert shock.to("MPa").magnitude == pytest.approx(base / (1 - 0.22), rel=1e-12)
    assert shock.to("MPa").magnitude == pytest.approx(161.5, rel=1e-3)
    # It is exactly the uniaxial constrained stress amplified by 1/(1-nu).
    uniaxial = constrained_thermal_stress(**kw)
    assert shock.to("MPa").magnitude == pytest.approx(
        uniaxial.to("MPa").magnitude / (1 - 0.22), rel=1e-12
    )
    assert shock.to("MPa").magnitude > uniaxial.to("MPa").magnitude
    with pytest.raises(ValueError, match=r"poisson must lie in \[0, 0.5\)"):
        thermal_shock_stress(**kw, poisson=0.5)
    with pytest.raises(ValueError, match="temperature_change must be a temperature"):
        thermal_shock_stress(
            elastic_modulus=_q("70 GPa"),
            thermal_expansion_coefficient=_q("9e-6 1/K"),
            temperature_change=_q("200 N"),
        )


def test_string_natural_frequency_and_harmonics():
    from math import sqrt

    kw = {"tension": _q("1000 N"), "length": _q("2 m"), "mass_per_length": _q("0.5 kg/m")}
    # f_1 = (1/2L)*sqrt(T/mu): 1000 N, 2 m, 0.5 kg/m -> 11.18 Hz.
    f1 = string_natural_frequency(**kw)
    assert f1.to("Hz").magnitude == pytest.approx(1 / (2 * 2.0) * sqrt(1000 / 0.5), rel=1e-12)
    assert f1.to("Hz").magnitude == pytest.approx(11.180, rel=1e-3)
    # Overtones are exact integer multiples of the fundamental.
    f3 = string_natural_frequency(**kw, mode=3)
    assert f3.to("Hz").magnitude == pytest.approx(3 * f1.to("Hz").magnitude, rel=1e-12)
    # Tightening the string (4x tension) doubles the pitch.
    tighter = string_natural_frequency(
        tension=_q("4000 N"), length=_q("2 m"), mass_per_length=_q("0.5 kg/m")
    )
    assert tighter.to("Hz").magnitude == pytest.approx(2 * f1.to("Hz").magnitude, rel=1e-12)


def test_string_natural_frequency_rejects_bad_inputs():
    with pytest.raises(ValueError, match="mode must be a positive whole number"):
        string_natural_frequency(
            tension=_q("1000 N"), length=_q("2 m"), mass_per_length=_q("0.5 kg/m"), mode=0
        )
    with pytest.raises(ValueError, match="tension must be positive"):
        string_natural_frequency(
            tension=_q("0 N"), length=_q("2 m"), mass_per_length=_q("0.5 kg/m")
        )
    with pytest.raises(ValueError, match="mass_per_length must be a"):
        string_natural_frequency(
            tension=_q("1000 N"), length=_q("2 m"), mass_per_length=_q("0.5 kg")
        )


def test_spiral_spring_rate_and_stress():
    # k_theta = E*b*t^3/(12*L): 200 GPa, 10 mm wide, 0.5 mm thick, 500 mm long.
    k = spiral_spring_rate(
        width=_q("10 mm"),
        thickness=_q("0.5 mm"),
        developed_length=_q("500 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    # E in MPa (=N/mm^2), lengths mm -> N*mm/rad, then /1000 -> N*m/rad.
    expected = 200e3 * 10.0 * 0.5**3 / (12.0 * 500.0) / 1000.0
    assert k.to("N*m").magnitude == pytest.approx(expected, rel=1e-12)
    assert k.to("N*m").magnitude == pytest.approx(0.041667, rel=1e-4)
    # A longer strip is softer (winds more turns for the same torque).
    softer = spiral_spring_rate(
        width=_q("10 mm"),
        thickness=_q("0.5 mm"),
        developed_length=_q("1000 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    assert softer.to("N*m").magnitude == pytest.approx(k.to("N*m").magnitude / 2, rel=1e-12)
    # Peak stress sigma = 6M/(b*t^2): a 0.02 N*m wind-up.
    s = spiral_spring_stress(moment=_q("0.02 N*m"), width=_q("10 mm"), thickness=_q("0.5 mm"))
    assert s.to("MPa").magnitude == pytest.approx(6 * 20.0 / (10.0 * 0.5**2), rel=1e-12)
    assert s.to("MPa").magnitude == pytest.approx(48.0, rel=1e-9)


def test_spiral_spring_rejects_bad_inputs():
    with pytest.raises(ValueError, match="thickness must be positive"):
        spiral_spring_rate(
            width=_q("10 mm"),
            thickness=_q("0 mm"),
            developed_length=_q("500 mm"),
            elastic_modulus=_q("200 GPa"),
        )
    with pytest.raises(ValueError, match="moment must be a"):
        spiral_spring_stress(moment=_q("0.02 N"), width=_q("10 mm"), thickness=_q("0.5 mm"))


def test_helical_torsion_spring_rate_and_stress():
    # k = E*d^4/(64*D*N_a): 200 GPa, 3 mm wire, 25 mm coil, 5 active coils.
    k = helical_torsion_spring_rate(
        mean_coil_diameter=_q("25 mm"),
        wire_diameter=_q("3 mm"),
        active_coils=5,
        elastic_modulus=_q("200 GPa"),
    )
    # E in MPa (N/mm^2), lengths mm -> N*mm/rad, /1000 -> N*m/rad.
    expected = 200e3 * 3.0**4 / (64.0 * 25.0 * 5.0) / 1000.0
    assert k.to("N*m").magnitude == pytest.approx(expected, rel=1e-12)
    assert k.to("N*m").magnitude == pytest.approx(2.025, rel=1e-3)
    # Inner-fibre stress sigma = K_i*32*M/(pi*d^3), K_i=(4C^2-C-1)/(4C(C-1)), C=D/d.
    c = 25.0 / 3.0
    ki = (4 * c**2 - c - 1) / (4 * c * (c - 1))
    s = helical_torsion_spring_stress(
        moment=_q("1 N*m"), mean_coil_diameter=_q("25 mm"), wire_diameter=_q("3 mm")
    )
    assert s.to("MPa").magnitude == pytest.approx(ki * 32 * 1000.0 / (pi * 3.0**3), rel=1e-12)
    assert s.to("MPa").magnitude == pytest.approx(414.3, rel=1e-3)
    # As the coil opens up (large C) the curvature factor fades to 1 and the
    # stress approaches the straight-beam value 32M/(pi*d^3).
    opened = helical_torsion_spring_stress(
        moment=_q("1 N*m"), mean_coil_diameter=_q("3000 mm"), wire_diameter=_q("3 mm")
    )
    assert opened.to("MPa").magnitude == pytest.approx(32 * 1000.0 / (pi * 3.0**3), rel=2e-3)


def test_helical_torsion_spring_rejects_bad_inputs():
    with pytest.raises(ValueError, match="active_coils must be positive"):
        helical_torsion_spring_rate(
            mean_coil_diameter=_q("25 mm"),
            wire_diameter=_q("3 mm"),
            active_coils=0,
            elastic_modulus=_q("200 GPa"),
        )
    with pytest.raises(ValueError, match="moment must be a"):
        helical_torsion_spring_stress(
            moment=_q("1 N"), mean_coil_diameter=_q("25 mm"), wire_diameter=_q("3 mm")
        )


def test_rotating_rim_radial_growth_matches_the_hoop_stress():
    steel = _q("7850 kg/m**3")
    E = _q("200 GPa")
    kw = {"density": steel, "mean_radius": _q("0.3 m"), "rotational_speed": _q("3000 rpm")}
    # delta = rho*omega^2*r^3/E: a 0.3 m steel rim at 3000 rpm grows ~0.105 mm.
    growth = rotating_rim_radial_growth(**kw, elastic_modulus=E)
    omega = 3000 * 2 * 3.141592653589793 / 60.0
    assert growth.to("mm").magnitude == pytest.approx(
        7850 * omega**2 * 0.3**3 / 200e9 * 1000, rel=1e-9
    )
    assert growth.to("mm").magnitude == pytest.approx(0.1046, rel=1e-3)
    # It is exactly the hoop stress times r/E (the shrink-fit loss at speed).
    sigma = rotating_rim_hoop_stress(**kw)
    predicted = sigma.to("Pa").magnitude * 0.3 / 200e9 * 1000  # mm
    assert growth.to("mm").magnitude == pytest.approx(predicted, rel=1e-9)
    # Growth rides on omega^2: doubling the speed quadruples it.
    faster = rotating_rim_radial_growth(
        density=steel, mean_radius=_q("0.3 m"), rotational_speed=_q("6000 rpm"), elastic_modulus=E
    )
    assert faster.to("mm").magnitude == pytest.approx(4 * growth.to("mm").magnitude, rel=1e-9)


def test_rotating_rim_radial_growth_rejects_bad_inputs():
    with pytest.raises(ValueError, match="rotational_speed must be positive"):
        rotating_rim_radial_growth(
            density=_q("7850 kg/m**3"),
            mean_radius=_q("0.3 m"),
            rotational_speed=_q("0 rpm"),
            elastic_modulus=_q("200 GPa"),
        )
    with pytest.raises(ValueError, match="elastic_modulus must be a"):
        rotating_rim_radial_growth(
            density=_q("7850 kg/m**3"),
            mean_radius=_q("0.3 m"),
            rotational_speed=_q("3000 rpm"),
            elastic_modulus=_q("200 mm"),
        )


def test_damped_vibration_measures():
    from math import pi, sqrt

    # Damped frequency f_d = f_n*sqrt(1-zeta^2): light damping barely shifts it.
    fd = damped_natural_frequency(natural_frequency=_q("100 Hz"), damping_ratio=0.05)
    assert fd.to("Hz").magnitude == pytest.approx(100 * sqrt(1 - 0.05**2), rel=1e-12)
    assert fd.to("Hz").magnitude == pytest.approx(99.875, rel=1e-4)
    # An undamped system keeps its full frequency.
    assert damped_natural_frequency(natural_frequency=_q("100 Hz"), damping_ratio=0.0).to(
        "Hz"
    ).magnitude == pytest.approx(100.0, rel=1e-12)
    # Log decrement delta = 2*pi*zeta/sqrt(1-zeta^2); ~2*pi*zeta when light.
    delta = logarithmic_decrement(damping_ratio=0.05)
    assert delta == pytest.approx(2 * pi * 0.05 / sqrt(1 - 0.05**2), rel=1e-12)
    assert delta == pytest.approx(2 * pi * 0.05, rel=2e-3)


def test_transmissibility_isolation_crossover():
    from math import sqrt

    # At r = sqrt(2) the transmissibility is exactly 1 for ANY damping -- the
    # crossover below which a mount amplifies and above which it isolates.
    for zeta in (0.0, 0.1, 0.3, 0.5):
        assert transmissibility(frequency_ratio=sqrt(2), damping_ratio=zeta) == pytest.approx(
            1.0, rel=1e-9
        )
    # Below the crossover the mount amplifies (TR > 1); well above it isolates.
    assert transmissibility(frequency_ratio=1.0, damping_ratio=0.1) > 1.0  # near resonance
    assert transmissibility(frequency_ratio=4.0, damping_ratio=0.1) < 1.0  # isolation region
    # More damping tames the resonant peak...
    assert transmissibility(frequency_ratio=1.0, damping_ratio=0.3) < transmissibility(
        frequency_ratio=1.0, damping_ratio=0.1
    )
    # ...but WORSENS isolation high above the crossover.
    assert transmissibility(frequency_ratio=4.0, damping_ratio=0.3) > transmissibility(
        frequency_ratio=4.0, damping_ratio=0.1
    )
    # At resonance TR = sqrt(1+(2*zeta)^2)/(2*zeta).
    tr_res = transmissibility(frequency_ratio=1.0, damping_ratio=0.2)
    assert tr_res == pytest.approx(sqrt(1 + (2 * 0.2) ** 2) / (2 * 0.2), rel=1e-12)


def test_dynamic_magnification_factor_peaks_near_resonance():
    # Quasi-static (r -> 0) the response equals the static deflection: M = 1.
    assert dynamic_magnification_factor(frequency_ratio=0.0, damping_ratio=0.05) == pytest.approx(
        1.0, rel=1e-12
    )
    # At r = 1 exactly, M = 1/(2*zeta) = the quality factor.
    assert dynamic_magnification_factor(frequency_ratio=1.0, damping_ratio=0.05) == pytest.approx(
        1.0 / (2 * 0.05), rel=1e-12
    )
    assert dynamic_magnification_factor(frequency_ratio=1.0, damping_ratio=0.05) == pytest.approx(
        quality_factor(damping_ratio=0.05), rel=1e-12
    )
    # Well above resonance the mass cannot follow the force: M -> 0.
    assert dynamic_magnification_factor(frequency_ratio=5.0, damping_ratio=0.05) < 0.05
    # More damping lowers the resonant peak.
    assert dynamic_magnification_factor(
        frequency_ratio=1.0, damping_ratio=0.2
    ) < dynamic_magnification_factor(frequency_ratio=1.0, damping_ratio=0.05)
    with pytest.raises(ValueError, match="frequency_ratio must be non-negative"):
        dynamic_magnification_factor(frequency_ratio=-1.0, damping_ratio=0.1)


def test_resonance_phase_angle_passes_through_ninety_at_resonance():
    # Well below resonance the response is in phase with the force.
    assert resonance_phase_angle(frequency_ratio=0.0, damping_ratio=0.1) == pytest.approx(
        0.0, abs=1e-9
    )
    # At r = 1 the lag is exactly 90 degrees for ANY damping.
    for zeta in (0.02, 0.1, 0.5):
        assert resonance_phase_angle(frequency_ratio=1.0, damping_ratio=zeta) == pytest.approx(
            90.0, rel=1e-12
        )
    # Well above resonance it approaches 180 degrees (moving opposite the force).
    assert resonance_phase_angle(frequency_ratio=50.0, damping_ratio=0.1) > 179.0
    # The phase climbs monotonically through resonance (atan2 keeps it in 0..180).
    below = resonance_phase_angle(frequency_ratio=0.9, damping_ratio=0.1)
    above = resonance_phase_angle(frequency_ratio=1.1, damping_ratio=0.1)
    assert below < 90.0 < above
    with pytest.raises(ValueError, match="frequency_ratio must be non-negative"):
        resonance_phase_angle(frequency_ratio=-1.0, damping_ratio=0.1)


def test_base_excitation_relative_transmissibility_two_instrument_regimes():
    # Accelerometer regime (r << 1): the reading tends to r^2, so it tracks the
    # base acceleration.
    small = base_excitation_relative_transmissibility(frequency_ratio=0.1, damping_ratio=0.1)
    assert small == pytest.approx(0.1**2, rel=0.02)
    # At resonance (r = 1) it peaks at the quality factor 1/(2*zeta).
    assert base_excitation_relative_transmissibility(
        frequency_ratio=1.0, damping_ratio=0.1
    ) == pytest.approx(1.0 / (2 * 0.1), rel=1e-12)
    # Seismometer regime (r >> 1): the reading tends to 1, tracking base displacement.
    assert base_excitation_relative_transmissibility(
        frequency_ratio=100.0, damping_ratio=0.1
    ) == pytest.approx(1.0, rel=1e-3)
    with pytest.raises(ValueError, match="frequency_ratio must be non-negative"):
        base_excitation_relative_transmissibility(frequency_ratio=-1.0, damping_ratio=0.1)


def test_damped_vibration_rejects_bad_inputs():
    with pytest.raises(ValueError, match=r"damping_ratio must lie in \[0, 1\)"):
        damped_natural_frequency(natural_frequency=_q("100 Hz"), damping_ratio=1.0)
    with pytest.raises(ValueError, match=r"damping_ratio must lie in \[0, 1\)"):
        logarithmic_decrement(damping_ratio=1.5)
    with pytest.raises(ValueError, match="frequency_ratio must be non-negative"):
        transmissibility(frequency_ratio=-1.0, damping_ratio=0.1)


def test_geneva_advance_and_dwell_fractions():
    # Advance (moving) fraction (n-2)/(2n); dwell its complement (n+2)/(2n).
    assert geneva_advance_fraction(slots=4) == pytest.approx(0.25)
    assert geneva_dwell_fraction(slots=4) == pytest.approx(0.75)
    assert geneva_advance_fraction(slots=6) == pytest.approx(1 / 3)
    assert geneva_dwell_fraction(slots=6) == pytest.approx(2 / 3)
    assert geneva_advance_fraction(slots=8) == pytest.approx(0.375)
    # They always sum to one, and more slots spend more of the cycle moving.
    for n in (3, 4, 6, 8, 12):
        assert geneva_advance_fraction(slots=n) + geneva_dwell_fraction(slots=n) == pytest.approx(
            1.0
        )
    assert geneva_advance_fraction(slots=8) > geneva_advance_fraction(slots=4)
    assert geneva_dwell_fraction(slots=8) < geneva_dwell_fraction(slots=4)
    with pytest.raises(ValueError, match="whole number ≥ 3"):
        geneva_advance_fraction(slots=2)


def test_elliptical_bar_torsion_reduces_to_the_circle():
    from math import pi

    # tau_max = 2T/(pi*a*b^2); at a = b = r it must equal the circular 2T/(pi*r^3).
    ellipse = elliptical_bar_torsional_stress(
        torque=_q("500 N*m"), semi_major_axis=_q("25 mm"), semi_minor_axis=_q("25 mm")
    )
    assert ellipse.to("MPa").magnitude == pytest.approx(
        shaft_torsional_stress(torque=_q("500 N*m"), diameter=_q("50 mm")).to("MPa").magnitude,
        rel=1e-12,
    )
    # A real 40x20 mm ellipse: peak at the minor-axis ends.
    e2 = elliptical_bar_torsional_stress(
        torque=_q("500 N*m"), semi_major_axis=_q("40 mm"), semi_minor_axis=_q("20 mm")
    )
    assert e2.to("MPa").magnitude == pytest.approx(2 * 500e3 / (pi * 40 * 20**2), rel=1e-12)
    # Twist also collapses to the circular-shaft value at a = b.
    et = elliptical_bar_twist_angle(
        torque=_q("500 N*m"),
        length=_q("1 m"),
        semi_major_axis=_q("25 mm"),
        semi_minor_axis=_q("25 mm"),
        shear_modulus=_q("79 GPa"),
    )
    assert et.to("degree").magnitude == pytest.approx(
        shaft_twist_angle(
            torque=_q("500 N*m"), length=_q("1 m"), diameter=_q("50 mm"), shear_modulus=_q("79 GPa")
        )
        .to("degree")
        .magnitude,
        rel=1e-12,
    )
    with pytest.raises(ValueError, match="semi_minor_axis .* must not exceed semi_major_axis"):
        elliptical_bar_torsional_stress(
            torque=_q("500 N*m"), semi_major_axis=_q("20 mm"), semi_minor_axis=_q("40 mm")
        )


def test_triangular_bar_torsion():
    from math import sqrt

    # tau_max = 20T/s^3 at the midpoint of each side.
    tau = triangular_bar_torsional_stress(torque=_q("500 N*m"), side_length=_q("60 mm"))
    assert tau.to("MPa").magnitude == pytest.approx(20 * 500e3 / 60**3, rel=1e-12)
    assert tau.to("MPa").magnitude == pytest.approx(46.30, rel=1e-3)
    # Twist theta = T*L/(G*J), J = sqrt(3)*s^4/80.
    theta = triangular_bar_twist_angle(
        torque=_q("500 N*m"), length=_q("1 m"), side_length=_q("60 mm"), shear_modulus=_q("79 GPa")
    )
    j = sqrt(3) * 60**4 / 80  # mm^4
    expected_rad = 500e3 * 1000 / (79000 * j)
    assert theta.to("rad").magnitude == pytest.approx(expected_rad, rel=1e-9)
    with pytest.raises(ValueError, match="side_length must be positive"):
        triangular_bar_torsional_stress(torque=_q("500 N*m"), side_length=_q("0 mm"))


def test_notch_sensitivity_neuber_and_peterson():
    from math import sqrt

    # Neuber q = 1/(1 + sqrt(a)/sqrt(r)); blunt notch -> q near 1.
    n = neuber_notch_sensitivity(notch_radius=_q("2 mm"), neuber_constant=_q("0.25 mm**0.5"))
    assert n == pytest.approx(1 / (1 + 0.25 / sqrt(2.0)), rel=1e-12)
    assert n == pytest.approx(0.8498, rel=1e-3)
    # q = 0.5 when sqrt(r) = sqrt(a), i.e. r = a^2 = 0.0625 mm.
    assert neuber_notch_sensitivity(
        notch_radius=_q("0.0625 mm"), neuber_constant=_q("0.25 mm**0.5")
    ) == pytest.approx(0.5, rel=1e-12)
    # Peterson q = 1/(1 + a/r); q = 0.5 at r = a, climbs toward 1 for a blunt notch.
    assert peterson_notch_sensitivity(
        notch_radius=_q("0.5 mm"), peterson_constant=_q("0.5 mm")
    ) == pytest.approx(0.5, rel=1e-12)
    assert peterson_notch_sensitivity(
        notch_radius=_q("5 mm"), peterson_constant=_q("0.5 mm")
    ) == pytest.approx(10 / 11, rel=1e-12)
    # A blunter notch is more sensitive; both q stay in [0, 1].
    assert (
        neuber_notch_sensitivity(notch_radius=_q("10 mm"), neuber_constant=_q("0.25 mm**0.5")) > n
    )
    # They feed the notch factor: K_f = 1 + q*(K_t - 1).
    kf = fatigue_notch_factor(kt=2.5, notch_sensitivity=n)
    assert kf == pytest.approx(1 + n * 1.5, rel=1e-12)
    with pytest.raises(ValueError, match="neuber_constant must be a"):
        neuber_notch_sensitivity(notch_radius=_q("2 mm"), neuber_constant=_q("0.25 mm"))
    with pytest.raises(ValueError, match="notch_radius must be positive"):
        peterson_notch_sensitivity(notch_radius=_q("0 mm"), peterson_constant=_q("0.5 mm"))


def test_thin_ring_diametral_deflection_and_moment():
    from math import pi

    # delta = (pi/4 - 2/pi)*P*R^3/(E*I): a 100 mm-radius ring under 500 N.
    d = thin_ring_diametral_deflection(
        load=_q("500 N"),
        radius=_q("100 mm"),
        elastic_modulus=_q("200 GPa"),
        second_moment=_q("500 mm**4"),
    )
    coefficient = pi / 4 - 2 / pi
    assert d.to("mm").magnitude == pytest.approx(
        coefficient * 500 * 100**3 / (200000 * 500), rel=1e-12
    )
    assert d.to("mm").magnitude == pytest.approx(0.7439, rel=1e-3)
    # The deflection scales with R^3 and inversely with E*I.
    stiffer = thin_ring_diametral_deflection(
        load=_q("500 N"),
        radius=_q("100 mm"),
        elastic_modulus=_q("200 GPa"),
        second_moment=_q("1000 mm**4"),
    )
    assert stiffer.to("mm").magnitude == pytest.approx(d.to("mm").magnitude / 2, rel=1e-12)
    # Peak moment M = P*R*(1/2 - 1/pi) ~ 0.1817*P*R at the load points.
    m = thin_ring_max_moment(load=_q("500 N"), radius=_q("100 mm"))
    assert m.to("N*mm").magnitude == pytest.approx(500 * 100 * (0.5 - 1 / pi), rel=1e-12)
    assert m.to("N*mm").magnitude == pytest.approx(9084.5, rel=1e-3)
    with pytest.raises(ValueError, match="radius must be positive"):
        thin_ring_max_moment(load=_q("500 N"), radius=_q("0 mm"))
    with pytest.raises(ValueError, match="second_moment must be a"):
        thin_ring_diametral_deflection(
            load=_q("500 N"),
            radius=_q("100 mm"),
            elastic_modulus=_q("200 GPa"),
            second_moment=_q("500 mm"),
        )


def test_thin_ring_buckling_pressure():
    # q_cr = 3*E*I/R^3: E=200 GPa, I=1000 mm^4, R=100 mm -> 600 N/mm.
    q = thin_ring_buckling_pressure(
        elastic_modulus=_q("200 GPa"),
        second_moment=_q("1000 mm**4"),
        radius=_q("100 mm"),
    )
    assert q.to("N/mm").magnitude == pytest.approx(3 * 200000 * 1000 / 100**3, rel=1e-12)
    assert q.to("N/mm").magnitude == pytest.approx(600.0, rel=1e-9)
    # It recovers the long-tube collapse pressure (bar the plane-strain 1-nu^2
    # factor) when I = t^3/12 per unit width: q_cr/1 vs E*t^3/(4*R^3).
    t = 4.0
    per_width = thin_ring_buckling_pressure(
        elastic_modulus=_q("200 GPa"),
        second_moment=_q(f"{t**3 / 12} mm**4"),
        radius=_q("100 mm"),
    )
    assert per_width.to("N/mm").magnitude == pytest.approx(200000 * t**3 / (4 * 100**3), rel=1e-12)
    # It falls off with the cube of the radius: doubling R gives 1/8.
    bigger = thin_ring_buckling_pressure(
        elastic_modulus=_q("200 GPa"),
        second_moment=_q("1000 mm**4"),
        radius=_q("200 mm"),
    )
    assert bigger.to("N/mm").magnitude == pytest.approx(q.to("N/mm").magnitude / 8, rel=1e-12)
    with pytest.raises(ValueError, match="radius must be positive"):
        thin_ring_buckling_pressure(
            elastic_modulus=_q("200 GPa"), second_moment=_q("1000 mm**4"), radius=_q("0 mm")
        )


def test_rotating_solid_disc_peak_stress_is_at_the_centre():
    steel = _q("7850 kg/m**3")
    kw = {"density": steel, "outer_radius": _q("300 mm"), "rotational_speed": _q("3000 rpm")}
    # sigma_center = (3+nu)/8 * rho * (omega*R)^2.
    disc = rotating_solid_disc_max_stress(**kw, poisson=0.3)
    omega = 3000 * 2 * 3.141592653589793 / 60.0
    v = omega * 0.3
    assert disc.to("MPa").magnitude == pytest.approx((3.3 / 8) * 7850 * v**2 / 1e6, rel=1e-12)
    assert disc.to("MPa").magnitude == pytest.approx(28.76, rel=1e-3)
    # A SOLID disc peaks at (3+nu)/8 = 0.4125 of a thin rim's rho*v^2 at the same R.
    rim = rotating_rim_hoop_stress(
        density=steel, mean_radius=_q("300 mm"), rotational_speed=_q("3000 rpm")
    )
    assert disc.to("MPa").magnitude / rim.to("MPa").magnitude == pytest.approx(3.3 / 8, rel=1e-9)
    # Stress rides on (omega*R)^2.
    faster = rotating_solid_disc_max_stress(
        density=steel, outer_radius=_q("300 mm"), rotational_speed=_q("6000 rpm")
    )
    assert faster.to("MPa").magnitude == pytest.approx(4 * disc.to("MPa").magnitude, rel=1e-9)
    with pytest.raises(ValueError, match=r"poisson must lie in \[0, 0.5\)"):
        rotating_solid_disc_max_stress(**kw, poisson=0.6)


def test_rotating_solid_disc_stress_distribution_at_centre_and_rim():
    steel = _q("7850 kg/m**3")
    kw = {"density": steel, "outer_radius": _q("300 mm"), "rotational_speed": _q("3000 rpm")}
    omega = 3000 * 2 * 3.141592653589793 / 60.0
    centre = rotating_solid_disc_max_stress(**kw).to("MPa").magnitude
    # At r = 0 the radial and tangential stresses both equal the centre peak.
    assert rotating_solid_disc_radial_stress(**kw, radius=_q("0 mm")).to(
        "MPa"
    ).magnitude == pytest.approx(centre, rel=1e-12)
    assert rotating_solid_disc_tangential_stress(**kw, radius=_q("0 mm")).to(
        "MPa"
    ).magnitude == pytest.approx(centre, rel=1e-12)
    # At the free rim the radial stress is zero...
    assert rotating_solid_disc_radial_stress(**kw, radius=_q("300 mm")).to(
        "MPa"
    ).magnitude == pytest.approx(0.0, abs=1e-9)
    # ...but the tangential stress settles to rho*omega^2*R^2*(1-nu)/4.
    rim_hoop = rotating_solid_disc_tangential_stress(**kw, radius=_q("300 mm"))
    assert rim_hoop.to("MPa").magnitude == pytest.approx(
        7850 * omega**2 * 0.3**2 * (1 - 0.3) / 4 / 1e6, rel=1e-12
    )
    assert rim_hoop.to("MPa").magnitude == pytest.approx(12.203, rel=1e-3)
    with pytest.raises(ValueError, match="radius .* must be between 0 and the outer_radius"):
        rotating_solid_disc_radial_stress(**kw, radius=_q("400 mm"))


def test_rotating_annular_disc_bore_stress_doubles_the_solid_disc():
    steel = _q("7850 kg/m**3")
    speed = _q("3000 rpm")
    # sigma_bore = (rho*omega^2/4)*[(3+nu)*Ro^2 + (1-nu)*Ri^2].
    bore = rotating_annular_disc_bore_stress(
        density=steel,
        outer_radius=_q("300 mm"),
        inner_radius=_q("100 mm"),
        rotational_speed=speed,
        poisson=0.3,
    )
    omega = 3000 * 2 * 3.141592653589793 / 60.0
    expected = 7850 * omega**2 / 4 * (3.3 * 0.3**2 + 0.7 * 0.1**2) / 1e6
    assert bore.to("MPa").magnitude == pytest.approx(expected, rel=1e-12)
    # The classic result: a vanishing central hole DOUBLES the solid-disc centre
    # stress -- even a pinhole at the axis halves the burst speed.
    tiny_hole = rotating_annular_disc_bore_stress(
        density=steel,
        outer_radius=_q("300 mm"),
        inner_radius=_q("0.001 mm"),
        rotational_speed=speed,
    )
    solid = rotating_solid_disc_max_stress(
        density=steel, outer_radius=_q("300 mm"), rotational_speed=speed
    )
    assert tiny_hole.to("MPa").magnitude == pytest.approx(2 * solid.to("MPa").magnitude, rel=1e-4)
    with pytest.raises(ValueError, match="outer_radius .* must exceed inner_radius"):
        rotating_annular_disc_bore_stress(
            density=steel,
            outer_radius=_q("100 mm"),
            inner_radius=_q("300 mm"),
            rotational_speed=speed,
        )


def test_rotating_annular_disc_stress_distribution():
    import math

    kw = {
        "density": _q("7850 kg/m**3"),
        "outer_radius": _q("300 mm"),
        "inner_radius": _q("100 mm"),
        "rotational_speed": _q("3000 rpm"),
    }
    # The tangential stress at the bore equals the closed-form bore stress.
    bore = rotating_annular_disc_bore_stress(**kw)
    tang_bore = rotating_annular_disc_tangential_stress(**kw, radius=_q("100 mm"))
    assert tang_bore.to("MPa").magnitude == pytest.approx(bore.to("MPa").magnitude, rel=1e-12)
    # The radial stress vanishes at both free edges (bore and rim).
    assert rotating_annular_disc_radial_stress(**kw, radius=_q("100 mm")).to(
        "MPa"
    ).magnitude == pytest.approx(0.0, abs=1e-9)
    assert rotating_annular_disc_radial_stress(**kw, radius=_q("300 mm")).to(
        "MPa"
    ).magnitude == pytest.approx(0.0, abs=1e-9)
    # ...and peaks in between at r = sqrt(Ri*Ro), above the values either side.
    r_peak = math.sqrt(0.1 * 0.3) * 1000  # mm
    peak = rotating_annular_disc_radial_stress(**kw, radius=_q(f"{r_peak} mm")).to("MPa").magnitude
    lower = rotating_annular_disc_radial_stress(**kw, radius=_q("150 mm")).to("MPa").magnitude
    assert peak > lower > 0
    with pytest.raises(ValueError, match="radius .* must lie between the inner and outer radii"):
        rotating_annular_disc_tangential_stress(**kw, radius=_q("50 mm"))


def test_box_and_i_section_second_moments():
    # Box tube I = (b*h^3 - (b-2t)*(h-2t)^3)/12.
    box = rectangular_tube_second_moment(
        width=_q("60 mm"), height=_q("100 mm"), wall_thickness=_q("5 mm")
    )
    assert box.to("mm**4").magnitude == pytest.approx((60 * 100**3 - 50 * 90**3) / 12, rel=1e-12)
    # A box carries far more I than the same-outline solid would per unit weight,
    # but less than the solid rectangle itself.
    assert (
        box.to("mm**4").magnitude
        < rectangular_second_moment(_q("60 mm"), _q("100 mm")).to("mm**4").magnitude
    )
    # I-section I = (b*h^3 - (b-t_w)*(h-2*t_f)^3)/12.
    ibeam = i_section_second_moment(
        flange_width=_q("100 mm"),
        total_height=_q("200 mm"),
        flange_thickness=_q("15 mm"),
        web_thickness=_q("10 mm"),
    )
    assert ibeam.to("mm**4").magnitude == pytest.approx(
        (100 * 200**3 - 90 * 170**3) / 12, rel=1e-12
    )
    # Filling the web and flanges solid recovers the solid rectangle.
    near_solid = i_section_second_moment(
        flange_width=_q("50 mm"),
        total_height=_q("100 mm"),
        flange_thickness=_q("49.999 mm"),
        web_thickness=_q("49.999 mm"),
    )
    assert near_solid.to("mm**4").magnitude == pytest.approx(
        rectangular_second_moment(_q("50 mm"), _q("100 mm")).to("mm**4").magnitude, rel=1e-3
    )
    with pytest.raises(ValueError, match="2\\*wall_thickness"):
        rectangular_tube_second_moment(
            width=_q("60 mm"), height=_q("100 mm"), wall_thickness=_q("30 mm")
        )
    with pytest.raises(ValueError, match="2\\*flange_thickness"):
        i_section_second_moment(
            flange_width=_q("100 mm"),
            total_height=_q("20 mm"),
            flange_thickness=_q("15 mm"),
            web_thickness=_q("10 mm"),
        )


def test_plastic_section_modulus_and_hinge_moment():
    from math import pi

    # Rectangle 50x100: Z_p = b*h^2/4 = 125000 mm^3, shape factor 3/2 over elastic.
    zp = rectangular_plastic_section_modulus(_q("50 mm"), _q("100 mm"))
    assert zp.to("mm**3").magnitude == pytest.approx(50 * 100**2 / 4, rel=1e-12)
    elastic = rectangular_second_moment(_q("50 mm"), _q("100 mm")).to("mm**4").magnitude / 50.0
    assert zp.to("mm**3").magnitude / elastic == pytest.approx(1.5, rel=1e-12)
    # Solid circle d=60: Z_p = d^3/6 = 36000 mm^3, shape factor 16/(3*pi).
    zpc = circular_plastic_section_modulus(_q("60 mm"))
    assert zpc.to("mm**3").magnitude == pytest.approx(60**3 / 6, rel=1e-12)
    elastic_c = circular_second_moment(_q("60 mm")).to("mm**4").magnitude / 30.0
    assert zpc.to("mm**3").magnitude / elastic_c == pytest.approx(16 / (3 * pi), rel=1e-12)
    # Fully-plastic moment M_p = Z_p * S_y.
    mp = plastic_moment(plastic_section_modulus=zp, yield_strength=_q("250 MPa"))
    assert mp.to("N*m").magnitude == pytest.approx(125000 * 250 / 1000, rel=1e-12)
    assert mp.to("N*m").magnitude == pytest.approx(31250.0, rel=1e-9)
    with pytest.raises(ValueError, match="yield_strength must be positive"):
        plastic_moment(plastic_section_modulus=zp, yield_strength=_q("0 MPa"))
    with pytest.raises(ValueError, match="width must be a"):
        rectangular_plastic_section_modulus(_q("50 N"), _q("100 mm"))
    # Hollow circle Z_p = (D^3 - d^3)/6, recovering the solid as the bore vanishes.
    hollow = hollow_circular_plastic_section_modulus(
        outer_diameter=_q("60 mm"), inner_diameter=_q("40 mm")
    )
    assert hollow.to("mm**3").magnitude == pytest.approx((60**3 - 40**3) / 6, rel=1e-12)
    solid_again = hollow_circular_plastic_section_modulus(
        outer_diameter=_q("60 mm"), inner_diameter=_q("0 mm")
    )
    assert solid_again.to("mm**3").magnitude == pytest.approx(zpc.to("mm**3").magnitude, rel=1e-12)
    # Box tube Z_p = (b*h^2 - (b-2t)*(h-2t)^2)/4.
    box = rectangular_tube_plastic_section_modulus(
        width=_q("60 mm"), height=_q("100 mm"), wall_thickness=_q("5 mm")
    )
    assert box.to("mm**3").magnitude == pytest.approx((60 * 100**2 - 50 * 90**2) / 4, rel=1e-12)
    with pytest.raises(ValueError, match="2\\*wall_thickness"):
        rectangular_tube_plastic_section_modulus(
            width=_q("60 mm"), height=_q("100 mm"), wall_thickness=_q("40 mm")
        )
    # I-section Z_p = b*t_f*(h - t_f) + t_w*(h - 2*t_f)^2/4.
    ibeam = i_section_plastic_section_modulus(
        flange_width=_q("100 mm"),
        total_height=_q("200 mm"),
        flange_thickness=_q("15 mm"),
        web_thickness=_q("10 mm"),
    )
    assert ibeam.to("mm**3").magnitude == pytest.approx(100 * 15 * 185 + 10 * 170**2 / 4, rel=1e-12)
    # Filling the flanges and web solid recovers the rectangle's b*h^2/4.
    near_solid = i_section_plastic_section_modulus(
        flange_width=_q("50 mm"),
        total_height=_q("100 mm"),
        flange_thickness=_q("49.999 mm"),
        web_thickness=_q("49.999 mm"),
    )
    assert near_solid.to("mm**3").magnitude == pytest.approx(
        rectangular_plastic_section_modulus(_q("50 mm"), _q("100 mm")).to("mm**3").magnitude,
        rel=1e-4,
    )


def test_plastic_collapse_loads_and_the_redistribution_reserve():
    mp = _q("50 kN*m")
    span = _q("4 m")
    # SS central point load collapses at P = 4*M_p/L (one midspan hinge).
    ss = simply_supported_plastic_collapse_load(plastic_moment_capacity=mp, span=span)
    assert ss.to("kN").magnitude == pytest.approx(4 * 50 / 4, rel=1e-12)
    assert ss.to("kN").magnitude == pytest.approx(50.0, rel=1e-9)
    # Fixed-fixed collapses at P = 8*M_p/L (three-hinge mechanism) -- twice the
    # simply-supported load, the moment-redistribution reserve of an indeterminate
    # ductile beam.
    ff = fixed_fixed_plastic_collapse_load(plastic_moment_capacity=mp, span=span)
    assert ff.to("kN").magnitude == pytest.approx(8 * 50 / 4, rel=1e-12)
    assert ff.to("N").magnitude == pytest.approx(2 * ss.to("N").magnitude, rel=1e-12)
    with pytest.raises(ValueError, match="plastic_moment_capacity must be positive"):
        simply_supported_plastic_collapse_load(plastic_moment_capacity=_q("0 kN*m"), span=span)
    with pytest.raises(ValueError, match="plastic_moment_capacity must be a"):
        fixed_fixed_plastic_collapse_load(plastic_moment_capacity=_q("50 kN"), span=span)
    # Under a uniform load the collapse intensities are w = 8*M_p/L^2 (SS) and
    # 16*M_p/L^2 (FF), again a 2x redistribution reserve.
    ss_w = simply_supported_plastic_collapse_udl(plastic_moment_capacity=mp, span=span)
    ff_w = fixed_fixed_plastic_collapse_udl(plastic_moment_capacity=mp, span=span)
    assert ss_w.to("kN/m").magnitude == pytest.approx(8 * 50 / 4**2, rel=1e-12)
    assert ff_w.to("kN/m").magnitude == pytest.approx(16 * 50 / 4**2, rel=1e-12)
    assert ff_w.to("N/m").magnitude == pytest.approx(2 * ss_w.to("N/m").magnitude, rel=1e-12)
    # A propped cantilever collapses at w = (6 + 4*sqrt(2))*M_p/L^2 ~ 11.66*M_p/L^2,
    # between the simply-supported 8 and the fixed-fixed 16.
    from math import sqrt

    pc_w = propped_cantilever_plastic_collapse_udl(plastic_moment_capacity=mp, span=span)
    assert pc_w.to("kN/m").magnitude == pytest.approx((6 + 4 * sqrt(2)) * 50 / 4**2, rel=1e-12)
    assert ss_w.to("N/m").magnitude < pc_w.to("N/m").magnitude < ff_w.to("N/m").magnitude
    # Under a central point load the propped cantilever collapses at P = 6*M_p/L,
    # between the SS (4) and FF (8) point-load cases.
    pc_p = propped_cantilever_plastic_collapse_load(plastic_moment_capacity=mp, span=span)
    assert pc_p.to("kN").magnitude == pytest.approx(6 * 50 / 4, rel=1e-12)
    assert ss.to("N").magnitude < pc_p.to("N").magnitude < ff.to("N").magnitude


def test_thermal_buckling_temperature_rise_is_the_sun_kink():
    from math import pi

    # dT_cr = pi^2 / ((K*lambda)^2 * alpha), independent of E: a held steel bar
    # (alpha = 12e-6) at slenderness 100 buckles at ~82 K rise.
    dt = thermal_buckling_temperature_rise(
        slenderness_ratio=100, thermal_expansion_coefficient=_q("12e-6 1/K")
    )
    assert dt.to("K").magnitude == pytest.approx(pi**2 / (100**2 * 12e-6), rel=1e-12)
    assert dt.to("K").magnitude == pytest.approx(82.25, rel=1e-3)
    # A stiffer restraint (fixed-fixed, K = 0.5) tolerates 4x the temperature rise.
    fixed = thermal_buckling_temperature_rise(
        slenderness_ratio=100,
        thermal_expansion_coefficient=_q("12e-6 1/K"),
        end_condition_factor=0.5,
    )
    assert fixed.to("K").magnitude == pytest.approx(4 * dt.to("K").magnitude, rel=1e-12)
    # A stockier bar (lower slenderness) tolerates far more heat before buckling.
    assert thermal_buckling_temperature_rise(
        slenderness_ratio=50, thermal_expansion_coefficient=_q("12e-6 1/K")
    ).to("K").magnitude == pytest.approx(4 * dt.to("K").magnitude, rel=1e-12)
    with pytest.raises(ValueError, match="slenderness_ratio must be positive"):
        thermal_buckling_temperature_rise(
            slenderness_ratio=0, thermal_expansion_coefficient=_q("12e-6 1/K")
        )
    with pytest.raises(ValueError, match="thermal_expansion_coefficient must have units"):
        thermal_buckling_temperature_rise(
            slenderness_ratio=100, thermal_expansion_coefficient=_q("12 MPa")
        )


def test_lateral_torsional_buckling_moment():
    from math import pi, sqrt

    kw = {
        "weak_axis_second_moment": _q("133333 mm**4"),
        "torsion_constant": _q("533333 mm**4"),
        "elastic_modulus": _q("200 GPa"),
        "shear_modulus": _q("79 GPa"),
    }
    # M_cr = (pi/L)*sqrt(E*I_y*G*J).
    m = lateral_torsional_buckling_moment(unbraced_length=_q("2 m"), **kw)
    expected = pi / 2000 * sqrt(200000 * 133333 * 79000 * 533333) / 1000  # N*m
    assert m.to("N*m").magnitude == pytest.approx(expected, rel=1e-9)
    assert m.to("N*m").magnitude == pytest.approx(52652, rel=1e-3)
    # It falls inversely with the unbraced length: brace it and it climbs.
    longer = lateral_torsional_buckling_moment(unbraced_length=_q("4 m"), **kw)
    assert longer.to("N*m").magnitude == pytest.approx(m.to("N*m").magnitude / 2, rel=1e-12)
    with pytest.raises(ValueError, match="weak_axis_second_moment must be a"):
        lateral_torsional_buckling_moment(
            unbraced_length=_q("2 m"),
            weak_axis_second_moment=_q("133333 mm"),
            torsion_constant=_q("533333 mm**4"),
            elastic_modulus=_q("200 GPa"),
            shear_modulus=_q("79 GPa"),
        )


def test_sphere_external_pressure_buckling_beats_the_cylinder():
    from math import sqrt

    kw = {
        "elastic_modulus": _q("200 GPa"),
        "wall_thickness": _q("5 mm"),
        "mean_radius": _q("500 mm"),
    }
    # p_cr = 2*E*(t/R)^2 / sqrt(3*(1-nu^2)).
    sphere = sphere_external_pressure_buckling(**kw, poisson=0.3)
    assert sphere.to("MPa").magnitude == pytest.approx(
        2 * 200e3 * (5 / 500) ** 2 / sqrt(3 * (1 - 0.3**2)), rel=1e-12
    )
    assert sphere.to("MPa").magnitude == pytest.approx(24.21, rel=1e-3)
    # A sphere holds far more external pressure than a cylinder of the same t/R
    # (it rides on (t/R)^2, the cylinder on (t/R)^3) -- why deep hulls are spheres.
    cylinder = cylinder_external_pressure_buckling(**kw, poisson=0.3)
    assert sphere.to("MPa").magnitude > 100 * cylinder.to("MPa").magnitude
    # It rides on the square of the thinness: doubling the wall gives 4x.
    thicker = sphere_external_pressure_buckling(
        elastic_modulus=_q("200 GPa"), wall_thickness=_q("10 mm"), mean_radius=_q("500 mm")
    )
    assert thicker.to("MPa").magnitude == pytest.approx(4 * sphere.to("MPa").magnitude, rel=1e-12)
    with pytest.raises(ValueError, match="wall_thickness must be positive"):
        sphere_external_pressure_buckling(
            elastic_modulus=_q("200 GPa"), wall_thickness=_q("0 mm"), mean_radius=_q("500 mm")
        )


def test_cylinder_axial_buckling_stress_rides_on_the_thin_ratio():
    from math import sqrt

    # sigma_cr = E*(t/R)/sqrt(3*(1-nu^2)): a 2 mm wall at 100 mm radius.
    s = cylinder_axial_buckling_stress(
        elastic_modulus=_q("200 GPa"), wall_thickness=_q("2 mm"), mean_radius=_q("100 mm")
    )
    expected = 200e3 * (2 / 100) / sqrt(3 * (1 - 0.3**2))
    assert s.to("MPa").magnitude == pytest.approx(expected, rel=1e-12)
    assert s.to("MPa").magnitude == pytest.approx(2420.9, rel=1e-3)
    # It rides on t/R linearly (unlike external-pressure collapse's cube), so
    # doubling the wall doubles the critical stress.
    thicker = cylinder_axial_buckling_stress(
        elastic_modulus=_q("200 GPa"), wall_thickness=_q("4 mm"), mean_radius=_q("100 mm")
    )
    assert thicker.to("MPa").magnitude == pytest.approx(2 * s.to("MPa").magnitude, rel=1e-12)
    with pytest.raises(ValueError, match="poisson must lie in"):
        cylinder_axial_buckling_stress(
            elastic_modulus=_q("200 GPa"),
            wall_thickness=_q("2 mm"),
            mean_radius=_q("100 mm"),
            poisson=0.5,
        )


def test_helical_spring_active_coils_for_rate_inverts_the_rate():
    kw = {
        "mean_coil_diameter": _q("30 mm"),
        "wire_diameter": _q("4 mm"),
        "shear_modulus": _q("79 GPa"),
    }
    # N_a = G*d^4/(8*D^3*k); round-trips through helical_spring_rate.
    n = helical_spring_active_coils_for_rate(target_rate=_q("15 N/mm"), **kw)
    assert n == pytest.approx(79000 * 4**4 / (8 * 30**3 * 15), rel=1e-12)
    assert n == pytest.approx(6.242, rel=1e-3)
    back = helical_spring_rate(active_coils=n, **kw)
    assert back.to("N/mm").magnitude == pytest.approx(15.0, rel=1e-12)
    # A softer target needs more coils.
    assert helical_spring_active_coils_for_rate(target_rate=_q("7.5 N/mm"), **kw) == pytest.approx(
        2 * n, rel=1e-12
    )
    with pytest.raises(ValueError, match="target_rate must be a"):
        helical_spring_active_coils_for_rate(target_rate=_q("15 N"), **kw)


def test_helical_spring_solid_length_stacks_the_coils():
    # L_s = N_t*d: 10 total coils of 3 mm wire stack to 30 mm solid.
    ls = helical_spring_solid_length(total_coils=10, wire_diameter=_q("3 mm"))
    assert ls.to("mm").magnitude == pytest.approx(30.0, rel=1e-12)
    # A design must clear the solid height by more than its working deflection: a
    # 60 mm free length gives 30 mm of travel before this spring goes solid.
    free_length = 60.0
    assert free_length - ls.to("mm").magnitude == pytest.approx(30.0, rel=1e-12)
    with pytest.raises(ValueError, match="total_coils must be positive"):
        helical_spring_solid_length(total_coils=0, wire_diameter=_q("3 mm"))
    with pytest.raises(ValueError, match="wire_diameter must be a"):
        helical_spring_solid_length(total_coils=10, wire_diameter=_q("3 N"))


def test_smith_watson_topper_equivalent_stress():
    from math import sqrt

    # Fully reversed (sigma_m = 0, sigma_max = sigma_a) returns the amplitude.
    assert smith_watson_topper_stress(max_stress=_q("50 MPa"), alternating_stress=_q("50 MPa")).to(
        "MPa"
    ).magnitude == pytest.approx(50.0, rel=1e-12)
    # sigma_ar = sqrt(sigma_max * sigma_a): a tensile mean raises it above sigma_a.
    swt = smith_watson_topper_stress(max_stress=_q("150 MPa"), alternating_stress=_q("50 MPa"))
    assert swt.to("MPa").magnitude == pytest.approx(sqrt(150 * 50), rel=1e-12)
    assert swt.to("MPa").magnitude == pytest.approx(86.603, rel=1e-4)
    assert swt.to("MPa").magnitude > 50.0
    # It composes with cyclic_stress_components: sigma_max = mean + amplitude.
    cyc = cyclic_stress_components(max_stress=_q("200 MPa"), min_stress=_q("40 MPa"))
    swt2 = smith_watson_topper_stress(
        max_stress=_q("200 MPa"), alternating_stress=cyc.alternating_stress
    )
    assert swt2.to("MPa").magnitude == pytest.approx(sqrt(200 * 80), rel=1e-12)
    with pytest.raises(ValueError, match="max_stress must be positive"):
        smith_watson_topper_stress(max_stress=_q("-10 MPa"), alternating_stress=_q("50 MPa"))


def test_rankine_gordon_stress_blends_crushing_to_euler():
    # sigma_R = sigma_c / (1 + a*lambda^2): at lambda = 0 it is the crushing stress.
    assert rankine_gordon_stress(
        crushing_stress=_q("320 MPa"), slenderness_ratio=0, rankine_constant=1 / 7500
    ).to("MPa").magnitude == pytest.approx(320.0, rel=1e-12)
    # It falls smoothly as slenderness grows -- one curve, no transition check.
    s100 = rankine_gordon_stress(
        crushing_stress=_q("320 MPa"), slenderness_ratio=100, rankine_constant=1 / 7500
    )
    assert s100.to("MPa").magnitude == pytest.approx(320 / (1 + 10000 / 7500), rel=1e-12)
    assert s100.to("MPa").magnitude == pytest.approx(137.14, rel=1e-3)
    s200 = rankine_gordon_stress(
        crushing_stress=_q("320 MPa"), slenderness_ratio=200, rankine_constant=1 / 7500
    )
    assert s200.to("MPa").magnitude < s100.to("MPa").magnitude
    # A larger Rankine constant (a floppier material like cast iron) drops faster.
    assert (
        rankine_gordon_stress(
            crushing_stress=_q("320 MPa"), slenderness_ratio=100, rankine_constant=1 / 1600
        )
        .to("MPa")
        .magnitude
        < s100.to("MPa").magnitude
    )
    with pytest.raises(ValueError, match="rankine_constant must be positive"):
        rankine_gordon_stress(
            crushing_stress=_q("320 MPa"), slenderness_ratio=100, rankine_constant=0
        )


def test_pendulum_periods():
    from math import pi, sqrt

    # Simple pendulum T = 2*pi*sqrt(L/g): a 1 m pendulum swings in ~2.006 s.
    t = simple_pendulum_period(length=_q("1 m"))
    assert t.to("s").magnitude == pytest.approx(2 * pi * sqrt(1 / 9.80665), rel=1e-12)
    assert t.to("s").magnitude == pytest.approx(2.006, rel=1e-3)
    # Period scales with sqrt(length): 4x length doubles the period.
    assert simple_pendulum_period(length=_q("4 m")).to("s").magnitude == pytest.approx(
        2 * t.to("s").magnitude, rel=1e-12
    )
    # Physical pendulum reduces to the simple one when I = m*d^2 (mass at the end).
    phys = physical_pendulum_period(
        moment_of_inertia=_q("2 kg*m**2"), mass=_q("2 kg"), pivot_distance=_q("1 m")
    )
    assert phys.to("s").magnitude == pytest.approx(t.to("s").magnitude, rel=1e-12)
    # A uniform rod pivoted at its end (I = m*L^2/3, d = L/2): T = 2*pi*sqrt(2L/3g).
    rod = physical_pendulum_period(
        moment_of_inertia=_q(f"{1 / 3} kg*m**2"), mass=_q("1 kg"), pivot_distance=_q("0.5 m")
    )
    assert rod.to("s").magnitude == pytest.approx(2 * pi * sqrt(2 / (3 * 9.80665)), rel=1e-9)
    with pytest.raises(ValueError, match="length must be positive"):
        simple_pendulum_period(length=_q("0 m"))
    with pytest.raises(ValueError, match="moment_of_inertia, mass, and pivot_distance"):
        physical_pendulum_period(
            moment_of_inertia=_q("2 kg*m**2"), mass=_q("2 kg"), pivot_distance=_q("0 m")
        )


def test_tuned_mass_damper_den_hartog_optimum():
    from math import sqrt

    # Optimal tuning f = 1/(1+mu); a 5% absorber tunes ~5% below the main mode.
    assert tuned_mass_damper_optimal_frequency_ratio(mass_ratio=0.05) == pytest.approx(
        1 / 1.05, rel=1e-12
    )
    assert tuned_mass_damper_optimal_frequency_ratio(mass_ratio=0.05) == pytest.approx(
        0.9524, rel=1e-3
    )
    # A heavier absorber tunes lower.
    assert tuned_mass_damper_optimal_frequency_ratio(
        mass_ratio=0.1
    ) < tuned_mass_damper_optimal_frequency_ratio(mass_ratio=0.05)
    # Optimal damping zeta = sqrt(3*mu/(8*(1+mu)^3)); a 5% absorber wants ~13%.
    assert tuned_mass_damper_optimal_damping(mass_ratio=0.05) == pytest.approx(
        sqrt(3 * 0.05 / (8 * 1.05**3)), rel=1e-12
    )
    assert tuned_mass_damper_optimal_damping(mass_ratio=0.05) == pytest.approx(0.1273, rel=1e-3)
    # A heavier absorber wants more damping.
    assert tuned_mass_damper_optimal_damping(mass_ratio=0.1) > tuned_mass_damper_optimal_damping(
        mass_ratio=0.05
    )
    with pytest.raises(ValueError, match="mass_ratio must be positive"):
        tuned_mass_damper_optimal_frequency_ratio(mass_ratio=0)


def test_plate_shear_buckling_coefficient():
    # k_s = 5.34 + 4/(a/b)^2: a square panel gives 9.34, a long one tends to 5.34.
    assert plate_shear_buckling_coefficient(aspect_ratio=1.0) == pytest.approx(9.34, rel=1e-12)
    assert plate_shear_buckling_coefficient(aspect_ratio=2.0) == pytest.approx(6.34, rel=1e-12)
    assert plate_shear_buckling_coefficient(aspect_ratio=100.0) == pytest.approx(5.3404, rel=1e-4)
    # Closer stiffeners (smaller aspect ratio) raise the coefficient.
    assert plate_shear_buckling_coefficient(aspect_ratio=1.5) > plate_shear_buckling_coefficient(
        aspect_ratio=3.0
    )
    # It feeds plate_buckling_stress as the buckling coefficient.
    k = plate_shear_buckling_coefficient(aspect_ratio=2.0)
    tau_cr = plate_buckling_stress(
        buckling_coefficient=k,
        elastic_modulus=_q("200 GPa"),
        thickness=_q("5 mm"),
        width=_q("300 mm"),
    )
    assert tau_cr.to("MPa").magnitude > 0
    with pytest.raises(ValueError, match="aspect_ratio .* must be at least 1"):
        plate_shear_buckling_coefficient(aspect_ratio=0.5)


def test_thin_closed_tube_torsion_generalizes_the_box():
    from math import pi

    # tau = T/(2*A_m*t); it matches the rectangular-box Bredt for a box's A_m.
    area = rectangular_tube_enclosed_area(
        width=_q("100 mm"), height=_q("60 mm"), wall_thickness=_q("5 mm")
    )
    general = thin_closed_tube_torsional_stress(
        torque=_q("500 N*m"), enclosed_area=area, wall_thickness=_q("5 mm")
    )
    box = rectangular_tube_torsional_stress(
        torque=_q("500 N*m"), width=_q("100 mm"), height=_q("60 mm"), wall_thickness=_q("5 mm")
    )
    assert general.to("MPa").magnitude == pytest.approx(box.to("MPa").magnitude, rel=1e-12)
    # For a thin circular tube A_m = pi*r_m^2, matching the direct T/(2*A_m*t).
    circ = thin_closed_tube_torsional_stress(
        torque=_q("500 N*m"), enclosed_area=_q(f"{pi * 47.5**2} mm**2"), wall_thickness=_q("5 mm")
    )
    assert circ.to("MPa").magnitude == pytest.approx(500e3 / (2 * pi * 47.5**2 * 5), rel=1e-12)
    with pytest.raises(ValueError, match="enclosed_area must be positive"):
        thin_closed_tube_torsional_stress(
            torque=_q("500 N*m"), enclosed_area=_q("0 mm**2"), wall_thickness=_q("5 mm")
        )


def test_hertz_sphere_approach_matches_a_squared_over_r():

    kw = {
        "force": _q("1000 N"),
        "diameter1": _q("20 mm"),
        "modulus1": _q("200 GPa"),
        "poisson1": 0.3,
        "modulus2": _q("200 GPa"),
        "poisson2": 0.3,
    }
    approach = hertz_sphere_approach(**kw)
    # delta = a^2 / R: cross-check against the contact-patch radius (R = 10 mm flat).
    contact = hertz_sphere_contact(**kw)
    a = contact.contact_radius.to("mm").magnitude
    assert approach.to("mm").magnitude == pytest.approx(a**2 / 10.0, rel=1e-12)
    # And against the closed form delta = (9 F^2 / (16 R E*^2))^(1/3).
    e_star = 200000 / (2 * (1 - 0.3**2))
    assert approach.to("um").magnitude == pytest.approx(
        (9 * 1000**2 / (16 * 10 * e_star**2)) ** (1 / 3) * 1000, rel=1e-9
    )
    # It grows only as F^(2/3): 8x the load doubles the approach (a contact stiffens).
    harder = hertz_sphere_approach(**{**kw, "force": _q("8000 N")})
    assert harder.to("um").magnitude == pytest.approx(4 * approach.to("um").magnitude, rel=1e-9)
    with pytest.raises(ValueError, match="diameter1 must be positive"):
        hertz_sphere_approach(**{**kw, "diameter1": _q("0 mm")})


def test_plate_compression_buckling_coefficient():
    # k = min over m of (m/gamma + gamma/m)^2; it touches 4 at integer aspect ratios.
    assert plate_compression_buckling_coefficient(aspect_ratio=1.0) == pytest.approx(4.0, rel=1e-12)
    assert plate_compression_buckling_coefficient(aspect_ratio=2.0) == pytest.approx(4.0, rel=1e-12)
    assert plate_compression_buckling_coefficient(aspect_ratio=3.0) == pytest.approx(4.0, rel=1e-12)
    # A short plate (gamma < 1) buckles in one half-wave with a higher coefficient.
    assert plate_compression_buckling_coefficient(aspect_ratio=0.5) == pytest.approx(
        (1 / 0.5 + 0.5) ** 2, rel=1e-12
    )
    # Between integer ratios it rises only slightly (never below 4).
    mid = plate_compression_buckling_coefficient(aspect_ratio=1.4142)
    assert mid == pytest.approx(4.5, rel=1e-3)
    assert mid > 4.0
    # It feeds plate_buckling_stress as the compression coefficient.
    sigma_cr = plate_buckling_stress(
        buckling_coefficient=plate_compression_buckling_coefficient(aspect_ratio=3.0),
        elastic_modulus=_q("200 GPa"),
        thickness=_q("5 mm"),
        width=_q("300 mm"),
    )
    assert sigma_cr.to("MPa").magnitude > 0
    with pytest.raises(ValueError, match="aspect_ratio must be positive"):
        plate_compression_buckling_coefficient(aspect_ratio=0)


def test_triaxial_constrained_thermal_stress_is_the_most_severe():
    kw = {
        "elastic_modulus": _q("200 GPa"),
        "thermal_expansion_coefficient": _q("12e-6 1/K"),
        "temperature_change": _q("100 K"),
    }
    # sigma = E*alpha*dT/(1-2nu): 2.5x the uniaxial for nu = 0.3.
    tri = triaxial_constrained_thermal_stress(**kw, poisson=0.3)
    assert tri.to("MPa").magnitude == pytest.approx(200e3 * 12e-6 * 100 / (1 - 2 * 0.3), rel=1e-12)
    assert tri.to("MPa").magnitude == pytest.approx(600.0, rel=1e-6)
    # It exceeds the biaxial (thermal shock) and uniaxial constraint cases.
    uni = constrained_thermal_stress(**kw)
    bi = thermal_shock_stress(**kw, poisson=0.3)
    assert tri.to("MPa").magnitude > bi.to("MPa").magnitude > uni.to("MPa").magnitude
    assert tri.to("MPa").magnitude == pytest.approx(2.5 * uni.to("MPa").magnitude, rel=1e-12)
    # As nu -> 0.5 (incompressible) the constrained stress diverges.
    near_incompressible = triaxial_constrained_thermal_stress(**kw, poisson=0.49)
    assert near_incompressible.to("MPa").magnitude > 10 * tri.to("MPa").magnitude
    with pytest.raises(ValueError, match=r"poisson must lie in \[0, 0.5\)"):
        triaxial_constrained_thermal_stress(**kw, poisson=0.5)


def test_quality_factor():
    # Q = 1/(2*zeta): light damping gives a tall, sharp resonance.
    assert quality_factor(damping_ratio=0.05) == pytest.approx(10.0, rel=1e-12)
    assert quality_factor(damping_ratio=0.01) == pytest.approx(50.0, rel=1e-12)
    # Lighter damping -> higher Q.
    assert quality_factor(damping_ratio=0.02) > quality_factor(damping_ratio=0.1)
    with pytest.raises(ValueError, match="damping_ratio"):
        quality_factor(damping_ratio=0)


def test_critical_damping_coefficient():
    from math import sqrt

    # c_c = 2*sqrt(k*m): k = 8000 N/m, m = 1 kg -> 178.9 N*s/m.
    cc = critical_damping_coefficient(stiffness=_q("8000 N/m"), mass=_q("1 kg"))
    assert cc.to("N*s/m").magnitude == pytest.approx(2 * sqrt(8000 * 1), rel=1e-12)
    assert cc.to("N*s/m").magnitude == pytest.approx(178.885, rel=1e-4)
    # c_c = 2*m*omega_n, so a target damping ratio needs c = zeta*c_c of damping.
    omega_n = natural_frequency(stiffness=_q("8000 N/m"), mass=_q("1 kg")).to("Hz").magnitude * (
        2 * 3.141592653589793
    )
    assert cc.to("N*s/m").magnitude == pytest.approx(2 * 1 * omega_n, rel=1e-9)
    with pytest.raises(ValueError, match="stiffness and mass must be positive"):
        critical_damping_coefficient(stiffness=_q("0 N/m"), mass=_q("1 kg"))


def test_belt_transmitted_power_and_mean_tension():
    # P = (T1 - T2)*v: 500 N tight, 200 N slack, 20 m/s -> 6 kW.
    p = belt_transmitted_power(
        tight_tension=_q("500 N"), slack_tension=_q("200 N"), belt_speed=_q("20 m/s")
    )
    assert p.to("W").magnitude == pytest.approx((500 - 200) * 20, rel=1e-12)
    assert p.to("kW").magnitude == pytest.approx(6.0, rel=1e-12)
    # T_m = (T1 + T2)/2: the initial tension / shaft side-load driver.
    tm = belt_mean_tension(tight_tension=_q("500 N"), slack_tension=_q("200 N"))
    assert tm.to("N").magnitude == pytest.approx(350.0, rel=1e-12)
    with pytest.raises(ValueError, match="tight_tension .* must exceed slack_tension"):
        belt_transmitted_power(
            tight_tension=_q("200 N"), slack_tension=_q("500 N"), belt_speed=_q("20 m/s")
        )
    with pytest.raises(ValueError, match="belt_speed must be a"):
        belt_transmitted_power(
            tight_tension=_q("500 N"), slack_tension=_q("200 N"), belt_speed=_q("20 N")
        )


def test_goodman_equivalent_reversed_stress():
    # sigma_ar = sigma_a/(1 - sigma_m/S_u): a tensile mean inflates the amplitude.
    r = goodman_equivalent_reversed_stress(
        alternating_stress=_q("50 MPa"), mean_stress=_q("100 MPa"), ultimate_strength=_q("700 MPa")
    )
    assert r.to("MPa").magnitude == pytest.approx(50 / (1 - 100 / 700), rel=1e-12)
    assert r.to("MPa").magnitude == pytest.approx(58.333, rel=1e-4)
    # A fully-reversed cycle (sigma_m = 0) returns the amplitude unchanged.
    assert goodman_equivalent_reversed_stress(
        alternating_stress=_q("50 MPa"), mean_stress=_q("0 MPa"), ultimate_strength=_q("700 MPa")
    ).to("MPa").magnitude == pytest.approx(50.0, rel=1e-12)
    # It differs from the SWT model for the same cycle (Goodman vs SWT lines).
    swt = smith_watson_topper_stress(max_stress=_q("150 MPa"), alternating_stress=_q("50 MPa"))
    assert r.to("MPa").magnitude != pytest.approx(swt.to("MPa").magnitude, rel=1e-2)
    with pytest.raises(ValueError, match="mean_stress .* must be below ultimate_strength"):
        goodman_equivalent_reversed_stress(
            alternating_stress=_q("50 MPa"),
            mean_stress=_q("700 MPa"),
            ultimate_strength=_q("700 MPa"),
        )


def test_morrow_equivalent_reversed_stress_is_less_conservative_than_goodman():
    # sigma_ar = sigma_a/(1 - sigma_m/sigma_f'): uses the true fracture strength.
    morrow = morrow_equivalent_reversed_stress(
        alternating_stress=_q("100 MPa"),
        mean_stress=_q("200 MPa"),
        true_fracture_strength=_q("700 MPa"),
    )
    assert morrow.to("MPa").magnitude == pytest.approx(100 / (1 - 200 / 700), rel=1e-12)
    assert morrow.to("MPa").magnitude == pytest.approx(140.0, rel=1e-4)
    # Because sigma_f' > S_u, Morrow inflates the amplitude less than Goodman does
    # for the same cycle (it is less conservative for a tensile mean).
    goodman = goodman_equivalent_reversed_stress(
        alternating_stress=_q("100 MPa"),
        mean_stress=_q("200 MPa"),
        ultimate_strength=_q("500 MPa"),
    )
    assert morrow.to("MPa").magnitude < goodman.to("MPa").magnitude
    # A fully-reversed cycle returns the amplitude unchanged.
    assert morrow_equivalent_reversed_stress(
        alternating_stress=_q("100 MPa"),
        mean_stress=_q("0 MPa"),
        true_fracture_strength=_q("700 MPa"),
    ).to("MPa").magnitude == pytest.approx(100.0, rel=1e-12)
    with pytest.raises(ValueError, match="mean_stress .* must be below true_fracture_strength"):
        morrow_equivalent_reversed_stress(
            alternating_stress=_q("100 MPa"),
            mean_stress=_q("700 MPa"),
            true_fracture_strength=_q("700 MPa"),
        )


def test_octahedral_shear_stress_is_sqrt2_over_3_of_von_mises():
    from math import sqrt

    # Uniaxial: tau_oct = sqrt(2)/3 * sigma.
    tau = octahedral_shear_stress(sigma_1=_q("100 MPa"), sigma_2=_q("0 MPa"), sigma_3=_q("0 MPa"))
    assert tau.to("MPa").magnitude == pytest.approx(sqrt(2) / 3 * 100, rel=1e-12)
    # It is exactly sqrt(2)/3 of the von Mises stress for the same state.
    triad = {"sigma_1": _q("120 MPa"), "sigma_2": _q("-40 MPa"), "sigma_3": _q("30 MPa")}
    to = octahedral_shear_stress(**triad).to("MPa").magnitude
    vm = von_mises_principal(**triad).to("MPa").magnitude
    assert to == pytest.approx(sqrt(2) / 3 * vm, rel=1e-12)
    # A hydrostatic state (equal principals) has zero octahedral shear.
    assert octahedral_shear_stress(
        sigma_1=_q("50 MPa"), sigma_2=_q("50 MPa"), sigma_3=_q("50 MPa")
    ).to("MPa").magnitude == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(ValueError, match="sigma_1 must be a"):
        octahedral_shear_stress(sigma_1=_q("100 mm"), sigma_2=_q("0 MPa"), sigma_3=_q("0 MPa"))


def test_horizontal_impact_force():
    from math import sqrt

    # F = v*sqrt(m*k): a 10 kg mass at 2 m/s into a 1e6 N/m stop -> 6325 N.
    f = horizontal_impact_force(mass=_q("10 kg"), velocity=_q("2 m/s"), stiffness=_q("1e6 N/m"))
    assert f.to("N").magnitude == pytest.approx(2 * sqrt(10 * 1e6), rel=1e-12)
    assert f.to("N").magnitude == pytest.approx(6324.56, rel=1e-4)
    # F = k*delta_max cross-check: delta_max = v*sqrt(m/k).
    delta_max = 2 * sqrt(10 / 1e6)  # m
    assert f.to("N").magnitude == pytest.approx(1e6 * delta_max, rel=1e-9)
    # A softer stop cushions the blow (force ~ sqrt(k)): quartering k halves F.
    softer = horizontal_impact_force(
        mass=_q("10 kg"), velocity=_q("2 m/s"), stiffness=_q("250000 N/m")
    )
    assert softer.to("N").magnitude == pytest.approx(f.to("N").magnitude / 2, rel=1e-9)
    with pytest.raises(ValueError, match="stiffness must be a"):
        horizontal_impact_force(mass=_q("10 kg"), velocity=_q("2 m/s"), stiffness=_q("1e6 N"))


def test_bearing_equivalent_dynamic_load():
    # P = X*Fr + Y*Fa: combined 4 kN radial + 2 kN axial with X=0.56, Y=1.6.
    p = bearing_equivalent_dynamic_load(
        radial_load=_q("4000 N"), axial_load=_q("2000 N"), radial_factor=0.56, axial_factor=1.6
    )
    assert p.to("N").magnitude == pytest.approx(0.56 * 4000 + 1.6 * 2000, rel=1e-12)
    assert p.to("N").magnitude == pytest.approx(5440.0, rel=1e-12)
    # It feeds the L10 life directly.
    life = bearing_basic_rating_life(dynamic_load_rating=_q("40 kN"), equivalent_load=p)
    assert life > 0
    # Pure radial (X=1, Y=0-ish) is just the radial load.
    assert bearing_equivalent_dynamic_load(
        radial_load=_q("4000 N"), axial_load=_q("0 N"), radial_factor=1.0, axial_factor=1.0
    ).to("N").magnitude == pytest.approx(4000.0, rel=1e-12)
    with pytest.raises(ValueError, match="radial_factor and axial_factor must be positive"):
        bearing_equivalent_dynamic_load(
            radial_load=_q("4000 N"), axial_load=_q("2000 N"), radial_factor=0, axial_factor=1.6
        )


def test_bearing_equivalent_static_load_floors_at_the_radial_load():
    # P0 = max(Fr, X0*Fr + Y0*Fa); deep-groove ball X0=0.6, Y0=0.5.
    # 4 kN radial + 2 kN axial: X0*Fr+Y0*Fa = 3400 N < Fr, so the radial governs.
    p0 = bearing_equivalent_static_load(
        radial_load=_q("4000 N"), axial_load=_q("2000 N"), radial_factor=0.6, axial_factor=0.5
    )
    assert p0.to("N").magnitude == pytest.approx(4000.0, rel=1e-12)
    # A heavier thrust pushes X0*Fr+Y0*Fa above Fr, so the combined form governs.
    heavy_axial = bearing_equivalent_static_load(
        radial_load=_q("4000 N"), axial_load=_q("8000 N"), radial_factor=0.6, axial_factor=0.5
    )
    assert heavy_axial.to("N").magnitude == pytest.approx(0.6 * 4000 + 0.5 * 8000, rel=1e-12)
    assert heavy_axial.to("N").magnitude == pytest.approx(6400.0, rel=1e-12)
    # It feeds the static safety factor s0 = C0/P0.
    s0 = bearing_static_safety_factor(static_load_rating=_q("20 kN"), equivalent_static_load=p0)
    assert s0 == pytest.approx(20000 / 4000, rel=1e-12)
    with pytest.raises(ValueError, match="radial_load and axial_load must be non-negative"):
        bearing_equivalent_static_load(
            radial_load=_q("-1 N"), axial_load=_q("2000 N"), radial_factor=0.6, axial_factor=0.5
        )


def test_bearing_reliability_life_factor_reproduces_the_iso281_table():
    from math import log

    # a1 = (ln(1/R)/ln(1/0.90))^(1/e), e=1.5: at 90% reliability a1 = 1.
    assert bearing_reliability_life_factor(reliability=0.90) == pytest.approx(1.0, rel=1e-12)
    # It reproduces the standard ISO 281 a1 table to two decimals.
    assert bearing_reliability_life_factor(reliability=0.95) == pytest.approx(0.62, abs=5e-3)
    assert bearing_reliability_life_factor(reliability=0.98) == pytest.approx(0.33, abs=5e-3)
    assert bearing_reliability_life_factor(reliability=0.99) == pytest.approx(0.21, abs=5e-3)
    # Match the closed form exactly.
    assert bearing_reliability_life_factor(reliability=0.99) == pytest.approx(
        (log(1 / 0.99) / log(1 / 0.90)) ** (1 / 1.5), rel=1e-12
    )
    # Designing for higher reliability shortens the usable life (a1 < 1).
    assert (
        bearing_reliability_life_factor(reliability=0.99)
        < bearing_reliability_life_factor(reliability=0.95)
        < 1.0
    )
    with pytest.raises(ValueError, match=r"reliability must lie in \(0, 1\)"):
        bearing_reliability_life_factor(reliability=1.0)


def test_bolt_and_member_stiffness_give_a_typical_joint_constant():
    from math import log, pi

    kb = bolt_axial_stiffness(
        nominal_diameter=_q("12 mm"),
        pitch=_q("1.75 mm"),
        grip_length=_q("30 mm"),
        elastic_modulus=_q("200 GPa"),
    )
    # k_b = A_t*E/L: A_t for M12x1.75 is 84.27 mm^2.
    at = (
        bolt_tensile_stress_area(nominal_diameter=_q("12 mm"), pitch=_q("1.75 mm"))
        .to("mm**2")
        .magnitude
    )
    assert kb.to("N/mm").magnitude == pytest.approx(at * 200000 / 30, rel=1e-12)
    # Member frustum (Shigley): matches the closed form.
    km = member_stiffness_frustum(
        nominal_diameter=_q("12 mm"), grip_length=_q("30 mm"), elastic_modulus=_q("200 GPa")
    )
    expected_km = (
        0.5774
        * pi
        * 200000
        * 12
        / (2 * log(5 * (0.5774 * 30 + 0.5 * 12) / (0.5774 * 30 + 2.5 * 12)))
    )
    assert km.to("N/mm").magnitude == pytest.approx(expected_km, rel=1e-12)
    # The members are several times stiffer than the bolt, so C lands in the
    # typical 0.15-0.35 range.
    c = joint_stiffness_factor(bolt_stiffness=kb, member_stiffness=km)
    assert km.to("N/mm").magnitude > kb.to("N/mm").magnitude
    assert 0.15 < c < 0.35
    assert c == pytest.approx(0.189, rel=1e-2)
    with pytest.raises(ValueError, match="grip_length must be positive"):
        bolt_axial_stiffness(
            nominal_diameter=_q("12 mm"),
            pitch=_q("1.75 mm"),
            grip_length=_q("0 mm"),
            elastic_modulus=_q("200 GPa"),
        )


def test_beam_on_elastic_foundation_point_load():
    # beta = (k/(4EI))^0.25: k=50 N/mm^2, E=200 GPa, I=1e6 mm^4.
    kw = {
        "foundation_modulus": _q("50 N/mm**2"),
        "elastic_modulus": _q("200 GPa"),
        "second_moment": _q("1e6 mm**4"),
    }
    beta = foundation_characteristic_parameter(**kw)
    expected_beta = (50.0 / (4.0 * 200e3 * 1e6)) ** 0.25  # 1/mm
    assert beta.to("1/mm").magnitude == pytest.approx(expected_beta, rel=1e-12)
    assert beta.to("1/mm").magnitude == pytest.approx(2.8117e-3, rel=1e-3)
    # y_max = P*beta/(2k), M_max = P/(4*beta) for a 10 kN point load.
    y = beam_on_elastic_foundation_max_deflection(load=_q("10 kN"), **kw)
    m = beam_on_elastic_foundation_max_moment(load=_q("10 kN"), **kw)
    assert y.to("mm").magnitude == pytest.approx(10000.0 * expected_beta / (2 * 50.0), rel=1e-12)
    assert y.to("mm").magnitude == pytest.approx(0.28117, rel=1e-4)
    assert m.to("N*m").magnitude == pytest.approx(10000.0 / (4 * expected_beta) / 1000.0, rel=1e-12)
    assert m.to("N*m").magnitude == pytest.approx(889.14, rel=1e-3)
    # A stiffer foundation localizes the load: bigger beta, smaller peak moment.
    stiffer = beam_on_elastic_foundation_max_moment(
        load=_q("10 kN"),
        foundation_modulus=_q("200 N/mm**2"),
        elastic_modulus=_q("200 GPa"),
        second_moment=_q("1e6 mm**4"),
    )
    assert stiffer.to("N*m").magnitude < m.to("N*m").magnitude


def test_beam_on_elastic_foundation_rejects_bad_inputs():
    good = {
        "foundation_modulus": _q("50 N/mm**2"),
        "elastic_modulus": _q("200 GPa"),
        "second_moment": _q("1e6 mm**4"),
    }
    with pytest.raises(ValueError, match="second_moment must be a"):
        foundation_characteristic_parameter(
            foundation_modulus=_q("50 N/mm**2"),
            elastic_modulus=_q("200 GPa"),
            second_moment=_q("1e6 mm"),
        )
    with pytest.raises(ValueError, match="load must be positive"):
        beam_on_elastic_foundation_max_deflection(load=_q("0 kN"), **good)
