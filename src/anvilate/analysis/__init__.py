"""Anvilate T1 analytical checks: closed-form, deterministic, no solver.

The T1 validation tier screens a design with handbook closed-form solutions
(Roark, Shigley) before any FEA — fast, deterministic, and unit-checked. The
modules:

- :mod:`~anvilate.analysis.axial` — direct axial stress, section area, and the
  minimum area an axial load requires
- :mod:`~anvilate.analysis.beam` — bending (cantilever / simply-supported /
  fixed-fixed / fixed-pinned; point, distributed, triangular, patch, and
  applied-couple loads), transverse shear, shear flow (VQ/I) and built-up-beam
  fastener spacing, section second moments
- :mod:`~anvilate.analysis.plate` — flat-plate bending (simply-supported
  rectangle via the exact Navier series; circular, simply-supported and clamped),
  the clamped-cover thickness a pressure requires, and elastic plate/web buckling
- :mod:`~anvilate.analysis.section` — ``CrossSection`` bundling area, second
  moment, extreme fibre, section modulus, and radius of gyration; the bending
  stress a moment makes and the minimum section modulus it requires
- :mod:`~anvilate.analysis.column` — Euler and Johnson buckling, slenderness,
  and the minimum section second moment a load requires
- :mod:`~anvilate.analysis.torsion` — the torque a power/speed makes, solid and
  hollow shaft torsion, twist, torsional stiffness, and the shaft diameter a
  torque requires; thin-walled rectangular (box) tube torsion (Bredt) and thin
  open-section (strip) torsion
- :mod:`~anvilate.analysis.power_screw` — square-thread lead-screw raise/lower
  torque, efficiency, and the self-locking condition
- :mod:`~anvilate.analysis.worm` — worm-drive reduction ratio, lead angle,
  mesh efficiency, the self-locking condition, and the input tangential force
- :mod:`~anvilate.analysis.clutch` — disc and cone clutch / brake friction torque
  (uniform-wear and uniform-pressure) and the clamp force a torque requires
- :mod:`~anvilate.analysis.pressure_vessel` — thin-wall cylinder and sphere,
  exact Lamé thick-wall cylinder (closed or open ends) and sphere, and the wall
  thickness a pressure requires (membrane and ASME VIII code form)
- :mod:`~anvilate.analysis.interference` — thick-wall press/shrink-fit (Lamé)
- :mod:`~anvilate.analysis.journal_bearing` — journal (plain) bearing Petroff
  friction torque and power loss, unit load, and Sommerfeld number
- :mod:`~anvilate.analysis.contact` — Hertzian point (sphere) and line (cylinder) contact
- :mod:`~anvilate.analysis.coupling` — rigid flange-coupling torque and per-bolt
  shear force
- :mod:`~anvilate.analysis.bearing` — rolling-bearing ISO 281 basic rating life
  (millions of revolutions and running hours) and static load safety factor
- :mod:`~anvilate.analysis.belt` — belt / capstan (Euler-Eytelwein) friction:
  tension ratio, slack tension, transmissible force (still and at speed, with
  centrifugal tension and the max-power belt speed), V-belt wedge friction, and
  belt-drive geometry (length and wrap angle)
- :mod:`~anvilate.analysis.brake` — band-brake torque, the tight-side tension a
  torque requires, the peak lining pressure, and the simple/differential lever
  force; short-shoe (block) brake lever statics; the self-energizing /
  self-locking distinction for both
- :mod:`~anvilate.analysis.curved_beam` — Winkler curved-beam bending
  (rectangular, trapezoidal, circular, and composite T/I/box/stepped sections):
  shifted neutral axis and the unequal inner/outer fibre stresses of hooks,
  clamps, and links
- :mod:`~anvilate.analysis.impact` — drop / suddenly-applied shock-load
  amplification factor (energy method)
- :mod:`~anvilate.analysis.flywheel` — flywheel energy fluctuation, coefficient
  of fluctuation, and the inertia a speed-smoothing target requires
- :mod:`~anvilate.analysis.gear` — spur-gear transmitted/radial/normal tooth loads,
  bevel-gear radial/axial (thrust) resolution about the pitch cone, pitch-line
  velocity, Barth dynamic factor, Lewis tooth-root bending, Hertzian surface
  contact stress, and train kinematics (signed compound-train value, reverted
  coaxial constraint, planetary Willis-equation speeds and ideal torque split,
  whole-tooth planet and assembly checks)
- :mod:`~anvilate.analysis.fastener` — bolt torque-tension, bearing, shear, the
  ISO 898 tensile stress area / axial stress, thread-stripping engagement, and
  preloaded-joint load sharing (stiffness constant, bolt/member load, separation)
- :mod:`~anvilate.analysis.keys` — shaft-key shear and bearing stress, and the
  key length a torque requires
- :mod:`~anvilate.analysis.weld` — fillet-weld throat shear and the weld leg a
  load requires
- :mod:`~anvilate.analysis.rivet` — riveted-joint tearing/shearing/crushing
  strength, governing mode, and efficiency
- :mod:`~anvilate.analysis.spring` — helical-spring shear (Wahl), rate, stored
  energy, series/parallel combination, lateral (column) buckling, leaf-spring
  stress and rate, and the Belleville (disc) washer's Almen-Laszlo
  load-deflection curve and flat load
- :mod:`~anvilate.analysis.thermal` — thermal growth, constrained thermal
  stress, shrink-fit assembly temperature, and CTE-mismatch (differential)
  joint stress
- :mod:`~anvilate.analysis.dynamics` — modal screens: SDOF and Rayleigh
  estimates, the Dunkerley multi-mass combination, distributed-mass beam
  fundamentals, disc-on-shaft torsional mode
- :mod:`~anvilate.analysis.stress` — von Mises combination, combined axial+bending
- :mod:`~anvilate.analysis.fatigue` — Goodman, Soderberg, and Gerber fatigue,
  the max/min → amplitude/mean cyclic-stress converter, the fatigue notch factor,
  the steel endurance-limit estimate with its Marin correction to the real
  part, the Basquin S-N finite-life law, and
  Palmgren-Miner cumulative damage over a load spectrum

Further analytical cases land here as they are built out (see
openspec/specs/validation-gauntlet/).
"""

