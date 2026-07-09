"""Anvilate T1 analytical checks: closed-form, deterministic, no solver.

The T1 validation tier screens a design with handbook closed-form solutions
(Roark, Shigley) before any FEA — fast, deterministic, and unit-checked. This
package holds those checks; :mod:`anvilate.analysis.axial` covers direct axial
stress, :mod:`anvilate.analysis.beam` covers the cantilever
and simply-supported bending cases, :mod:`anvilate.analysis.column` the Euler
buckling load, :mod:`anvilate.analysis.fastener` the bolt torque-tension
relation, :mod:`anvilate.analysis.torsion` the solid-shaft torsion check, and
:mod:`anvilate.analysis.pressure_vessel` the thin-wall cylinder stresses, and
:mod:`anvilate.analysis.stress` the von Mises combination of component stresses,
and :mod:`anvilate.analysis.fatigue` the modified-Goodman fatigue screen, and
:mod:`anvilate.analysis.spring` the helical-spring shear stress. Further
analytical cases land here as they are built out (see
openspec/specs/validation-gauntlet/).
"""

from __future__ import annotations

from .axial import axial_stress, circular_area
from .beam import (
    SHEAR_FORM_CIRCULAR,
    SHEAR_FORM_RECTANGULAR,
    BeamBendingResult,
    cantilever_end_load,
    cantilever_uniform_load,
    circular_second_moment,
    deflection_scorecard,
    hollow_circular_second_moment,
    max_transverse_shear_stress,
    rectangular_second_moment,
    simply_supported_center_load,
    simply_supported_uniform_load,
)
from .column import (
    ColumnEnd,
    euler_buckling_load,
    euler_critical_stress,
    radius_of_gyration,
    slenderness_ratio,
)
from .fastener import (
    NUT_FACTOR_AS_RECEIVED,
    bearing_stress,
    bolt_preload_from_torque,
    bolt_shear_stress,
    torque_for_preload,
)
from .fatigue import goodman_safety_factor, goodman_scorecard
from .pressure_vessel import (
    ThinWallStress,
    thin_wall_cylinder,
    thin_wall_sphere_stress,
)
from .spring import spring_index, spring_shear_stress, wahl_factor
from .stress import (
    CombinedNormalStress,
    combine_axial_bending,
    strength_scorecard,
    von_mises_bending_torsion,
    von_mises_plane_stress,
    yield_safety_factor,
)
from .torsion import (
    hollow_shaft_torsional_stress,
    polar_second_moment_hollow,
    polar_second_moment_solid,
    shaft_torsional_stress,
    shaft_twist_angle,
)

__all__ = [
    "axial_stress",
    "circular_area",
    "BeamBendingResult",
    "cantilever_end_load",
    "cantilever_uniform_load",
    "simply_supported_center_load",
    "simply_supported_uniform_load",
    "rectangular_second_moment",
    "circular_second_moment",
    "hollow_circular_second_moment",
    "max_transverse_shear_stress",
    "deflection_scorecard",
    "SHEAR_FORM_RECTANGULAR",
    "SHEAR_FORM_CIRCULAR",
    "ColumnEnd",
    "euler_buckling_load",
    "radius_of_gyration",
    "slenderness_ratio",
    "euler_critical_stress",
    "NUT_FACTOR_AS_RECEIVED",
    "bolt_preload_from_torque",
    "torque_for_preload",
    "bearing_stress",
    "bolt_shear_stress",
    "goodman_safety_factor",
    "goodman_scorecard",
    "polar_second_moment_solid",
    "polar_second_moment_hollow",
    "shaft_torsional_stress",
    "hollow_shaft_torsional_stress",
    "shaft_twist_angle",
    "ThinWallStress",
    "thin_wall_cylinder",
    "thin_wall_sphere_stress",
    "spring_index",
    "wahl_factor",
    "spring_shear_stress",
    "von_mises_plane_stress",
    "von_mises_bending_torsion",
    "yield_safety_factor",
    "strength_scorecard",
    "CombinedNormalStress",
    "combine_axial_bending",
]
