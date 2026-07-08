"""Anvilate tolerance management: general tolerances, explicit tolerances,
fits, and stack-up analysis.

This slice ships ISO 2768-1 general tolerances (linear and angular), the
ISO 286-1 standard tolerance grades (IT grades), and fit resolution for the
H/h basis, the clearance letters d/e/f/g, the symmetric js/JS zones, and the
transition/interference shaft letters m/n/p — so the common hole-basis fits
(H7/g6, H8/f7, H9/d9, H7/js6, H7/n6, H7/p6, ...) resolve to limit deviations. It
also ships the three explicit per-dimension tolerance forms a spec can declare —
symmetric ±, asymmetric limits, and an ISO 286 fit — each resolving to a common
feature-size band. The grade-dependent j/k letters, the finer-stepped r/s/t/u,
the delta-corrected uppercase interference holes, wiring explicit tolerances onto
the Spec IR, and 1D stack-up analysis land here as they are built out (see
openspec/specs/tolerance-management/).
"""

from __future__ import annotations

from .explicit import (
    FitTolerance,
    LimitTolerance,
    ResolvedTolerance,
    SymmetricTolerance,
    Tolerance,
)
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
    "ResolvedTolerance",
    "SymmetricTolerance",
    "LimitTolerance",
    "FitTolerance",
    "Tolerance",
]
