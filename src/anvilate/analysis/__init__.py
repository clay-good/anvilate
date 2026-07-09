"""Anvilate T1 analytical checks: closed-form, deterministic, no solver.

The T1 validation tier screens a design with handbook closed-form solutions
(Roark, Shigley) before any FEA — fast, deterministic, and unit-checked. This
package holds those checks; :mod:`anvilate.analysis.beam` covers the cantilever
and simply-supported bending cases and :mod:`anvilate.analysis.column` the Euler
buckling load. Further analytical cases land here as they are built out (see
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

__all__ = [
    "BeamBendingResult",
    "cantilever_end_load",
    "simply_supported_center_load",
    "rectangular_second_moment",
    "ColumnEnd",
    "euler_buckling_load",
]
