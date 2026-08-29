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

Sources: MIL-HDBK-217 and IEC 61709 for the failure-rate conventions;
O'Connor & Kleyner, *Practical Reliability Engineering*, for the reliability,
availability and Weibull relations.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb, exp, gamma, log

from ..units import Quantity

__all__ = [
    "k_out_of_n_reliability",
    "parallel_system_reliability",
    "parallel_system_mtbf",
    "series_system_mtbf",
    "series_system_reliability",
    "steady_state_availability",
    "weibull_hazard_rate",
    "weibull_mean_life",
    "weibull_life_for_reliability",
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


def weibull_life_for_reliability(
    *, reliability: float, characteristic_life: Quantity, shape: float
) -> Quantity:
    """The age at which a stated fraction still survives, t = η·(−ln R)^(1/β).

    The inverse of :func:`weibull_reliability`, and the direction design actually asks in: not
    "what fraction survives to this age" but "what age can I quote at this survival fraction".
    From the target ``reliability`` R (a plain float in (0, 1)), the ``characteristic_life`` η, and
    the ``shape`` β: t = η·(−ln R)^(1/β). At R = 0.90 it is the B10 life every bearing, pump, and
    gearbox is rated on; at R = 0.01 the B1 life a critical component is held to.

    R = 1/e = 0.3679 returns η exactly for any β, which is what makes η "the characteristic life".
    Note the deliberate asymmetry with :func:`weibull_reliability`: reliability is a probability, so
    it is a plain float, while the life returned is a time. Returns the life in seconds.
    """
    _check(characteristic_life, "[time]", "characteristic_life")
    eta = characteristic_life.to("s").magnitude
    if not 0.0 < reliability < 1.0:
        raise ValueError(f"reliability must be strictly between 0 and 1; got {reliability}")
    if eta <= 0:
        raise ValueError("characteristic_life must be positive")
    if shape <= 0:
        raise ValueError("shape must be positive")
    return Quantity(magnitude=eta * (-log(reliability)) ** (1.0 / shape), unit="s")


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
    if not isinstance(component_reliabilities, Sequence):
        raise ValueError(
            f"component_reliabilities must be a sequence, not a single value; "
            f"got {component_reliabilities!r}"
        )
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
    if not isinstance(component_reliabilities, Sequence):
        raise ValueError(
            f"component_reliabilities must be a sequence, not a single value; "
            f"got {component_reliabilities!r}"
        )
    if len(component_reliabilities) == 0:
        raise ValueError("component_reliabilities must contain at least one component")
    failure_product = 1.0
    for r in component_reliabilities:
        if not 0.0 <= r <= 1.0:
            raise ValueError(f"each reliability must be in [0, 1]; got {r}")
        failure_product *= 1.0 - r
    return 1.0 - failure_product


def k_out_of_n_reliability(
    *, component_reliability: float, total_units: int, required_units: int
) -> float:
    """The reliability of a k-out-of-n redundant system, R = Σ_{i=k}^{n} C(n,i)·R^i·(1−R)^(n−i).

    The general redundancy form for n identical units of reliability ``component_reliability`` R
    where any ``required_units`` k of ``total_units`` n keep the system up (a 2-of-3 voting logic, 3
    of 4 engines, a spared array): the binomial sum of the ways at least k survive. It spans the
    range between :func:`series_system_reliability` (k = n, all must work) and
    :func:`parallel_system_reliability` (k = 1, any one will do), letting you size just enough
    redundancy. R in [0, 1]; ``total_units`` and ``required_units`` positive integers with k ≤ n.
    Returns the system reliability (0 to 1) as a plain float.
    """
    if not 0.0 <= component_reliability <= 1.0:
        raise ValueError(f"component_reliability must be in [0, 1]; got {component_reliability}")
    if not isinstance(total_units, int) or total_units < 1:
        raise ValueError(f"total_units must be a positive integer; got {total_units!r}")
    if not isinstance(required_units, int) or required_units < 1:
        raise ValueError(f"required_units must be a positive integer; got {required_units!r}")
    if required_units > total_units:
        raise ValueError("required_units must not exceed total_units")
    r = component_reliability
    return sum(
        comb(total_units, i) * r**i * (1.0 - r) ** (total_units - i)
        for i in range(required_units, total_units + 1)
    )


def parallel_system_mtbf(*, failure_rate: Quantity, unit_count: int) -> Quantity:
    """The MTBF of n identical active-redundant units, MTBF = (1/λ)·Σ(1/k) for k = 1..n.

    The mirror of :func:`series_system_mtbf`, which the module had without its redundant
    counterpart. In a parallel (active-redundant) set the system survives until the LAST unit
    fails, so the expected time is the sum of the waiting times for each successive failure: with
    n units running, failures arrive at n·λ, then (n−1)·λ, and so on — a harmonic series.

    The intuitive answer is wrong in the unsafe direction. Two units of 10,000 h MTBF do not give
    20,000 h; they give 15,000 h, because early on there are two units failing at twice the rate.
    Three give 18,333 h, not 30,000. Redundancy pays diminishing returns and the shortfall against
    the naive n·MTBF grows with n.

    Assumes constant hazard (exponential life), units that are truly independent, and no repair —
    so this is an upper bound on any real redundant set, which shares a power supply or an
    environment. ``failure_rate`` λ is the per-unit rate (1/time) and ``unit_count`` n the number
    of units. Returns the system MTBF as a time.
    """
    _check(failure_rate, "1/[time]", "failure_rate")
    rate = failure_rate.to("1/hour").magnitude
    if rate <= 0:
        raise ValueError(f"failure_rate must be positive; got {failure_rate}")
    if unit_count < 1:
        raise ValueError(f"unit_count must be at least 1; got {unit_count}")
    harmonic = sum(1.0 / k for k in range(1, unit_count + 1))
    return Quantity(magnitude=harmonic / rate, unit="hour")


def series_system_mtbf(*, failure_rates: Sequence[Quantity]) -> Quantity:
    """The MTBF of a series system of constant-hazard parts, MTBF = 1/Σ λ_i.

    For components whose failure rates add — a series system where any part failing stops the whole,
    each with constant hazard λ_i — the system failure rate is the sum Σ λ_i and the mean time
    between failures is its reciprocal, MTBF = 1/Σ λ_i. This is the parts-count reliability
    prediction: more parts in series means a higher combined rate and a shorter MTBF. Each entry in
    ``failure_rates`` is a rate (1/time) and must be non-negative, with at least one positive.
    Returns the MTBF as a time.
    """
    if not isinstance(failure_rates, Sequence):
        raise ValueError(
            f"failure_rates must be a sequence, not a single value; got {failure_rates!r}"
        )
    if len(failure_rates) == 0:
        raise ValueError("failure_rates must contain at least one component")
    total_rate = 0.0
    for rate in failure_rates:
        _check(rate, "1/[time]", "failure_rates entry")
        value = rate.to("1/s").magnitude
        if value < 0:
            raise ValueError("each failure rate must be non-negative")
        total_rate += value
    if total_rate <= 0:
        raise ValueError("at least one failure rate must be positive")
    return Quantity(magnitude=1.0 / total_rate, unit="s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
