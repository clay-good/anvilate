"""T1 analytical Weibull reliability checks (closed-form).

How long a population of parts survives is rarely captured by a single average — some fail early
from defects, most fail around a wear-out age, and the pattern between them is what the Weibull
distribution describes. Its shape parameter tunes the failure mode continuously: below 1 is infant
mortality (a falling failure rate), exactly 1 is the constant-hazard exponential model, and above 1
is wear-out (a rising failure rate). This is the reliability-engineering complement to the fatigue
life of :mod:`anvilate.analysis.fatigue` — that module counts cycles to a crack, this one describes
the statistical spread of times to failure across a fleet.

The reliability (survival probability) at age t is R(t) = exp(−(t/η)^β), from the characteristic
life η (the age by which 63.2% have failed) and the dimensionless shape β. The instantaneous
failure rate is the hazard h(t) = (β/η)·(t/η)^(β−1), rising, constant, or falling as β is above,
at, or below 1. The mean time to failure follows from the gamma function, MTTF = η·Γ(1 + 1/β).
Inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import exp, gamma

from ..units import Quantity

__all__ = [
    "parallel_system_reliability",
    "series_system_reliability",
    "steady_state_availability",
    "weibull_hazard_rate",
    "weibull_mean_life",
    "weibull_reliability",
]


def weibull_reliability(*, time: Quantity, characteristic_life: Quantity, shape: float) -> float:
    """The Weibull reliability (survival probability), R(t) = exp(-(t/η)^β).

    The fraction of a population still working at age ``time`` t, from the ``characteristic_life`` η
    (the age by which 63.2% have failed) and the dimensionless ``shape`` β: R(t) = exp(-(t/η)^β). It
    falls from 1 at t = 0 toward 0, reaching 0.368 at t = η regardless of β. Returns the reliability
    as a plain float between 0 and 1.
    """
    _check(time, "[time]", "time")
    _check(characteristic_life, "[time]", "characteristic_life")
    t = time.to("s").magnitude
    eta = characteristic_life.to("s").magnitude
    if t < 0:
        raise ValueError("time must be non-negative")
    if eta <= 0:
        raise ValueError("characteristic_life must be positive")
    if shape <= 0:
        raise ValueError("shape must be positive")
    return exp(-((t / eta) ** shape))


def weibull_hazard_rate(*, time: Quantity, characteristic_life: Quantity, shape: float) -> Quantity:
    """The Weibull hazard (instantaneous failure) rate, h(t) = (β/η)*(t/η)^(β-1).

    The instantaneous failure rate among the survivors at age ``time`` t, from the
    ``characteristic_life`` η and the dimensionless ``shape`` β: h(t) = (β/η)*(t/η)^(β-1). It rises
    with age for β > 1 (wear-out), stays constant for β = 1 (the exponential model), and falls for
    β < 1 (infant mortality). Returns the hazard rate in 1/s.
    """
    _check(time, "[time]", "time")
    _check(characteristic_life, "[time]", "characteristic_life")
    t = time.to("s").magnitude
    eta = characteristic_life.to("s").magnitude
    if t < 0:
        raise ValueError("time must be non-negative")
    if eta <= 0:
        raise ValueError("characteristic_life must be positive")
    if shape <= 0:
        raise ValueError("shape must be positive")
    if t == 0.0 and shape < 1.0:
        raise ValueError("hazard rate diverges at t = 0 for shape < 1")
    h = (shape / eta) * (t / eta) ** (shape - 1.0)
    return Quantity(magnitude=h, unit="1/s")


def weibull_mean_life(*, characteristic_life: Quantity, shape: float) -> Quantity:
    """The Weibull mean time to failure, MTTF = η*Γ(1 + 1/β).

    The population's average life, from the ``characteristic_life`` η and the dimensionless
    ``shape`` β, via the gamma function: MTTF = η*Γ(1 + 1/β). It equals η exactly for β = 1 (the
    exponential model) and sits a little below η for typical wear-out shapes (β > 1). Returns the
    mean life in s.
    """
    _check(characteristic_life, "[time]", "characteristic_life")
    eta = characteristic_life.to("s").magnitude
    if eta <= 0:
        raise ValueError("characteristic_life must be positive")
    if shape <= 0:
        raise ValueError("shape must be positive")
    return Quantity(magnitude=eta * gamma(1.0 + 1.0 / shape), unit="s")


def steady_state_availability(*, mtbf: Quantity, mttr: Quantity) -> float:
    """The steady-state availability, A = MTBF/(MTBF + MTTR).

    The long-run fraction of time a repairable system is up and working: from the mean time between
    failures ``mtbf`` and the mean time to repair ``mttr``, A = MTBF/(MTBF + MTTR). It is the
    headline maintainability metric — "five nines" means A = 0.99999 — and it improves with either a
    more reliable system (longer MTBF) or faster repair (shorter MTTR). Returns the dimensionless
    availability (0 to 1) as a plain float.
    """
    _check(mtbf, "[time]", "mtbf")
    _check(mttr, "[time]", "mttr")
    up = mtbf.to("s").magnitude
    down = mttr.to("s").magnitude
    if up <= 0:
        raise ValueError("mtbf must be positive")
    if down < 0:
        raise ValueError("mttr must be non-negative")
    return up / (up + down)


def series_system_reliability(*, component_reliabilities: Sequence[float]) -> float:
    """The reliability of a series system, R = Π R_i.

    The probability that every component of a series system survives — the system fails if *any* one
    does — is the product of the individual ``component_reliabilities`` R_i: R = R_1·R_2·…·R_n. A
    series system is always less reliable than its weakest part, and adding components only lowers
    it, which is why long unredundant chains are fragile. Each reliability must be in [0, 1].
    Returns the system reliability (0 to 1) as a plain float.
    """
    if len(component_reliabilities) == 0:
        raise ValueError("component_reliabilities must contain at least one component")
    product = 1.0
    for r in component_reliabilities:
        if not 0.0 <= r <= 1.0:
            raise ValueError(f"each reliability must be in [0, 1]; got {r}")
        product *= r
    return product


def parallel_system_reliability(*, component_reliabilities: Sequence[float]) -> float:
    """The reliability of a parallel (redundant) system, R = 1 − Π(1 − R_i).

    The probability that at least one component of a parallel system survives — the system fails
    only if *all* of them do — is one minus the product of the individual failure probabilities:
    R = 1 − (1 − R_1)·(1 − R_2)·…·(1 − R_n), from the ``component_reliabilities`` R_i. Redundancy
    makes a parallel system more reliable than its best part, and adding parallel legs only raises
    it — the basis of fault-tolerant design. Each reliability must be in [0, 1]. Returns the system
    reliability (0 to 1) as a plain float.
    """
    if len(component_reliabilities) == 0:
        raise ValueError("component_reliabilities must contain at least one component")
    failure_product = 1.0
    for r in component_reliabilities:
        if not 0.0 <= r <= 1.0:
            raise ValueError(f"each reliability must be in [0, 1]; got {r}")
        failure_product *= 1.0 - r
    return 1.0 - failure_product


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
