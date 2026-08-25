"""T1 analytical batch reaction-kinetics checks (integrated rate laws, closed-form).

How fast a batch reaction runs down its reactant depends on its order, and each order gives a
different closed-form concentration-versus-time law. This is the concentration-time side of
chemical kinetics — the temperature side (how the rate constant itself varies with T) is
:mod:`anvilate.analysis.arrhenius`, and the flow-reactor conversion is
:mod:`anvilate.analysis.reactor`; this module is the batch beaker.

A first-order reaction decays exponentially, C = C₀·e^(−k·t), so its half-life t½ = ln2/k depends
only on the rate constant, not on how much reactant you start with — the hallmark that also governs
radioactive decay and simple drug clearance. A second-order reaction runs C = C₀/(1 + k·C₀·t), whose
half-life t½ = 1/(k·C₀) *does* depend on the starting concentration, so a dilute batch takes longer
to half-convert. Turning the first-order law around gives the time to reach a target fractional
conversion X, t = −ln(1 − X)/k — the number a batch schedule or a shelf-life is built on.
Concentrations are dimension-checked :class:`~anvilate.units.Quantity` values (any [substance]/
[volume] unit); rate constants carry the order-appropriate units; conversion is a plain fraction.

Sources: Fogler, *Elements of Chemical Reaction Engineering* (rate laws and stoichiometry) — the
integrated first- and second-order concentration histories, their half-lives, and the time a
stated conversion takes.
"""

from __future__ import annotations

from math import exp, log

from ..units import Quantity

__all__ = [
    "first_order_half_life",
    "first_order_concentration",
    "first_order_time_for_conversion",
    "second_order_half_life",
    "second_order_concentration",
]


def first_order_half_life(*, rate_constant: Quantity) -> Quantity:
    """The half-life of a first-order reaction, t½ = ln2/k.

    The time for a first-order reaction to consume half its remaining reactant: t½ = ln2/k, from the
    ``rate_constant`` k (units of 1/time). Its defining feature is that it is *independent of
    concentration* — the reactant always halves in the same time, which is why first-order decay
    (and radioactive decay, and one-compartment drug clearance) has a fixed half-life. Returns the
    half-life as a time.
    """
    _check(rate_constant, "1/[time]", "rate_constant")
    k = rate_constant.to("1/s").magnitude
    if k <= 0:
        raise ValueError("rate_constant must be positive")
    return Quantity(magnitude=log(2.0) / k, unit="s")


def first_order_concentration(
    *, initial_concentration: Quantity, rate_constant: Quantity, time: Quantity
) -> Quantity:
    """The concentration in a first-order reaction, C = C₀·e^(−k·t).

    The integrated first-order rate law: the reactant left after a ``time`` t is C = C₀·e^(−k·t),
    from the ``initial_concentration`` C₀ and the ``rate_constant`` k (1/time). It falls
    exponentially — fast at first, then ever more slowly — never quite reaching zero, so it is
    quoted by half-lives (:func:`first_order_half_life`) rather than a finish time. Returns the
    concentration in the same units as the input.
    """
    _check(initial_concentration, "[substance]/[volume]", "initial_concentration")
    _check(rate_constant, "1/[time]", "rate_constant")
    _check(time, "[time]", "time")
    c0 = initial_concentration.to("mol/m**3").magnitude
    k = rate_constant.to("1/s").magnitude
    t = time.to("s").magnitude
    if c0 < 0:
        raise ValueError("initial_concentration must be non-negative")
    if k <= 0:
        raise ValueError("rate_constant must be positive")
    if t < 0:
        raise ValueError("time must be non-negative")
    return Quantity(magnitude=c0 * exp(-k * t), unit="mol/m**3")


def first_order_time_for_conversion(*, rate_constant: Quantity, conversion: float) -> Quantity:
    """The time to reach a target conversion in a first-order reaction, t = −ln(1 − X)/k.

    The batch-schedule inverse of the first-order law: the time to convert a fraction ``conversion``
    X of the reactant is t = −ln(1 − X)/k, from the ``rate_constant`` k (1/time). Because the tail
    thins exponentially, each further nine of conversion costs the same fixed increment of time
    (going from 90 % to 99 % takes as long as 0 % to 90 %), so chasing complete conversion is
    expensive. ``conversion`` X must be in [0, 1). Returns the required time.
    """
    _check(rate_constant, "1/[time]", "rate_constant")
    k = rate_constant.to("1/s").magnitude
    if k <= 0:
        raise ValueError("rate_constant must be positive")
    if not 0.0 <= conversion < 1.0:
        raise ValueError(f"conversion must be in [0, 1); got {conversion}")
    return Quantity(magnitude=-log(1.0 - conversion) / k, unit="s")


def second_order_half_life(*, rate_constant: Quantity, initial_concentration: Quantity) -> Quantity:
    """The half-life of a second-order reaction, t½ = 1/(k·C₀).

    Unlike the first-order case, a second-order reaction's half-life *depends on the starting
    concentration*: t½ = 1/(k·C₀), from the ``rate_constant`` k (volume/(amount·time)) and the
    ``initial_concentration`` C₀. A dilute batch (small C₀) half-converts more slowly, and each
    successive half-life is twice as long as the last — the signature that tells second-order
    from first-order kinetics in a rate study. Returns the half-life as a time.
    """
    _check(rate_constant, "[volume]/[substance]/[time]", "rate_constant")
    _check(initial_concentration, "[substance]/[volume]", "initial_concentration")
    k = rate_constant.to("m**3/(mol*s)").magnitude
    c0 = initial_concentration.to("mol/m**3").magnitude
    if k <= 0:
        raise ValueError("rate_constant must be positive")
    if c0 <= 0:
        raise ValueError("initial_concentration must be positive")
    return Quantity(magnitude=1.0 / (k * c0), unit="s")


def second_order_concentration(
    *, initial_concentration: Quantity, rate_constant: Quantity, time: Quantity
) -> Quantity:
    """The concentration in a second-order reaction, C = C₀/(1 + k·C₀·t).

    The integrated second-order rate law: after a ``time`` t the reactant left is
    C = C₀/(1 + k·C₀·t), from the ``initial_concentration`` C₀ and the ``rate_constant`` k
    (volume/(amount·time)). It decays as 1/t at long times — much slower in the tail than the
    exponential first-order decay — which is why the last of a second-order reactant is so hard to
    clear. Returns the concentration in the same units as the input.
    """
    _check(initial_concentration, "[substance]/[volume]", "initial_concentration")
    _check(rate_constant, "[volume]/[substance]/[time]", "rate_constant")
    _check(time, "[time]", "time")
    c0 = initial_concentration.to("mol/m**3").magnitude
    k = rate_constant.to("m**3/(mol*s)").magnitude
    t = time.to("s").magnitude
    if c0 < 0:
        raise ValueError("initial_concentration must be non-negative")
    if k <= 0:
        raise ValueError("rate_constant must be positive")
    if t < 0:
        raise ValueError("time must be non-negative")
    return Quantity(magnitude=c0 / (1.0 + k * c0 * t), unit="mol/m**3")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
