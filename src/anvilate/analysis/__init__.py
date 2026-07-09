"""Anvilate T1 analytical checks: closed-form, deterministic, no solver.

The T1 validation tier screens a design with handbook closed-form solutions
(Roark, Shigley) before any FEA — fast, deterministic, and unit-checked. This
package holds those checks; the first is the cantilever beam
(:mod:`anvilate.analysis.beam`). Further analytical cases land here as they are
built out (see openspec/specs/validation-gauntlet/).
"""

from __future__ import annotations

from .beam import CantileverResult, cantilever_end_load, rectangular_second_moment

__all__ = [
    "CantileverResult",
    "cantilever_end_load",
    "rectangular_second_moment",
]
