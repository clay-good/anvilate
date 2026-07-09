"""Anvilate T1 analytical checks: closed-form, deterministic, no solver.

The T1 validation tier screens a design with handbook closed-form solutions
(Roark, Shigley) before any FEA — fast, deterministic, and unit-checked. This
package holds those checks; :mod:`anvilate.analysis.beam` covers the cantilever
and simply-supported bending cases, :mod:`anvilate.analysis.column` the Euler
buckling load, :mod:`anvilate.analysis.fastener` the bolt torque-tension
relation, :mod:`anvilate.analysis.torsion` the solid-shaft torsion check, and
:mod:`anvilate.analysis.pressure_vessel` the thin-wall cylinder stresses, and
:mod:`anvilate.analysis.stress` the von Mises combination of component stresses.
Further analytical cases land here as they are built out (see
openspec/specs/validation-gauntlet/).
"""

from __future__ import annotations

from .beam import (
    BeamBendingResult,
    cantilever_end_load,
    rectangular_second_moment,
    simply_supported_center_load,
)
from .column import ColumnEnd, euler_buckling_load
from .fastener import (
    NUT_FACTOR_AS_RECEIVED,
    bolt_preload_from_torque,
    torque_for_preload,
)
from .pressure_vessel import ThinWallStress, thin_wall_cylinder
from .stress import (
    von_mises_bending_torsion,
    von_mises_plane_stress,
    yield_safety_factor,
)
from .torsion import (
    polar_second_moment_solid,
    shaft_torsional_stress,
    shaft_twist_angle,
)

__all__ = [
    "BeamBendingResult",
    "cantilever_end_load",
    "simply_supported_center_load",
    "rectangular_second_moment",
    "ColumnEnd",
    "euler_buckling_load",
    "NUT_FACTOR_AS_RECEIVED",
    "bolt_preload_from_torque",
    "torque_for_preload",
    "polar_second_moment_solid",
    "shaft_torsional_stress",
    "shaft_twist_angle",
    "ThinWallStress",
    "thin_wall_cylinder",
    "von_mises_plane_stress",
    "von_mises_bending_torsion",
    "yield_safety_factor",
]
