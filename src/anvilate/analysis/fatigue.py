"""T1 analytical fatigue screening (modified Goodman / Soderberg, closed-form).

A part under fluctuating load fails by fatigue below its static strength. The
modified Goodman criterion combines the alternating stress amplitude σ_a and the
mean stress σ_m against the endurance limit S_e and the ultimate strength S_u:

    σ_a/S_e + σ_m/S_u = 1/n

so the fatigue safety factor is ``n = 1 / (σ_a/S_e + σ_m/S_u)`` (Shigley). The
Soderberg criterion is the same line drawn to the *yield* strength S_y instead of
S_u, ``σ_a/S_e + σ_m/S_y = 1/n`` — more conservative, and the one criterion that
also guards the mean stress against first-cycle yielding. The endurance limit is
often a labelled estimate or simply absent for a material — in which case a screen
honours No-silent-green and reports ``NOT_EVALUATED`` rather than a silent pass.
As with the other checks, inputs are dimension-checked
:class:`~anvilate.units.Quantity` stresses.
"""

from __future__ import annotations

from math import inf

from ..scorecard import ScorecardEntry
from ..units import Quantity

__all__ = [
    "goodman_safety_factor",
    "goodman_scorecard",
    "soderberg_safety_factor",
    "soderberg_scorecard",
]


def _require_stress(value: Quantity, name: str) -> float:
    if not value.has_dimension("[pressure]"):
        raise ValueError(
            f"{name} must be a [pressure] quantity; got {value.dimensionality} ({value})"
        )
    return value.to("MPa").magnitude


def goodman_safety_factor(
    *,
    alternating_stress: Quantity,
    mean_stress: Quantity,
    endurance_limit: Quantity,
    ultimate_strength: Quantity,
) -> float:
    """The modified-Goodman fatigue safety factor n = 1/(σ_a/S_e + σ_m/S_u).

    ``alternating_stress`` is the stress amplitude σ_a (non-negative), ``mean_stress``
    the mean σ_m (tension positive), ``endurance_limit`` S_e and
    ``ultimate_strength`` S_u the material strengths (both positive). All must be
    stresses. Returns ``inf`` when the combination predicts no fatigue failure
    (a non-positive Goodman sum, e.g. a fully-compressive mean with no amplitude).
    """
    sa = _require_stress(alternating_stress, "alternating_stress")
    sm = _require_stress(mean_stress, "mean_stress")
    se = _require_stress(endurance_limit, "endurance_limit")
    su = _require_stress(ultimate_strength, "ultimate_strength")
    if sa < 0:
        raise ValueError(f"alternating_stress (an amplitude) must be non-negative; got {sa} MPa")
    if se <= 0 or su <= 0:
        raise ValueError("endurance_limit and ultimate_strength must be positive")
    goodman_sum = sa / se + sm / su
    return inf if goodman_sum <= 0 else 1.0 / goodman_sum


def goodman_scorecard(
    name: str,
    *,
    alternating_stress: Quantity,
    mean_stress: Quantity,
    endurance_limit: Quantity | None,
    ultimate_strength: Quantity,
    required: float,
) -> ScorecardEntry:
    """Screen a fluctuating stress state for fatigue → a :class:`ScorecardEntry`.

    Computes the modified-Goodman safety factor and judges it against ``required``.
    When ``endurance_limit`` is ``None`` — a material with no listed (or estimable)
    endurance limit — the entry is ``NOT_EVALUATED`` rather than a silent pass,
    honouring No-silent-green for the fatigue dimension.
    """
    if endurance_limit is None:
        computed = None
    else:
        computed = goodman_safety_factor(
            alternating_stress=alternating_stress,
            mean_stress=mean_stress,
            endurance_limit=endurance_limit,
            ultimate_strength=ultimate_strength,
        )
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required)


def soderberg_safety_factor(
    *,
    alternating_stress: Quantity,
    mean_stress: Quantity,
    endurance_limit: Quantity,
    yield_strength: Quantity,
) -> float:
    """The Soderberg fatigue safety factor n = 1/(σ_a/S_e + σ_m/S_y).

    The same construction as :func:`goodman_safety_factor` but drawn to the
    ``yield_strength`` S_y instead of the ultimate — more conservative, and unlike
    Goodman it also holds the mean stress below yield, so a passing part is safe
    from first-cycle yielding too. ``alternating_stress`` is the amplitude σ_a
    (non-negative), ``mean_stress`` the mean σ_m (tension positive), and
    ``endurance_limit`` S_e / ``yield_strength`` S_y the material strengths (both
    positive). All must be stresses. Returns ``inf`` when the combination predicts
    no fatigue failure (a non-positive Soderberg sum).
    """
    sa = _require_stress(alternating_stress, "alternating_stress")
    sm = _require_stress(mean_stress, "mean_stress")
    se = _require_stress(endurance_limit, "endurance_limit")
    sy = _require_stress(yield_strength, "yield_strength")
    if sa < 0:
        raise ValueError(f"alternating_stress (an amplitude) must be non-negative; got {sa} MPa")
    if se <= 0 or sy <= 0:
        raise ValueError("endurance_limit and yield_strength must be positive")
    soderberg_sum = sa / se + sm / sy
    return inf if soderberg_sum <= 0 else 1.0 / soderberg_sum


def soderberg_scorecard(
    name: str,
    *,
    alternating_stress: Quantity,
    mean_stress: Quantity,
    endurance_limit: Quantity | None,
    yield_strength: Quantity,
    required: float,
) -> ScorecardEntry:
    """Screen a fluctuating stress state for fatigue (Soderberg) → a
    :class:`ScorecardEntry`.

    The conservative counterpart of :func:`goodman_scorecard`, judging the
    Soderberg safety factor against ``required``. When ``endurance_limit`` is
    ``None`` the entry is ``NOT_EVALUATED`` rather than a silent pass, honouring
    No-silent-green for the fatigue dimension.
    """
    if endurance_limit is None:
        computed = None
    else:
        computed = soderberg_safety_factor(
            alternating_stress=alternating_stress,
            mean_stress=mean_stress,
            endurance_limit=endurance_limit,
            yield_strength=yield_strength,
        )
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required)