from __future__ import annotations

from .axial import axial_stress, circular_area, required_axial_area
from .beam import (
    SHEAR_FORM_CIRCULAR,
    SHEAR_FORM_RECTANGULAR,
    BeamBendingResult,
    cantilever_center_patch_load,
    cantilever_end_load,
    cantilever_end_moment,
    cantilever_offset_load,
    cantilever_offset_moment,
    cantilever_partial_uniform_load,
    cantilever_triangular_load,
    cantilever_triangular_load_peak_at_tip,
    cantilever_uniform_load,
    circular_second_moment,
    deflection_scorecard,
    fastener_spacing_for_shear_flow,
    fixed_fixed_center_load,
    fixed_fixed_center_patch_load,
    fixed_fixed_offset_load,
    fixed_fixed_partial_uniform_load,
    fixed_fixed_triangular_load,
    fixed_fixed_uniform_load,
    fixed_pinned_center_load,
    fixed_pinned_center_patch_load,
    fixed_pinned_end_moment,
    fixed_pinned_offset_load,
    fixed_pinned_partial_uniform_load,
    fixed_pinned_triangular_load,
    fixed_pinned_triangular_load_peak_at_prop,
    fixed_pinned_uniform_load,
    hollow_circular_second_moment,
    max_transverse_shear_stress,
    overhang_tip_load,
    overhang_uniform_load,
    rectangular_second_moment,
    shear_flow,
    simply_supported_center_load,
    simply_supported_center_patch_load,
    simply_supported_end_moment,
    simply_supported_offset_load,
    simply_supported_offset_moment,
    simply_supported_partial_uniform_load,
    simply_supported_symmetric_point_loads,
    simply_supported_triangular_load,
    simply_supported_uniform_load,
    span_deflection_limit,
)
from .bearing import (
    BALL_BEARING_LIFE_EXPONENT,
    ROLLER_BEARING_LIFE_EXPONENT,
    bearing_basic_rating_life,
    bearing_life_hours,
    bearing_static_safety_factor,
)
from .belt import (
    belt_centrifugal_tension,
    belt_length,
    belt_max_transmissible_force,
    belt_max_transmissible_force_at_speed,
    belt_slack_tension,
    belt_speed_for_max_power,
    belt_wrap_angle,
    capstan_tension_ratio,
    vee_belt_effective_friction,
)
from .brake import (
    band_brake_max_lining_pressure,
    band_brake_tight_tension_for_torque,
    band_brake_torque,
    differential_band_brake_actuation_force,
    differential_band_brake_is_self_locking,
    short_shoe_brake_torque,
    short_shoe_is_self_locking,
    short_shoe_normal_force,
)
from .clutch import (
    UNIFORM_PRESSURE,
    UNIFORM_WEAR,
    cone_clutch_torque,
    disc_clutch_force_for_torque,
    disc_clutch_torque,
)
from .column import (
    ColumnEnd,
    euler_buckling_load,
    euler_critical_stress,
    euler_second_moment_for_load,
    johnson_critical_stress,
    radius_of_gyration,
    secant_column_max_stress,
    slenderness_ratio,
    transition_slenderness,
)
from .contact import (
    HertzContact,
    HertzLineContact,
    hertz_cylinder_contact,
    hertz_effective_modulus,
    hertz_sphere_contact,
)
from .coupling import (
    flange_coupling_bolt_force,
    flange_coupling_torque,
)
from .curved_beam import (
    CurvedBeamStress,
    circular_curved_beam_stress,
    composite_curved_beam_stress,
    rectangular_curved_beam_stress,
    trapezoidal_curved_beam_stress,
)
from .dynamics import (
    STANDARD_GRAVITY,
    cantilever_fundamental_frequency,
    clamped_annular_plate_fundamental_frequency,
    clamped_circular_plate_fundamental_frequency,
    clamped_plate_fundamental_frequency,
    dunkerley_fundamental_frequency,
    fixed_fixed_fundamental_frequency,
    fixed_pinned_fundamental_frequency,
    frequency_scorecard,
    natural_frequency,
    natural_frequency_from_deflection,
    simply_supported_annular_plate_fundamental_frequency,
    simply_supported_circular_plate_fundamental_frequency,
    simply_supported_fundamental_frequency,
    simply_supported_plate_fundamental_frequency,
    solid_disc_polar_mass_moment,
    spring_surge_frequency,
    torsional_natural_frequency,
)
from .fastener import (
    NUT_FACTOR_AS_RECEIVED,
    bearing_stress,
    bolt_axial_stress,
    bolt_diameter_for_shear,
    bolt_load_in_joint,
    bolt_preload_from_torque,
    bolt_shear_stress,
    bolt_tensile_stress_area,
    joint_separation_load,
    joint_stiffness_factor,
    member_clamp_load_in_joint,
    preloaded_bolt_cyclic_stress,
    thread_engagement_for_load,
    thread_stripping_shear_area,
    thread_stripping_stress,
    torque_for_preload,
)
from .fatigue import (
    CyclicStress,
    basquin_cycles_to_failure,
    basquin_stress_for_life,
    cyclic_stress_components,
    estimated_endurance_limit,
    fatigue_notch_factor,
    gerber_safety_factor,
    gerber_scorecard,
    goodman_safety_factor,
    goodman_scorecard,
    marin_endurance_limit,
    miner_cumulative_damage,
    miner_spectrum_repeats_to_failure,
    soderberg_safety_factor,
    soderberg_scorecard,
)
from .flywheel import (
    coefficient_of_fluctuation,
    flywheel_energy_fluctuation,
    flywheel_inertia_for_fluctuation,
)
from .gear import (
    PlanetaryTorques,
    barth_velocity_factor,
    bevel_gear_axial_load,
    bevel_gear_radial_load,
    bevel_pitch_cone_angle,
    gear_contact_stress,
    gear_normal_load,
    gear_radial_load,
    gear_tangential_load,
    gear_train_value,
    lewis_bending_stress,
    pitch_line_velocity,
    planetary_can_assemble,
    planetary_planet_teeth,
    planetary_speed,
    planetary_torques,
    reverted_train_is_coaxial,
)
from .impact import (
    SUDDENLY_APPLIED_FACTOR,
    impact_factor,
    impact_stress,
)
from .interference import (
    InterferenceFit,
    interference_axial_capacity,
    interference_fit,
    interference_for_contact_pressure,
    interference_torque_capacity,
)
from .journal_bearing import (
    journal_bearing_unit_load,
    petroff_friction_power,
    petroff_friction_torque,
    sommerfeld_number,
)
from .keys import (
    KeyLengthRequirement,
    key_bearing_stress,
    key_length_for_torque,
    key_shear_stress,
    key_tangential_force,
)
from .plate import (
    PlateBendingResult,
    clamped_annular_plate_uniform_load,
    clamped_circular_plate_thickness_for_pressure,
    clamped_circular_plate_uniform_load,
    clamped_plate_uniform_load,
    plate_buckling_stress,
    simply_supported_annular_plate_uniform_load,
    simply_supported_circular_plate_uniform_load,
    simply_supported_plate_center_patch_load,
    simply_supported_plate_uniform_load,
)
from .power_screw import (
    lead_angle,
    power_screw_efficiency,
    power_screw_is_self_locking,
    power_screw_lower_torque,
    power_screw_raise_torque,
)
from .pressure_vessel import (
    ThickWallSphereStress,
    ThickWallStress,
    ThinWallStress,
    asme_cylinder_thickness,
    thick_wall_cylinder,
    thick_wall_sphere,
    thin_wall_cylinder,
    thin_wall_sphere_stress,
    thin_wall_thickness_for_pressure,
)
from .rivet import (
    RivetedJointStrength,
    riveted_joint_efficiency,
)
from .section import CrossSection, bending_stress, required_section_modulus
from .spring import (
    BELLEVILLE_PLATEAU_RATIO,
    SPRING_END_CLAMPED_FREE,
    SPRING_END_FIXED_HINGED,
    SPRING_END_HINGED_HINGED,
    SPRING_END_PARALLEL_PLATES,
    SpringBucklingResult,
    belleville_flat_load,
    belleville_washer_force,
    helical_spring_buckling,
    helical_spring_rate,
    leaf_spring_rate,
    leaf_spring_stress,
    spring_index,
    spring_shear_stress,
    spring_stored_energy,
    springs_in_parallel,
    springs_in_series,
    wahl_factor,
)
from .stress import (
    CombinedNormalStress,
    combine_axial_bending,
    concentrated_stress,
    max_shear_stress_plane,
    principal_stresses_plane,
    strength_scorecard,
    tresca_equivalent_stress,
    tresca_principal,
    von_mises_bending_torsion,
    von_mises_plane_stress,
    von_mises_principal,
    yield_safety_factor,
)
from .thermal import (
    DifferentialThermalStress,
    constrained_thermal_stress,
    differential_thermal_stress,
    free_thermal_expansion,
    shrink_fit_assembly_temperature,
)
from .torsion import (
    hollow_shaft_diameter_for_bending_torsion,
    hollow_shaft_torsional_stress,
    hollow_shaft_twist_angle,
    polar_second_moment_hollow,
    polar_second_moment_solid,
    rectangular_tube_enclosed_area,
    rectangular_tube_torsional_stress,
    rectangular_tube_twist_angle,
    shaft_diameter_for_bending_torsion,
    shaft_diameter_for_torque,
    shaft_torsional_stiffness,
    shaft_torsional_stress,
    shaft_twist_angle,
    shaft_von_mises_stress,
    thin_open_strip_torsion_constant,
    thin_open_strip_torsional_stress,
    thin_open_strip_twist_angle,
    torque_from_power,
)
from .weld import (
    FILLET_THROAT_FACTOR,
    fillet_weld_leg_for_load,
    fillet_weld_throat_stress,
)
from .worm import (
    worm_gear_efficiency,
    worm_gear_ratio,
    worm_is_self_locking,
    worm_lead_angle,
    worm_tangential_force,
)

