"""Anvilate T1 analytical checks: closed-form, deterministic, no solver.

The T1 validation tier screens a design with handbook closed-form solutions
(Roark, Shigley) before any FEA — fast, deterministic, and unit-checked. The
modules:

- :mod:`~anvilate.analysis.axial` — direct axial stress and section area
- :mod:`~anvilate.analysis.beam` — bending (cantilever / simply-supported /
  fixed-fixed / fixed-pinned; point, distributed, triangular, patch, and
  applied-couple loads), transverse shear, section second moments
- :mod:`~anvilate.analysis.plate` — flat-plate bending (simply-supported
  rectangle via the exact Navier series; circular, simply-supported and clamped)
- :mod:`~anvilate.analysis.section` — ``CrossSection`` bundling area, second
  moment, extreme fibre, section modulus, and radius of gyration
- :mod:`~anvilate.analysis.column` — Euler and Johnson buckling, slenderness
- :mod:`~anvilate.analysis.torsion` — solid and hollow shaft torsion, twist,
  and torsional stiffness; thin-walled rectangular (box) tube torsion (Bredt)
- :mod:`~anvilate.analysis.pressure_vessel` — thin-wall cylinder and sphere,
  exact Lamé thick-wall cylinder and sphere
- :mod:`~anvilate.analysis.interference` — thick-wall press/shrink-fit (Lamé)
- :mod:`~anvilate.analysis.contact` — Hertzian point (sphere) and line (cylinder) contact
- :mod:`~anvilate.analysis.fastener` — bolt torque-tension, bearing, and shear
- :mod:`~anvilate.analysis.keys` — shaft-key shear and bearing stress
- :mod:`~anvilate.analysis.spring` — helical-spring shear (Wahl), rate, and
  lateral (column) buckling screen
- :mod:`~anvilate.analysis.thermal` — thermal growth, constrained thermal
  stress, and shrink-fit assembly temperature
- :mod:`~anvilate.analysis.dynamics` — modal screens: SDOF and Rayleigh
  estimates, distributed-mass beam fundamentals, disc-on-shaft torsional mode
- :mod:`~anvilate.analysis.stress` — von Mises combination, combined axial+bending
- :mod:`~anvilate.analysis.fatigue` — Goodman, Soderberg, and Gerber fatigue

Further analytical cases land here as they are built out (see
openspec/specs/validation-gauntlet/).
"""

from __future__ import annotations

from .axial import axial_stress, circular_area
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
    simply_supported_center_load,
    simply_supported_center_patch_load,
    simply_supported_end_moment,
    simply_supported_offset_load,
    simply_supported_offset_moment,
    simply_supported_partial_uniform_load,
    simply_supported_symmetric_point_loads,
    simply_supported_triangular_load,
    simply_supported_uniform_load,
)
from .column import (
    ColumnEnd,
    euler_buckling_load,
    euler_critical_stress,
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
    hertz_sphere_contact,
)
from .dynamics import (
    STANDARD_GRAVITY,
    cantilever_fundamental_frequency,
    clamped_annular_plate_fundamental_frequency,
    clamped_circular_plate_fundamental_frequency,
    clamped_plate_fundamental_frequency,
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
    bolt_preload_from_torque,
    bolt_shear_stress,
    torque_for_preload,
)
from .fatigue import (
    gerber_safety_factor,
    gerber_scorecard,
    goodman_safety_factor,
    goodman_scorecard,
    soderberg_safety_factor,
    soderberg_scorecard,
)
from .interference import (
    InterferenceFit,
    interference_axial_capacity,
    interference_fit,
    interference_torque_capacity,
)
from .keys import key_bearing_stress, key_shear_stress, key_tangential_force
from .plate import (
    PlateBendingResult,
    clamped_annular_plate_uniform_load,
    clamped_circular_plate_uniform_load,
    clamped_plate_uniform_load,
    simply_supported_annular_plate_uniform_load,
    simply_supported_circular_plate_uniform_load,
    simply_supported_plate_center_patch_load,
    simply_supported_plate_uniform_load,
)
from .pressure_vessel import (
    ThickWallSphereStress,
    ThickWallStress,
    ThinWallStress,
    thick_wall_cylinder,
    thick_wall_sphere,
    thin_wall_cylinder,
    thin_wall_sphere_stress,
)
from .section import CrossSection
from .spring import (
    SPRING_END_CLAMPED_FREE,
    SPRING_END_FIXED_HINGED,
    SPRING_END_HINGED_HINGED,
    SPRING_END_PARALLEL_PLATES,
    SpringBucklingResult,
    helical_spring_buckling,
    helical_spring_rate,
    spring_index,
    spring_shear_stress,
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
    von_mises_bending_torsion,
    von_mises_plane_stress,
    yield_safety_factor,
)
from .thermal import (
    constrained_thermal_stress,
    free_thermal_expansion,
    shrink_fit_assembly_temperature,
)
from .torsion import (
    hollow_shaft_torsional_stress,
    hollow_shaft_twist_angle,
    polar_second_moment_hollow,
    polar_second_moment_solid,
    rectangular_tube_enclosed_area,
    rectangular_tube_torsional_stress,
    rectangular_tube_twist_angle,
    shaft_torsional_stiffness,
    shaft_torsional_stress,
    shaft_twist_angle,
)

