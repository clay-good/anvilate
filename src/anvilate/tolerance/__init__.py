"""Anvilate tolerance management: general tolerances, explicit tolerances,
fits, and stack-up analysis.

This slice ships ISO 2768-1 general tolerances (linear and angular), the
ISO 286-1 standard tolerance grades (IT grades), and fit resolution for the
H/h basis and clearance letters d/e/f/g — so the common clearance fits (H7/g6,
H8/f7, H9/d9, ...) resolve to limit deviations. The transition and interference
letters and 1D stack-up analysis land here as they are built out (see
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
    resolve_class,
)
from .iso286 import (
    Fit,
    LimitDeviations,
    StandardTolerance,
    fit,
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
    "resolve_class",
    "StandardTolerance",
    "standard_tolerance",
    "LimitDeviations",
    "zone_limits",
    "Fit",
    "fit",
]
