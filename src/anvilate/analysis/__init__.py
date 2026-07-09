"""Anvilate T1 analytical checks: closed-form, deterministic, no solver.

The T1 validation tier screens a design with handbook closed-form solutions
(Roark, Shigley) before any FEA — fast, deterministic, and unit-checked. This
package holds those checks; :mod:`anvilate.analysis.beam` covers the cantilever
and simply-supported bending cases, :mod:`anvilate.analysis.column` the Euler
buckling load, :mod:`anvilate.analysis.fastener` the bolt torque-tension
relation, and :mod:`anvilate.analysis.torsion` the solid-shaft torsion check.
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
]
