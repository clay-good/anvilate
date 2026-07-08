"""Anvilate tolerance management: general tolerances, explicit tolerances,
fits, and stack-up analysis.

This slice ships ISO 2768-1 general tolerances (linear and angular) and the
ISO 286-1 standard tolerance grades (IT grades) — the width half of every ISO
fit designation. Fundamental deviations, full fit resolution (H7/g6 → limits),
and 1D stack-up analysis land here as they are built out (see
openspec/specs/tolerance-management/).
"""

from __future__ import annotations

from .general import (
    AngularTolerance,
    GeneralTolerance,
    ToleranceClass,
    ToleranceRangeError,
    general_angular_tolerance,
    general_tolerance,
)
from .iso286 import (
    LimitDeviations,
    StandardTolerance,
    standard_tolerance,
    zone_limits,
)

__all__ = [
    "ToleranceClass",
    "GeneralTolerance",
    "AngularTolerance",
    "ToleranceRangeError",
    "general_tolerance",
    "general_angular_tolerance",
    "StandardTolerance",
    "standard_tolerance",
    "LimitDeviations",
    "zone_limits",
]
