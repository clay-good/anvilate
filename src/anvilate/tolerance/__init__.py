"""Anvilate tolerance management: general tolerances, explicit tolerances,
fits, and stack-up analysis.

This slice ships ISO 2768-1 general linear tolerances — the permissible
variation applied to any dimension without an explicit tolerance. Explicit
tolerances, ISO 286 fits, and 1D stack-up analysis land here as they are built
out (see openspec/specs/tolerance-management/).
"""

from __future__ import annotations

from .general import (
    GeneralTolerance,
    ToleranceClass,
    ToleranceRangeError,
    general_tolerance,
)

__all__ = [
    "ToleranceClass",
    "GeneralTolerance",
    "ToleranceRangeError",
    "general_tolerance",
]
