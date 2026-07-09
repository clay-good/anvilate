"""Anvilate tolerance management: general tolerances, explicit tolerances,
fits, and stack-up analysis.

This slice ships ISO 2768-1 general tolerances (linear and angular), the
ISO 286-1 standard tolerance grades (IT grades), and fit resolution for the
H/h basis, the clearance letters d/e/f/g, the symmetric js/JS zones, the
transition/interference shaft letters m/n/p, the grade-banded k transition
shaft, the finer-stepped r/s interference zones (shaft and R/S hole, up to
50 mm), the heavier u interference zone (shaft and U hole, up to 18 mm), and the
uppercase holes K/M/N/P via the ISO 286 delta rule — so the common
hole-basis fits (H7/g6, H8/f7, H9/d9, H7/js6, H7/k6, H7/n6, H7/p6, H7/r6, H7/s6,
H7/u6, ...) and the shaft-basis K7/h6, N7/h6, M7/h6, P7/h6, S7/h6 resolve to limit
deviations. It also ships the three explicit per-dimension tolerance forms a spec
can declare — symmetric ±, asymmetric limits, and an ISO 286 fit — each resolving
to a common feature-size band, and 1D tolerance stack-up analysis (worst-case,
root-sum-square, and Monte Carlo) over a chain of those bands with ranked
per-contributor sensitivities and predicted yield. The grade-dependent letter j
and the finer-stepped t (and r/s/u above their exact bound) land here as they are
built out (see openspec/specs/tolerance-management/).
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
    general_tolerance_source,
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
from .process import (
    AchievabilityCheck,
    ProcessCapability,
    process_capability,
    processes_that_can_hold,
    tolerance_is_achievable,
)
from .stackup import (
    Contribution,
    MonteCarloResult,
    StackContributor,
    StackResult,
    StackUp,
)

__all__ = [
    "ToleranceClass",
    "GeneralTolerance",
    "AngularTolerance",
    "ToleranceRangeError",
    "general_tolerance",
    "general_angular_tolerance",
    "general_tolerance_source",
    "resolve_class",
    "StandardTolerance",
    "standard_tolerance",
    "LimitDeviations",
    "zone_limits",
    "Fit",
    "fit",
    "ProcessCapability",
    "AchievabilityCheck",
    "process_capability",
    "tolerance_is_achievable",
    "processes_that_can_hold",
    "ResolvedTolerance",
    "SymmetricTolerance",
    "LimitTolerance",
    "FitTolerance",
    "Tolerance",
    "StackContributor",
    "Contribution",
    "StackResult",
    "MonteCarloResult",
    "StackUp",
]
