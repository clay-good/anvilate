"""Anvilate T1 analytical checks: closed-form, deterministic, no solver.

The T1 validation tier screens a design with handbook closed-form solutions
(Roark, Shigley) before any FEA — fast, deterministic, and unit-checked. The
modules:

- :mod:`~anvilate.analysis.axial` — direct axial stress and section area
- :mod:`~anvilate.analysis.beam` — bending (cantilever / simply-supported /
  fixed-fixed, point and distributed), transverse shear, section second moments
- :mod:`~anvilate.analysis.section` — ``CrossSection`` bundling area, second
  moment, extreme fibre, section modulus, and radius of gyration
- :mod:`~anvilate.analysis.column` — Euler and Johnson buckling, slenderness
- :mod:`~anvilate.analysis.torsion` — solid and hollow shaft torsion and twist
- :mod:`~anvilate.analysis.pressure_vessel` — thin-wall cylinder and sphere
- :mod:`~anvilate.analysis.interference` — thick-wall press/shrink-fit (Lamé)
- :mod:`~anvilate.analysis.contact` — Hertzian point (sphere) and line (cylinder) contact
- :mod:`~anvilate.analysis.fastener` — bolt torque-tension, bearing, and shear
- :mod:`~anvilate.analysis.keys` — shaft-key shear and bearing stress
- :mod:`~anvilate.analysis.spring` — helical-spring shear (Wahl)
- :mod:`~anvilate.analysis.thermal` — constrained thermal stress
- :mod:`~anvilate.analysis.dynamics` — fundamental-frequency (modal) screen
- :mod:`~anvilate.analysis.stress` — von Mises combination, combined axial+bending
- :mod:`~anvilate.analysis.fatigue` — modified-Goodman fatigue

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
    cantilever_offset_load,
    cantilever_partial_uniform_load,
    cantilever_triangular_load,
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
    fixed_pinned_offset_load,
    fixed_pinned_partial_uniform_load,
    fixed_pinned_triangular_load,
    fixed_pinned_triangular_load_peak_at_prop,
    fixed_pinned_uniform_load,
    hollow_circular_second_moment,
    max_transverse_shear_stress,
    rectangular_second_moment,
    simply_supported_center_load,
    simply_supported_center_patch_load,
    simply_supported_offset_load,
    simply_supported_partial_uniform_load,
    simply_supported_triangular_load,
    simply_supported_uniform_load,
)
from .column import (
    ColumnEnd,
    euler_buckling_load,
    euler_critical_stress,
    johnson_critical_stress,
    radius_of_gyration,
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
    frequency_scorecard,
    natural_frequency,
    natural_frequency_from_deflection,
)
from .fastener import (
    NUT_FACTOR_AS_RECEIVED,
    bearing_stress,
    bolt_preload_from_torque,
    bolt_shear_stress,
    torque_for_preload,
)
from .fatigue import goodman_safety_factor, goodman_scorecard
from .interference import (
    InterferenceFit,
    interference_axial_capacity,
    interference_fit,
    interference_torque_capacity,
)
from .keys import key_bearing_stress, key_shear_stress, key_tangential_force
from .pressure_vessel import (
    ThinWallStress,
    thin_wall_cylinder,
    thin_wall_sphere_stress,
)
from .section import CrossSection
from .spring import spring_index, spring_shear_stress, wahl_factor
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
from .thermal import constrained_thermal_stress
from .torsion import (
    hollow_shaft_torsional_stress,
    hollow_shaft_twist_angle,
    polar_second_moment_hollow,
    polar_second_moment_solid,
    shaft_torsional_stress,
    shaft_twist_angle,
)

__all__ = [
    "axial_stress",
    "circular_area",
    "BeamBendingResult",
    "cantilever_center_patch_load",
    "cantilever_end_load",
    "cantilever_offset_load",
    "cantilever_partial_uniform_load",
    "cantilever_triangular_load",
    "cantilever_uniform_load",
    "simply_supported_center_load",
    "simply_supported_center_patch_load",
    "simply_supported_offset_load",
    "simply_supported_partial_uniform_load",
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
    "fixed_pinned_offset_load",
    "fixed_pinned_partial_uniform_load",
    "fixed_pinned_triangular_load",
    "fixed_pinned_triangular_load_peak_at_prop",
    "fixed_pinned_uniform_load",
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
    "STANDARD_GRAVITY",
    "natural_frequency",
    "natural_frequency_from_deflection",
    "frequency_scorecard",
    "NUT_FACTOR_AS_RECEIVED",
    "bolt_preload_from_torque",
    "torque_for_preload",
    "bearing_stress",
    "bolt_shear_stress",
    "goodman_safety_factor",
    "goodman_scorecard",
    "key_tangential_force",
    "key_shear_stress",
    "key_bearing_stress",
    "polar_second_moment_solid",
    "polar_second_moment_hollow",
    "shaft_torsional_stress",
    "hollow_shaft_torsional_stress",
    "shaft_twist_angle",
    "hollow_shaft_twist_angle",
    "ThinWallStress",
    "thin_wall_cylinder",
    "thin_wall_sphere_stress",
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
]