__all__ = [
    "axial_stress",
    "circular_area",
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
    "max_transverse_shear_stress",
    "deflection_scorecard",
    "SHEAR_FORM_RECTANGULAR",
    "SHEAR_FORM_CIRCULAR",
    "ColumnEnd",
    "euler_buckling_load",
    "radius_of_gyration",
    "slenderness_ratio",
    "euler_critical_stress",
    "transition_slenderness",
    "johnson_critical_stress",
    "secant_column_max_stress",
    "STANDARD_GRAVITY",
    "natural_frequency",
    "natural_frequency_from_deflection",
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
    "goodman_safety_factor",
    "goodman_scorecard",
    "soderberg_safety_factor",
    "soderberg_scorecard",
    "gerber_safety_factor",
    "gerber_scorecard",
    "key_tangential_force",
    "key_shear_stress",
    "key_bearing_stress",
    "polar_second_moment_solid",
    "polar_second_moment_hollow",
    "shaft_torsional_stress",
    "hollow_shaft_torsional_stress",
    "shaft_twist_angle",
    "hollow_shaft_twist_angle",
    "shaft_torsional_stiffness",
    "rectangular_tube_enclosed_area",
    "rectangular_tube_torsional_stress",
    "rectangular_tube_twist_angle",
    "PlateBendingResult",
    "simply_supported_plate_uniform_load",
    "simply_supported_plate_center_patch_load",
    "clamped_plate_uniform_load",
    "simply_supported_circular_plate_uniform_load",
    "clamped_circular_plate_uniform_load",
    "simply_supported_annular_plate_uniform_load",
    "clamped_annular_plate_uniform_load",
    "ThinWallStress",
    "ThickWallStress",
    "ThickWallSphereStress",
    "thin_wall_cylinder",
    "thick_wall_cylinder",
    "thin_wall_sphere_stress",
    "thick_wall_sphere",
    "InterferenceFit",
    "interference_fit",
    "interference_axial_capacity",
    "interference_torque_capacity",
    "HertzContact",
    "hertz_sphere_contact",
    "HertzLineContact",
    "hertz_cylinder_contact",
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
    "spring_surge_frequency",
    "von_mises_plane_stress",
    "von_mises_bending_torsion",
    "principal_stresses_plane",
    "max_shear_stress_plane",
    "tresca_equivalent_stress",
    "yield_safety_factor",
    "strength_scorecard",
    "CombinedNormalStress",
    "combine_axial_bending",
    "concentrated_stress",
    "constrained_thermal_stress",
    "free_thermal_expansion",
    "shrink_fit_assembly_temperature",
]