__all__ = [
    "axial_stress",
    "circular_area",
    "required_axial_area",
    "BeamBendingResult",
    "cantilever_center_patch_load",
    "cantilever_end_load",
    "cantilever_end_moment",
    "cantilever_offset_load",
    "cantilever_offset_moment",
    "cantilever_partial_uniform_load",
    "cantilever_triangular_load",
    "cantilever_triangular_load_peak_at_tip",
    "cantilever_uniform_load",
    "simply_supported_center_load",
    "simply_supported_center_patch_load",
    "simply_supported_end_moment",
    "simply_supported_offset_load",
    "simply_supported_offset_moment",
    "simply_supported_partial_uniform_load",
    "simply_supported_symmetric_point_loads",
    "simply_supported_triangular_load",
    "simply_supported_uniform_load",
    "fixed_fixed_center_load",
    "fixed_fixed_center_patch_load",
    "fixed_fixed_offset_load",
    "fixed_fixed_partial_uniform_load",
    "fixed_fixed_triangular_load",
    "fixed_fixed_uniform_load",
    "fixed_pinned_center_load",
    "fixed_pinned_center_patch_load",
    "fixed_pinned_end_moment",
    "fixed_pinned_offset_load",
    "fixed_pinned_partial_uniform_load",
    "fixed_pinned_triangular_load",
    "fixed_pinned_triangular_load_peak_at_prop",
    "fixed_pinned_uniform_load",
    "overhang_tip_load",
    "overhang_uniform_load",
    "rectangular_second_moment",
    "circular_second_moment",
    "hollow_circular_second_moment",
    "CrossSection",
    "bending_stress",
    "required_section_modulus",
    "RivetedJointStrength",
    "riveted_joint_efficiency",
    "max_transverse_shear_stress",
    "shear_flow",
    "fastener_spacing_for_shear_flow",
    "deflection_scorecard",
    "span_deflection_limit",
    "SHEAR_FORM_RECTANGULAR",
    "SHEAR_FORM_CIRCULAR",
    "BALL_BEARING_LIFE_EXPONENT",
    "ROLLER_BEARING_LIFE_EXPONENT",
    "bearing_basic_rating_life",
    "bearing_life_hours",
    "bearing_static_safety_factor",
    "capstan_tension_ratio",
    "belt_slack_tension",
    "belt_max_transmissible_force",
    "belt_centrifugal_tension",
    "belt_max_transmissible_force_at_speed",
    "belt_speed_for_max_power",
    "vee_belt_effective_friction",
    "belt_length",
    "belt_wrap_angle",
    "band_brake_torque",
    "band_brake_tight_tension_for_torque",
    "band_brake_max_lining_pressure",
    "differential_band_brake_actuation_force",
    "differential_band_brake_is_self_locking",
    "short_shoe_normal_force",
    "short_shoe_brake_torque",
    "short_shoe_is_self_locking",
    "CurvedBeamStress",
    "rectangular_curved_beam_stress",
    "trapezoidal_curved_beam_stress",
    "circular_curved_beam_stress",
    "composite_curved_beam_stress",
    "ColumnEnd",
    "euler_buckling_load",
    "euler_second_moment_for_load",
    "radius_of_gyration",
    "slenderness_ratio",
    "euler_critical_stress",
    "transition_slenderness",
    "johnson_critical_stress",
    "secant_column_max_stress",
    "UNIFORM_WEAR",
    "UNIFORM_PRESSURE",
    "disc_clutch_torque",
    "disc_clutch_force_for_torque",
    "cone_clutch_torque",
    "STANDARD_GRAVITY",
    "natural_frequency",
    "natural_frequency_from_deflection",
    "dunkerley_fundamental_frequency",
    "cantilever_fundamental_frequency",
    "simply_supported_fundamental_frequency",
    "fixed_fixed_fundamental_frequency",
    "fixed_pinned_fundamental_frequency",
    "simply_supported_plate_fundamental_frequency",
    "clamped_plate_fundamental_frequency",
    "simply_supported_circular_plate_fundamental_frequency",
    "clamped_circular_plate_fundamental_frequency",
    "simply_supported_annular_plate_fundamental_frequency",
    "clamped_annular_plate_fundamental_frequency",
    "torsional_natural_frequency",
    "solid_disc_polar_mass_moment",
    "frequency_scorecard",
    "NUT_FACTOR_AS_RECEIVED",
    "bolt_preload_from_torque",
    "torque_for_preload",
    "bearing_stress",
    "bolt_shear_stress",
    "bolt_diameter_for_shear",
    "bolt_tensile_stress_area",
    "bolt_axial_stress",
    "thread_stripping_shear_area",
    "thread_stripping_stress",
    "thread_engagement_for_load",
    "joint_stiffness_factor",
    "bolt_load_in_joint",
    "member_clamp_load_in_joint",
    "joint_separation_load",
    "preloaded_bolt_cyclic_stress",
    "goodman_safety_factor",
    "goodman_scorecard",
    "soderberg_safety_factor",
    "soderberg_scorecard",
    "gerber_safety_factor",
    "gerber_scorecard",
    "miner_cumulative_damage",
    "miner_spectrum_repeats_to_failure",
    "basquin_cycles_to_failure",
    "basquin_stress_for_life",
    "CyclicStress",
    "cyclic_stress_components",
    "estimated_endurance_limit",
    "marin_endurance_limit",
    "fatigue_notch_factor",
    "coefficient_of_fluctuation",
    "flywheel_energy_fluctuation",
    "flywheel_inertia_for_fluctuation",
    "SUDDENLY_APPLIED_FACTOR",
    "impact_factor",
    "impact_stress",
    "gear_tangential_load",
    "gear_radial_load",
    "gear_normal_load",
    "bevel_pitch_cone_angle",
    "bevel_gear_radial_load",
    "bevel_gear_axial_load",
    "pitch_line_velocity",
    "barth_velocity_factor",
    "lewis_bending_stress",
    "gear_contact_stress",
    "gear_train_value",
    "reverted_train_is_coaxial",
    "planetary_planet_teeth",
    "planetary_can_assemble",
    "planetary_speed",
    "PlanetaryTorques",
    "planetary_torques",
    "key_tangential_force",
    "key_shear_stress",
    "key_bearing_stress",
    "KeyLengthRequirement",
    "key_length_for_torque",
    "polar_second_moment_solid",
    "polar_second_moment_hollow",
    "shaft_torsional_stress",
    "shaft_von_mises_stress",
    "shaft_diameter_for_torque",
    "shaft_diameter_for_bending_torsion",
    "hollow_shaft_diameter_for_bending_torsion",
    "hollow_shaft_torsional_stress",
    "torque_from_power",
    "shaft_twist_angle",
    "hollow_shaft_twist_angle",
    "shaft_torsional_stiffness",
    "rectangular_tube_enclosed_area",
    "rectangular_tube_torsional_stress",
    "rectangular_tube_twist_angle",
    "thin_open_strip_torsion_constant",
    "thin_open_strip_torsional_stress",
    "thin_open_strip_twist_angle",
    "PlateBendingResult",
    "simply_supported_plate_uniform_load",
    "simply_supported_plate_center_patch_load",
    "clamped_plate_uniform_load",
    "simply_supported_circular_plate_uniform_load",
    "clamped_circular_plate_uniform_load",
    "simply_supported_annular_plate_uniform_load",
    "clamped_annular_plate_uniform_load",
    "clamped_circular_plate_thickness_for_pressure",
    "plate_buckling_stress",
    "lead_angle",
    "power_screw_raise_torque",
    "power_screw_lower_torque",
    "power_screw_efficiency",
    "power_screw_is_self_locking",
    "worm_gear_ratio",
    "worm_lead_angle",
    "worm_gear_efficiency",
    "worm_is_self_locking",
    "worm_tangential_force",
    "ThinWallStress",
    "ThickWallStress",
    "ThickWallSphereStress",
    "thin_wall_cylinder",
    "thin_wall_thickness_for_pressure",
    "asme_cylinder_thickness",
    "thick_wall_cylinder",
    "thin_wall_sphere_stress",
    "thick_wall_sphere",
    "InterferenceFit",
    "interference_fit",
    "interference_for_contact_pressure",
    "interference_axial_capacity",
    "interference_torque_capacity",
    "petroff_friction_torque",
    "petroff_friction_power",
    "journal_bearing_unit_load",
    "sommerfeld_number",
    "hertz_effective_modulus",
    "HertzContact",
    "hertz_sphere_contact",
    "HertzLineContact",
    "hertz_cylinder_contact",
    "flange_coupling_torque",
    "flange_coupling_bolt_force",
    "spring_index",
    "wahl_factor",
    "spring_shear_stress",
    "helical_spring_rate",
    "SPRING_END_PARALLEL_PLATES",
    "SPRING_END_FIXED_HINGED",
    "SPRING_END_HINGED_HINGED",
    "SPRING_END_CLAMPED_FREE",
    "SpringBucklingResult",
    "helical_spring_buckling",
    "spring_stored_energy",
    "springs_in_series",
    "springs_in_parallel",
    "BELLEVILLE_PLATEAU_RATIO",
    "belleville_washer_force",
    "belleville_flat_load",
    "leaf_spring_stress",
    "leaf_spring_rate",
    "spring_surge_frequency",
    "von_mises_plane_stress",
    "von_mises_bending_torsion",
    "von_mises_principal",
    "principal_stresses_plane",
    "max_shear_stress_plane",
    "tresca_equivalent_stress",
    "tresca_principal",
    "yield_safety_factor",
    "strength_scorecard",
    "CombinedNormalStress",
    "combine_axial_bending",
    "concentrated_stress",
    "constrained_thermal_stress",
    "free_thermal_expansion",
    "shrink_fit_assembly_temperature",
    "DifferentialThermalStress",
    "differential_thermal_stress",
    "FILLET_THROAT_FACTOR",
    "fillet_weld_throat_stress",
    "fillet_weld_leg_for_load",
]
