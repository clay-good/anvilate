"""Anvilate T1 analytical checks: closed-form, deterministic, no solver.

The T1 validation tier screens a design with handbook closed-form solutions
(Roark, Shigley) before any FEA — fast, deterministic, and unit-checked. The
modules:

- :mod:`~anvilate.analysis.axial` — direct axial stress, section area, the
  minimum area an axial load requires, and the axial elongation and stiffness
- :mod:`~anvilate.analysis.beam` — bending (cantilever / simply-supported /
  fixed-fixed / fixed-pinned; point, distributed, triangular, patch, and
  applied-couple loads), transverse shear, shear flow (VQ/I) and built-up-beam
  fastener spacing, section second moments (rectangular, circular, hollow circle,
  box tube, and I-section), the plastic section modulus / fully-plastic hinge
  moment (solid and hollow rectangle and circle, I-section), the plastic
  collapse load (point and distributed) of a simply-supported, fixed-fixed, and
  propped-cantilever beam, and the bearing-misalignment slope (simply-supported end
  under a central or distributed load, and cantilever tip under an end or
  distributed load)
- :mod:`~anvilate.analysis.beam_foundation` — beam on a continuous elastic
  foundation (Hetényi): the characteristic parameter β, and the peak deflection and
  bending moment a point load makes on a long (effectively infinite) beam
- :mod:`~anvilate.analysis.plate` — flat-plate bending (simply-supported
  rectangle via the exact Navier series; circular, simply-supported and clamped,
  under uniform pressure or a central point load), the clamped-cover thickness a
  pressure requires, elastic plate/web buckling,
  and the compression/shear-buckling coefficients
- :mod:`~anvilate.analysis.section` — ``CrossSection`` bundling area, second
  moment, extreme fibre, section modulus, and radius of gyration; the bending
  stress a moment makes and the minimum section modulus it requires
- :mod:`~anvilate.analysis.column` — Euler and Johnson buckling, slenderness,
  the minimum section second moment a load requires, the eccentric-load secant
  stress, the Perry-Robertson imperfect-column stress, the lateral-torsional
  buckling moment of an unbraced beam, and the empirical Rankine-Gordon column
  stress
- :mod:`~anvilate.analysis.torsion` — the torque a power/speed makes, solid and
  hollow shaft torsion, twist, torsional stiffness, and the shaft diameter a
  torque requires; thin-walled rectangular (box) tube torsion (Bredt), thin
  open-section (strip) torsion, general closed thin-tube (Bredt) torsion, and
  solid rectangular, elliptical, and equilateral-triangle bar torsion
- :mod:`~anvilate.analysis.power_screw` — square-thread lead-screw raise/lower
  torque, efficiency, the self-locking condition, and the collar (thrust-bearing)
  friction torque
- :mod:`~anvilate.analysis.worm` — worm-drive reduction ratio, lead angle,
  mesh efficiency, the self-locking condition, and the input tangential and
  separating (radial) tooth forces
- :mod:`~anvilate.analysis.clutch` — disc and cone clutch / brake friction torque
  (uniform-wear and uniform-pressure) and the clamp force a torque requires
- :mod:`~anvilate.analysis.pressure_vessel` — thin-wall cylinder and sphere,
  exact Lamé thick-wall cylinder (closed or open ends) and sphere, the wall
  thickness a pressure requires (membrane and ASME VIII code form), and the
  external-pressure collapse (buckling) pressure of a long cylinder and a sphere,
  the classical axial-compression buckling stress of a thin cylindrical shell, and
  the diametral growth a pressurized thin cylinder or sphere breathes
- :mod:`~anvilate.analysis.interference` — thick-wall press/shrink-fit (Lamé)
- :mod:`~anvilate.analysis.journal_bearing` — journal (plain) bearing Petroff
  friction torque and power loss, unit load, Sommerfeld number, and the minimum
  oil-film thickness from the eccentricity ratio
- :mod:`~anvilate.analysis.contact` — Hertzian point (sphere) and line (cylinder) contact
- :mod:`~anvilate.analysis.coupling` — rigid flange-coupling torque and per-bolt
  shear force
- :mod:`~anvilate.analysis.bearing` — rolling-bearing ISO 281 basic rating life
  (millions of revolutions and running hours), static load safety factor, the
  combined-load equivalent dynamic and static loads, and the reliability
  life-adjustment factor a₁
- :mod:`~anvilate.analysis.belt` — belt / capstan (Euler-Eytelwein) friction:
  tension ratio, slack tension, transmissible force (still and at speed, with
  centrifugal tension and the max-power belt speed), V-belt wedge friction,
  open- and crossed-belt-drive geometry (length and wrap angle), transmitted power,
  and mean tension
- :mod:`~anvilate.analysis.chain` — roller-chain drive geometry: chain length in
  pitches, mean chain speed, the chordal (polygon-action) speed variation of
  a sprocket, and the working tension from transmitted power
- :mod:`~anvilate.analysis.cable` — uniformly loaded cable (parabolic) midspan
  sag, peak support tension, and developed arc length, and the exact catenary
  (heavy-cable) sag, arc length, and peak tension
- :mod:`~anvilate.analysis.cam` — cam-follower rise kinematics (SHM, cycloidal,
  parabolic, and 3-4-5 polynomial profiles): follower displacement, velocity, and
  acceleration at a cam angle, and the translating roller-follower pressure angle
- :mod:`~anvilate.analysis.geneva` — external Geneva (intermittent-indexing)
  mechanism geometry: index angle, crank and driven engagement radii, and the
  advance/dwell fraction of the cycle
- :mod:`~anvilate.analysis.slider_crank` — slider-crank (piston) exact
  displacement from top dead centre, slider velocity, slider acceleration, and the
  connecting-rod obliquity side thrust on the piston
- :mod:`~anvilate.analysis.scotch_yoke` — scotch-yoke pure simple-harmonic
  displacement, velocity, and acceleration (the infinite-rod slider-crank limit)
- :mod:`~anvilate.analysis.fourbar` — four-bar linkage Grashof rotatability
  criterion, mechanism-type classification, and the transmission angle at a given
  input angle
- :mod:`~anvilate.analysis.brake` — band-brake torque, the tight-side tension a
  torque requires, the peak lining pressure, and the simple/differential lever
  force; short-shoe (block) brake lever statics; the self-energizing /
  self-locking distinction for both
- :mod:`~anvilate.analysis.curved_beam` — Winkler curved-beam bending
  (rectangular, trapezoidal, circular, and composite T/I/box/stepped sections):
  shifted neutral axis and the unequal inner/outer fibre stresses of hooks,
  clamps, and links; and the thin circular ring's diametral deflection, peak
  moment under opposing loads, and external-pressure buckling load
- :mod:`~anvilate.analysis.impact` — drop / suddenly-applied shock-load
  amplification factor and the horizontal (kinetic-energy) impact force
  (energy method)
- :mod:`~anvilate.analysis.flywheel` — flywheel energy fluctuation, coefficient
  of fluctuation, the inertia a speed-smoothing target requires, the rotating
  thin-rim hoop (bursting) stress, burst speed, and radial growth, the solid
  spinning disc's peak centre stress and its full radial/tangential stress
  distribution at any radius, and the annular (bored) disc's bore stress and full
  radial/tangential distribution
- :mod:`~anvilate.analysis.gear` — spur-gear transmitted/radial/normal tooth loads,
  bevel-gear radial/axial (thrust) resolution about the pitch cone, helical-gear
  axial thrust, radial load, and virtual tooth number, pitch-line
  velocity, Barth dynamic factor, Lewis tooth-root bending and the module a bending
  allowable requires, Hertzian surface
  contact stress, the mesh contact ratio, the minimum teeth to avoid undercut,
  the involute function and its Newton inverse, base tangent length (span
  measurement), the arc tooth thickness at any radius (top-land pointed-tooth check),
  and the operating pressure angle and profile-shift sum for a non-standard centre,
  and train kinematics (signed compound-train value, reverted coaxial constraint,
  planetary Willis-equation speeds and ideal torque split, whole-tooth planet and
  assembly checks)
- :mod:`~anvilate.analysis.fastener` — bolt torque-tension, bearing, shear, the
  ISO 898 tensile stress area / axial stress, the proof load and recommended
  preload, thread-stripping engagement, and
  preloaded-joint load sharing (bolt and member stiffness, stiffness constant,
  bolt/member load, separation), and the peak fastener force in an
  eccentrically-loaded shear group (AISC elastic method)
- :mod:`~anvilate.analysis.keys` — shaft-key shear and bearing stress, and the
  key length a torque requires
- :mod:`~anvilate.analysis.o_ring` — O-ring gland design geometry: the squeeze,
  gland-fill, and stretch fractions a groove must keep in band to seal without
  extruding or over-straining the ring
- :mod:`~anvilate.analysis.living_hinge` — moulded living-hinge fold strain
  ε = θ·t/(2·L) and the minimum web length a permissible flexural strain requires
- :mod:`~anvilate.analysis.weld` — fillet-weld throat shear, the weld leg a
  load requires, and the peak throat stress of an eccentrically-loaded weld group
  (AISC elastic method)
- :mod:`~anvilate.analysis.rivet` — riveted-joint tearing/shearing/crushing
  strength, governing mode, and efficiency
- :mod:`~anvilate.analysis.rigging` — multi-leg sling lifting statics: the
  sling-angle tension multiplier 1/sin θ, each leg's tension, and the inward
  horizontal force at the pick points (the eyebolt/lifting-beam side load)
- :mod:`~anvilate.analysis.spring` — helical-spring shear (Wahl), rate, active
  coils for a rate, solid (fully-compressed) length, stored
  energy, series/parallel combination, lateral (column) buckling, leaf-spring
  stress and rate, the helical torsion spring's angular rate and inner-fibre
  bending stress, the Belleville (disc) washer's Almen-Laszlo load-deflection
  curve and flat load, and the flat spiral (clock) spring's rate and stress
- :mod:`~anvilate.analysis.thermal` — thermal growth, constrained thermal
  stress, thermal-shock (quench) surface stress, the thermal-buckling ("sun kink")
  temperature rise of a held bar, the triaxial (fully-constrained) thermal stress,
  the through-wall linear-gradient bending stress of a restrained wall,
  shrink-fit assembly temperature, CTE-mismatch (differential) joint stress, and the
  Timoshenko bimetallic-strip curvature and cantilever tip deflection
- :mod:`~anvilate.analysis.dynamics` — modal screens: SDOF and Rayleigh
  estimates, the mass-on-beam frequencies (cantilever tip, simply-supported and
  fixed-fixed central, with the Rayleigh beam-mass correction), the Dunkerley
  multi-mass combination, distributed-mass beam
  fundamentals, taut-string/cable transverse modes, disc-on-shaft and two-rotor
  drivetrain torsional modes,
  and damped-vibration measures (damped frequency, log decrement, quality factor,
  critical damping coefficient, isolator transmissibility and its design inverse
  (the mount natural frequency and static deflection a target isolation needs),
  forced-response dynamic
  magnification and phase, and the base-excitation seismic-instrument response);
  simple and physical (rigid-body) pendulum periods; the solid-disc and annular
  (hollow-cylinder) polar mass moments of inertia;
  and the Den Hartog tuned-mass-damper optimal tuning
- :mod:`~anvilate.analysis.stress` — von Mises and octahedral-shear combination,
  the plane principal stresses and their orientation angle, the maximum shear,
  Tresca, combined axial+bending, and the Inglis elliptical-hole
  stress-concentration factor
- :mod:`~anvilate.analysis.fracture` — linear-elastic fracture mechanics: mode-I
  stress-intensity factor, the critical crack length for fast fracture, and the
  Paris-Erdogan fatigue crack-growth rate and integrated propagation life
- :mod:`~anvilate.analysis.fatigue` — Goodman, Soderberg, and Gerber fatigue,
  the max/min → amplitude/mean cyclic-stress converter, the Goodman and
  Smith-Watson-Topper equivalent reversed stresses, the fatigue notch factor
  (with the Neuber and Peterson notch sensitivities that feed it),
  the steel endurance-limit estimate with its Marin correction to the real
  part, the Basquin S-N finite-life law, and
  Palmgren-Miner cumulative damage over a load spectrum
- :mod:`~anvilate.analysis.gasket` — bolted-flange gasket bolt loads (ASME VIII
  Appendix 2): the gasket seating load (π·b·G·y), the operating load (hydrostatic
  end force plus the m-factor residual gasket reaction), and the governing (larger)
  bolt load a flange is sized for
- :mod:`~anvilate.analysis.sheetmetal` — sheet-metal bending flat-pattern geometry:
  the neutral-axis radius and bend allowance (K-factor), the outside setback and
  bend deduction, the developed blank length of a multi-bend strip, the minimum
  bend radius a material's ductility allows, the air (V-die) bending force, and the
  shear-cutting / round-hole punching force and the stripping force to clear the punch,
  and the deep-drawing cup blank diameter, draw ratio, and drawing force
- :mod:`~anvilate.analysis.snapfit` — constant-section cantilever snap-fit design by
  strain: the permissible deflection a material allowable permits, the peak root strain
  a required undercut imposes, the finger deflection (spring) force, and the mating
  (assembly) force over the lead-in ramp

Further analytical cases land here as they are built out (see
openspec/specs/validation-gauntlet/).
"""

from __future__ import annotations

from .axial import (
    axial_elongation,
    axial_stiffness,
    axial_stress,
    circular_area,
    required_axial_area,
)
from .beam import (
    SHEAR_FORM_CIRCULAR,
    SHEAR_FORM_RECTANGULAR,
    BeamBendingResult,
    cantilever_center_patch_load,
    cantilever_end_load,
    cantilever_end_load_tip_slope,
    cantilever_end_moment,
    cantilever_offset_load,
    cantilever_offset_moment,
    cantilever_partial_uniform_load,
    cantilever_triangular_load,
    cantilever_triangular_load_peak_at_tip,
    cantilever_uniform_load,
    cantilever_uniform_load_tip_slope,
    circular_plastic_section_modulus,
    circular_second_moment,
    deflection_scorecard,
    fastener_spacing_for_shear_flow,
    fixed_fixed_center_load,
    fixed_fixed_center_patch_load,
    fixed_fixed_offset_load,
    fixed_fixed_partial_uniform_load,
    fixed_fixed_plastic_collapse_load,
    fixed_fixed_plastic_collapse_udl,
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
    hollow_circular_plastic_section_modulus,
    hollow_circular_second_moment,
    i_section_plastic_section_modulus,
    i_section_second_moment,
    max_transverse_shear_stress,
    overhang_tip_load,
    overhang_uniform_load,
    plastic_moment,
    propped_cantilever_plastic_collapse_load,
    propped_cantilever_plastic_collapse_udl,
    rectangular_plastic_section_modulus,
    rectangular_second_moment,
    rectangular_tube_plastic_section_modulus,
    rectangular_tube_second_moment,
    shear_flow,
    simply_supported_center_load,
    simply_supported_center_load_support_slope,
    simply_supported_center_patch_load,
    simply_supported_end_moment,
    simply_supported_offset_load,
    simply_supported_offset_moment,
    simply_supported_partial_uniform_load,
    simply_supported_plastic_collapse_load,
    simply_supported_plastic_collapse_udl,
    simply_supported_symmetric_point_loads,
    simply_supported_triangular_load,
    simply_supported_uniform_load,
    simply_supported_uniform_load_support_slope,
    span_deflection_limit,
)
from .beam_foundation import (
    beam_on_elastic_foundation_max_deflection,
    beam_on_elastic_foundation_max_moment,
    foundation_characteristic_parameter,
)
from .bearing import (
    BALL_BEARING_LIFE_EXPONENT,
    ROLLER_BEARING_LIFE_EXPONENT,
    bearing_basic_rating_life,
    bearing_equivalent_dynamic_load,
    bearing_equivalent_static_load,
    bearing_life_hours,
    bearing_reliability_life_factor,
    bearing_static_safety_factor,
)
from .belt import (
    belt_centrifugal_tension,
    belt_length,
    belt_max_transmissible_force,
    belt_max_transmissible_force_at_speed,
    belt_mean_tension,
    belt_slack_tension,
    belt_speed_for_max_power,
    belt_transmitted_power,
    belt_wrap_angle,
    capstan_tension_ratio,
    crossed_belt_length,
    crossed_belt_wrap_angle,
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
from .cable import (
    catenary_arc_length,
    catenary_max_tension,
    catenary_sag,
    parabolic_cable_length,
    parabolic_cable_max_tension,
    parabolic_cable_sag,
)
from .cam import (
    CamMotion,
    cam_follower_motion,
    cam_pressure_angle,
)
from .chain import (
    chain_length_in_pitches,
    chain_speed,
    chain_working_tension,
    chordal_speed_variation,
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
    lateral_torsional_buckling_moment,
    perry_robertson_stress,
    radius_of_gyration,
    rankine_gordon_stress,
    secant_column_max_stress,
    slenderness_ratio,
    transition_slenderness,
)
from .contact import (
    HertzContact,
    HertzLineContact,
    hertz_cylinder_contact,
    hertz_effective_modulus,
    hertz_sphere_approach,
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
    thin_ring_buckling_pressure,
    thin_ring_diametral_deflection,
    thin_ring_max_moment,
    trapezoidal_curved_beam_stress,
)
from .dynamics import (
    STANDARD_GRAVITY,
    annular_disc_polar_mass_moment,
    base_excitation_relative_transmissibility,
    cantilever_fundamental_frequency,
    cantilever_tip_mass_frequency,
    clamped_annular_plate_fundamental_frequency,
    clamped_circular_plate_fundamental_frequency,
    clamped_plate_fundamental_frequency,
    critical_damping_coefficient,
    damped_natural_frequency,
    dunkerley_fundamental_frequency,
    dynamic_magnification_factor,
    fixed_fixed_center_mass_frequency,
    fixed_fixed_fundamental_frequency,
    fixed_pinned_fundamental_frequency,
    frequency_scorecard,
    isolator_natural_frequency_for_transmissibility,
    isolator_static_deflection_for_transmissibility,
    logarithmic_decrement,
    natural_frequency,
    natural_frequency_from_deflection,
    physical_pendulum_period,
    quality_factor,
    resonance_phase_angle,
    simple_pendulum_period,
    simply_supported_annular_plate_fundamental_frequency,
    simply_supported_center_mass_frequency,
    simply_supported_circular_plate_fundamental_frequency,
    simply_supported_fundamental_frequency,
    simply_supported_plate_fundamental_frequency,
    solid_disc_polar_mass_moment,
    spring_surge_frequency,
    string_natural_frequency,
    torsional_natural_frequency,
    transmissibility,
    tuned_mass_damper_optimal_damping,
    tuned_mass_damper_optimal_frequency_ratio,
    two_rotor_torsional_natural_frequency,
)
from .fastener import (
    NUT_FACTOR_AS_RECEIVED,
    bearing_stress,
    bolt_axial_stiffness,
    bolt_axial_stress,
    bolt_diameter_for_shear,
    bolt_load_in_joint,
    bolt_preload_from_torque,
    bolt_proof_load,
    bolt_shear_stress,
    bolt_tensile_stress_area,
    eccentric_shear_group_peak_force,
    joint_separation_load,
    joint_stiffness_factor,
    member_clamp_load_in_joint,
    member_stiffness_frustum,
    preloaded_bolt_cyclic_stress,
    recommended_bolt_preload,
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
    goodman_equivalent_reversed_stress,
    goodman_safety_factor,
    goodman_scorecard,
    marin_endurance_limit,
    miner_cumulative_damage,
    miner_spectrum_repeats_to_failure,
    morrow_equivalent_reversed_stress,
    neuber_notch_sensitivity,
    peterson_notch_sensitivity,
    smith_watson_topper_stress,
    soderberg_safety_factor,
    soderberg_scorecard,
)
from .flywheel import (
    coefficient_of_fluctuation,
    flywheel_energy_fluctuation,
    flywheel_inertia_for_fluctuation,
    rotating_annular_disc_bore_stress,
    rotating_annular_disc_radial_stress,
    rotating_annular_disc_tangential_stress,
    rotating_rim_burst_speed,
    rotating_rim_hoop_stress,
    rotating_rim_radial_growth,
    rotating_solid_disc_max_stress,
    rotating_solid_disc_radial_stress,
    rotating_solid_disc_tangential_stress,
)
from .fourbar import (
    fourbar_transmission_angle,
    fourbar_type,
    is_grashof,
)
from .fracture import (
    critical_crack_length,
    paris_law_crack_growth_rate,
    paris_law_cycles_to_failure,
    stress_intensity_factor,
)
from .gasket import (
    gasket_operating_load,
    gasket_seating_load,
    governing_gasket_bolt_load,
)
from .gear import (
    PlanetaryTorques,
    barth_velocity_factor,
    base_tangent_length,
    bevel_gear_axial_load,
    bevel_gear_radial_load,
    bevel_pitch_cone_angle,
    gear_contact_stress,
    gear_normal_load,
    gear_radial_load,
    gear_tangential_load,
    gear_tooth_thickness_at_radius,
    gear_train_efficiency,
    gear_train_value,
    helical_gear_axial_thrust,
    helical_gear_radial_load,
    helical_virtual_teeth,
    involute_angle,
    involute_function,
    lewis_bending_stress,
    lewis_module_for_bending_stress,
    minimum_teeth_to_avoid_undercut,
    operating_pressure_angle,
    pitch_line_velocity,
    planetary_can_assemble,
    planetary_planet_teeth,
    planetary_speed,
    planetary_torques,
    profile_shift_sum_for_center_distance,
    reverted_train_is_coaxial,
    spur_gear_contact_ratio,
)
from .geneva import (
    geneva_advance_fraction,
    geneva_crank_radius,
    geneva_driven_radius,
    geneva_dwell_fraction,
    geneva_index_angle,
)
from .impact import (
    SUDDENLY_APPLIED_FACTOR,
    horizontal_impact_force,
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
    journal_bearing_minimum_film_thickness,
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
from .living_hinge import (
    living_hinge_fold_strain,
    living_hinge_web_length_for_strain,
)
from .o_ring import (
    o_ring_gland_fill_fraction,
    o_ring_squeeze_fraction,
    o_ring_stretch_fraction,
)
from .plate import (
    PlateBendingResult,
    clamped_annular_plate_uniform_load,
    clamped_circular_plate_center_load_deflection,
    clamped_circular_plate_thickness_for_pressure,
    clamped_circular_plate_uniform_load,
    clamped_plate_uniform_load,
    plate_buckling_stress,
    plate_compression_buckling_coefficient,
    plate_shear_buckling_coefficient,
    simply_supported_annular_plate_uniform_load,
    simply_supported_circular_plate_center_load_deflection,
    simply_supported_circular_plate_uniform_load,
    simply_supported_plate_center_patch_load,
    simply_supported_plate_uniform_load,
)
from .power_screw import (
    lead_angle,
    power_screw_collar_torque,
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
    cylinder_axial_buckling_stress,
    cylinder_external_pressure_buckling,
    sphere_external_pressure_buckling,
    thick_wall_cylinder,
    thick_wall_sphere,
    thin_wall_cylinder,
    thin_wall_cylinder_diametral_growth,
    thin_wall_sphere_diametral_growth,
    thin_wall_sphere_stress,
    thin_wall_thickness_for_pressure,
)
from .rigging import (
    sling_horizontal_force,
    sling_leg_tension,
    sling_tension_factor,
)
from .rivet import (
    RivetedJointStrength,
    riveted_joint_efficiency,
)
from .scotch_yoke import (
    scotch_yoke_acceleration,
    scotch_yoke_displacement,
    scotch_yoke_velocity,
)
from .section import CrossSection, bending_stress, required_section_modulus
from .sheetmetal import (
    air_bending_force,
    bend_allowance,
    bend_deduction,
    cup_blank_diameter,
    deep_draw_force,
    draw_ratio,
    flat_pattern_length,
    minimum_bend_radius,
    neutral_axis_radius,
    outside_setback,
    round_hole_punching_force,
    shear_cutting_force,
    stripping_force,
)
from .slider_crank import (
    slider_crank_acceleration,
    slider_crank_displacement,
    slider_crank_piston_side_thrust,
    slider_crank_velocity,
)
from .snapfit import (
    snap_fit_deflection_force,
    snap_fit_mating_force,
    snap_fit_permissible_deflection,
    snap_fit_strain,
)
from .spring import (
    BELLEVILLE_PLATEAU_RATIO,
    SPRING_END_CLAMPED_FREE,
    SPRING_END_FIXED_HINGED,
    SPRING_END_HINGED_HINGED,
    SPRING_END_PARALLEL_PLATES,
    SpringBucklingResult,
    belleville_flat_load,
    belleville_washer_force,
    helical_spring_active_coils_for_rate,
    helical_spring_buckling,
    helical_spring_rate,
    helical_spring_solid_length,
    helical_torsion_spring_rate,
    helical_torsion_spring_stress,
    leaf_spring_rate,
    leaf_spring_stress,
    spiral_spring_rate,
    spiral_spring_stress,
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
    elliptical_hole_stress_concentration,
    max_shear_stress_plane,
    octahedral_shear_stress,
    principal_angle_plane,
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
    bimetallic_strip_curvature,
    bimetallic_strip_tip_deflection,
    constrained_thermal_stress,
    differential_thermal_stress,
    free_thermal_expansion,
    shrink_fit_assembly_temperature,
    thermal_buckling_temperature_rise,
    thermal_shock_stress,
    through_wall_gradient_thermal_stress,
    triaxial_constrained_thermal_stress,
)
from .torsion import (
    elliptical_bar_torsional_stress,
    elliptical_bar_twist_angle,
    hollow_shaft_diameter_for_bending_torsion,
    hollow_shaft_torsional_stress,
    hollow_shaft_twist_angle,
    polar_second_moment_hollow,
    polar_second_moment_solid,
    rectangular_bar_torsion_constant,
    rectangular_bar_twist_angle,
    rectangular_tube_enclosed_area,
    rectangular_tube_torsional_stress,
    rectangular_tube_twist_angle,
    shaft_diameter_for_bending_torsion,
    shaft_diameter_for_torque,
    shaft_torsional_stiffness,
    shaft_torsional_stress,
    shaft_twist_angle,
    shaft_von_mises_stress,
    thin_closed_tube_torsional_stress,
    thin_open_strip_torsion_constant,
    thin_open_strip_torsional_stress,
    thin_open_strip_twist_angle,
    torque_from_power,
    triangular_bar_torsional_stress,
    triangular_bar_twist_angle,
)
from .weld import (
    FILLET_THROAT_FACTOR,
    eccentric_weld_group_peak_stress,
    fillet_weld_leg_for_load,
    fillet_weld_throat_stress,
)
from .worm import (
    worm_gear_efficiency,
    worm_gear_ratio,
    worm_is_self_locking,
    worm_lead_angle,
    worm_separating_force,
    worm_tangential_force,
)

__all__ = [
    "axial_stress",
    "axial_elongation",
    "axial_stiffness",
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
    "rectangular_tube_second_moment",
    "i_section_second_moment",
    "rectangular_plastic_section_modulus",
    "circular_plastic_section_modulus",
    "hollow_circular_plastic_section_modulus",
    "rectangular_tube_plastic_section_modulus",
    "i_section_plastic_section_modulus",
    "plastic_moment",
    "simply_supported_plastic_collapse_load",
    "fixed_fixed_plastic_collapse_load",
    "simply_supported_center_load_support_slope",
    "simply_supported_uniform_load_support_slope",
    "cantilever_end_load_tip_slope",
    "cantilever_uniform_load_tip_slope",
    "simply_supported_plastic_collapse_udl",
    "fixed_fixed_plastic_collapse_udl",
    "propped_cantilever_plastic_collapse_load",
    "propped_cantilever_plastic_collapse_udl",
    "CrossSection",
    "bending_stress",
    "required_section_modulus",
    "neutral_axis_radius",
    "bend_allowance",
    "outside_setback",
    "bend_deduction",
    "flat_pattern_length",
    "minimum_bend_radius",
    "air_bending_force",
    "shear_cutting_force",
    "round_hole_punching_force",
    "stripping_force",
    "cup_blank_diameter",
    "draw_ratio",
    "deep_draw_force",
    "RivetedJointStrength",
    "riveted_joint_efficiency",
    "sling_tension_factor",
    "sling_leg_tension",
    "sling_horizontal_force",
    "max_transverse_shear_stress",
    "shear_flow",
    "fastener_spacing_for_shear_flow",
    "deflection_scorecard",
    "span_deflection_limit",
    "SHEAR_FORM_RECTANGULAR",
    "SHEAR_FORM_CIRCULAR",
    "foundation_characteristic_parameter",
    "beam_on_elastic_foundation_max_deflection",
    "beam_on_elastic_foundation_max_moment",
    "BALL_BEARING_LIFE_EXPONENT",
    "ROLLER_BEARING_LIFE_EXPONENT",
    "bearing_basic_rating_life",
    "bearing_life_hours",
    "bearing_static_safety_factor",
    "bearing_equivalent_dynamic_load",
    "bearing_equivalent_static_load",
    "bearing_reliability_life_factor",
    "capstan_tension_ratio",
    "belt_slack_tension",
    "belt_max_transmissible_force",
    "belt_centrifugal_tension",
    "belt_max_transmissible_force_at_speed",
    "belt_speed_for_max_power",
    "vee_belt_effective_friction",
    "belt_length",
    "belt_wrap_angle",
    "crossed_belt_length",
    "crossed_belt_wrap_angle",
    "belt_transmitted_power",
    "belt_mean_tension",
    "chain_length_in_pitches",
    "chordal_speed_variation",
    "chain_speed",
    "chain_working_tension",
    "CamMotion",
    "cam_follower_motion",
    "cam_pressure_angle",
    "parabolic_cable_sag",
    "parabolic_cable_max_tension",
    "parabolic_cable_length",
    "catenary_sag",
    "catenary_arc_length",
    "catenary_max_tension",
    "geneva_index_angle",
    "geneva_crank_radius",
    "geneva_driven_radius",
    "geneva_advance_fraction",
    "geneva_dwell_fraction",
    "slider_crank_displacement",
    "slider_crank_velocity",
    "slider_crank_acceleration",
    "slider_crank_piston_side_thrust",
    "snap_fit_permissible_deflection",
    "snap_fit_strain",
    "snap_fit_deflection_force",
    "snap_fit_mating_force",
    "scotch_yoke_displacement",
    "scotch_yoke_velocity",
    "scotch_yoke_acceleration",
    "is_grashof",
    "fourbar_type",
    "fourbar_transmission_angle",
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
    "thin_ring_diametral_deflection",
    "thin_ring_max_moment",
    "thin_ring_buckling_pressure",
    "ColumnEnd",
    "euler_buckling_load",
    "euler_second_moment_for_load",
    "radius_of_gyration",
    "slenderness_ratio",
    "euler_critical_stress",
    "transition_slenderness",
    "johnson_critical_stress",
    "secant_column_max_stress",
    "perry_robertson_stress",
    "lateral_torsional_buckling_moment",
    "rankine_gordon_stress",
    "UNIFORM_WEAR",
    "UNIFORM_PRESSURE",
    "disc_clutch_torque",
    "disc_clutch_force_for_torque",
    "cone_clutch_torque",
    "STANDARD_GRAVITY",
    "natural_frequency",
    "natural_frequency_from_deflection",
    "cantilever_tip_mass_frequency",
    "simply_supported_center_mass_frequency",
    "fixed_fixed_center_mass_frequency",
    "string_natural_frequency",
    "damped_natural_frequency",
    "logarithmic_decrement",
    "quality_factor",
    "critical_damping_coefficient",
    "transmissibility",
    "isolator_natural_frequency_for_transmissibility",
    "isolator_static_deflection_for_transmissibility",
    "dynamic_magnification_factor",
    "resonance_phase_angle",
    "base_excitation_relative_transmissibility",
    "simple_pendulum_period",
    "physical_pendulum_period",
    "tuned_mass_damper_optimal_frequency_ratio",
    "tuned_mass_damper_optimal_damping",
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
    "two_rotor_torsional_natural_frequency",
    "solid_disc_polar_mass_moment",
    "annular_disc_polar_mass_moment",
    "frequency_scorecard",
    "NUT_FACTOR_AS_RECEIVED",
    "bolt_preload_from_torque",
    "torque_for_preload",
    "bearing_stress",
    "bolt_shear_stress",
    "bolt_diameter_for_shear",
    "bolt_tensile_stress_area",
    "bolt_axial_stress",
    "bolt_proof_load",
    "recommended_bolt_preload",
    "thread_stripping_shear_area",
    "thread_stripping_stress",
    "thread_engagement_for_load",
    "bolt_axial_stiffness",
    "member_stiffness_frustum",
    "joint_stiffness_factor",
    "bolt_load_in_joint",
    "member_clamp_load_in_joint",
    "joint_separation_load",
    "preloaded_bolt_cyclic_stress",
    "eccentric_shear_group_peak_force",
    "goodman_safety_factor",
    "goodman_scorecard",
    "smith_watson_topper_stress",
    "goodman_equivalent_reversed_stress",
    "morrow_equivalent_reversed_stress",
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
    "neuber_notch_sensitivity",
    "peterson_notch_sensitivity",
    "coefficient_of_fluctuation",
    "flywheel_energy_fluctuation",
    "flywheel_inertia_for_fluctuation",
    "rotating_rim_hoop_stress",
    "rotating_rim_burst_speed",
    "rotating_rim_radial_growth",
    "rotating_solid_disc_max_stress",
    "rotating_solid_disc_radial_stress",
    "rotating_solid_disc_tangential_stress",
    "rotating_annular_disc_bore_stress",
    "rotating_annular_disc_radial_stress",
    "rotating_annular_disc_tangential_stress",
    "SUDDENLY_APPLIED_FACTOR",
    "impact_factor",
    "impact_stress",
    "horizontal_impact_force",
    "gear_tangential_load",
    "gear_radial_load",
    "gear_normal_load",
    "bevel_pitch_cone_angle",
    "bevel_gear_radial_load",
    "bevel_gear_axial_load",
    "helical_gear_axial_thrust",
    "helical_gear_radial_load",
    "helical_virtual_teeth",
    "pitch_line_velocity",
    "barth_velocity_factor",
    "lewis_bending_stress",
    "lewis_module_for_bending_stress",
    "gear_contact_stress",
    "spur_gear_contact_ratio",
    "minimum_teeth_to_avoid_undercut",
    "involute_function",
    "involute_angle",
    "base_tangent_length",
    "gear_tooth_thickness_at_radius",
    "operating_pressure_angle",
    "profile_shift_sum_for_center_distance",
    "gear_train_value",
    "gear_train_efficiency",
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
    "living_hinge_fold_strain",
    "living_hinge_web_length_for_strain",
    "o_ring_squeeze_fraction",
    "o_ring_gland_fill_fraction",
    "o_ring_stretch_fraction",
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
    "rectangular_bar_torsion_constant",
    "rectangular_bar_twist_angle",
    "elliptical_bar_torsional_stress",
    "elliptical_bar_twist_angle",
    "triangular_bar_torsional_stress",
    "triangular_bar_twist_angle",
    "thin_closed_tube_torsional_stress",
    "PlateBendingResult",
    "simply_supported_plate_uniform_load",
    "simply_supported_plate_center_patch_load",
    "clamped_plate_uniform_load",
    "simply_supported_circular_plate_uniform_load",
    "clamped_circular_plate_uniform_load",
    "simply_supported_circular_plate_center_load_deflection",
    "clamped_circular_plate_center_load_deflection",
    "simply_supported_annular_plate_uniform_load",
    "clamped_annular_plate_uniform_load",
    "clamped_circular_plate_thickness_for_pressure",
    "plate_buckling_stress",
    "plate_shear_buckling_coefficient",
    "plate_compression_buckling_coefficient",
    "lead_angle",
    "power_screw_raise_torque",
    "power_screw_lower_torque",
    "power_screw_efficiency",
    "power_screw_is_self_locking",
    "power_screw_collar_torque",
    "worm_gear_ratio",
    "worm_lead_angle",
    "worm_gear_efficiency",
    "worm_is_self_locking",
    "worm_tangential_force",
    "worm_separating_force",
    "ThinWallStress",
    "ThickWallStress",
    "ThickWallSphereStress",
    "thin_wall_cylinder",
    "thin_wall_cylinder_diametral_growth",
    "thin_wall_thickness_for_pressure",
    "asme_cylinder_thickness",
    "thick_wall_cylinder",
    "thin_wall_sphere_stress",
    "thin_wall_sphere_diametral_growth",
    "thick_wall_sphere",
    "cylinder_external_pressure_buckling",
    "sphere_external_pressure_buckling",
    "cylinder_axial_buckling_stress",
    "InterferenceFit",
    "interference_fit",
    "interference_for_contact_pressure",
    "interference_axial_capacity",
    "interference_torque_capacity",
    "petroff_friction_torque",
    "petroff_friction_power",
    "journal_bearing_unit_load",
    "sommerfeld_number",
    "journal_bearing_minimum_film_thickness",
    "hertz_effective_modulus",
    "HertzContact",
    "hertz_sphere_contact",
    "hertz_sphere_approach",
    "HertzLineContact",
    "hertz_cylinder_contact",
    "flange_coupling_torque",
    "flange_coupling_bolt_force",
    "spring_index",
    "wahl_factor",
    "spring_shear_stress",
    "helical_spring_rate",
    "helical_spring_active_coils_for_rate",
    "helical_spring_solid_length",
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
    "spiral_spring_rate",
    "spiral_spring_stress",
    "helical_torsion_spring_rate",
    "helical_torsion_spring_stress",
    "leaf_spring_stress",
    "leaf_spring_rate",
    "spring_surge_frequency",
    "von_mises_plane_stress",
    "von_mises_bending_torsion",
    "von_mises_principal",
    "octahedral_shear_stress",
    "principal_stresses_plane",
    "principal_angle_plane",
    "max_shear_stress_plane",
    "tresca_equivalent_stress",
    "tresca_principal",
    "yield_safety_factor",
    "strength_scorecard",
    "CombinedNormalStress",
    "combine_axial_bending",
    "concentrated_stress",
    "elliptical_hole_stress_concentration",
    "stress_intensity_factor",
    "critical_crack_length",
    "paris_law_crack_growth_rate",
    "paris_law_cycles_to_failure",
    "gasket_seating_load",
    "gasket_operating_load",
    "governing_gasket_bolt_load",
    "constrained_thermal_stress",
    "thermal_shock_stress",
    "triaxial_constrained_thermal_stress",
    "through_wall_gradient_thermal_stress",
    "thermal_buckling_temperature_rise",
    "free_thermal_expansion",
    "shrink_fit_assembly_temperature",
    "DifferentialThermalStress",
    "differential_thermal_stress",
    "bimetallic_strip_curvature",
    "bimetallic_strip_tip_deflection",
    "FILLET_THROAT_FACTOR",
    "fillet_weld_throat_stress",
    "fillet_weld_leg_for_load",
    "eccentric_weld_group_peak_stress",
]
