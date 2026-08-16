"""T1 analytical radioactive-decay checks (closed-form).

A radioactive source weakens over time by exponential decay: each nuclide has a fixed half-life, the
time for half of it to transform, and the activity falls by half every half-life regardless of how
much is present. This governs the shelf life of a medical isotope, the output of a radioisotope
power source, the dating of a sample by a known isotope, and the decay-in-storage of hot material.

The decay constant is lambda = ln(2) / T_half, the fractional decay rate that the half-life T_half
fixes. The activity then follows A = A0 * exp(-lambda * t) = A0 * 2^(-t / T_half): the source drops
to half at one half-life, a quarter at two, and so on. Reading it the other way gives the wait, the
time for a source to fall from an initial to a target activity, t = T_half * log2(A0 / A) — how long
a source must be stored before it is weak enough to handle or ship.
"""

from __future__ import annotations

from math import log, log2

from ..units import Quantity

__all__ = [
    "decay_constant_from_half_life",
    "specific_activity",
    "remaining_activity",
    "time_for_activity_decay",
]


_AVOGADRO = 6.02214076e23  # 1/mol (exact, SI definition)


def specific_activity(*, half_life: Quantity, molar_mass: Quantity) -> Quantity:
    """The specific activity of a pure nuclide, a = ln(2)·N_A/(T_half·M).

    :func:`remaining_activity` starts from an activity someone hands you; this is where that number
    comes from. A gram of a pure nuclide holds N_A/M atoms, each decaying at the rate λ = ln(2)/
    T_half, so its activity per unit mass is a = λ·N_A/M = ln(2)·N_A/(``half_life``·``molar_mass``).
    It is how sources are actually specified and priced, and it explains why short-lived nuclides
    are so fierce: activity is inversely proportional to half-life, so I-131 (8 days) carries about
    110 times the activity per gram of Co-60 (5.3 years), and a medical dose of it is a speck.
    ``molar_mass`` M is the nuclide's atomic mass (59.9338 g/mol for Co-60). Returns the specific
    activity in Bq/g — call ``.to("Ci/g")`` for curies.
    """
    _check(half_life, "[time]", "half_life")
    _check(molar_mass, "[mass]/[substance]", "molar_mass")
    t_half = half_life.to("s").magnitude
    m = molar_mass.to("g/mol").magnitude
    if t_half <= 0:
        raise ValueError("half_life must be positive")
    if m <= 0:
        raise ValueError("molar_mass must be positive")
    return Quantity(magnitude=log(2.0) * _AVOGADRO / (t_half * m), unit="Bq/g")


def decay_constant_from_half_life(*, half_life: Quantity) -> Quantity:
    """The decay constant, lambda = ln(2) / T_half.

    The fractional decay rate a nuclide's ``half_life`` T_half fixes: lambda = ln(2) / T_half. It is
    the probability per unit time that a given nucleus decays, and it sets the exponential decay of
    both the activity and the amount of the nuclide. Returns the decay constant in 1/s.
    """
    _check(half_life, "[time]", "half_life")
    t_half = half_life.to("s").magnitude
    if t_half <= 0:
        raise ValueError("half_life must be positive")
    return Quantity(magnitude=log(2.0) / t_half, unit="1/s")


def remaining_activity(
    *, initial_activity: Quantity, elapsed_time: Quantity, half_life: Quantity
) -> Quantity:
    """The activity remaining after a time, A = A0 * 2^(-t / T_half).

    The activity of a source after decay: the ``initial_activity`` A0 halved once per ``half_life``
    T_half over the ``elapsed_time`` t, A = A0 * 2^(-t / T_half). It is what is left of a source's
    output after storage or transit — half at one half-life, a quarter at two. Returns the activity
    in the same units as A0 (reported in becquerel).
    """
    _check(initial_activity, "1/[time]", "initial_activity")
    _check(elapsed_time, "[time]", "elapsed_time")
    _check(half_life, "[time]", "half_life")
    a0 = initial_activity.to("Bq").magnitude
    t = elapsed_time.to("s").magnitude
    t_half = half_life.to("s").magnitude
    if a0 < 0:
        raise ValueError("initial_activity must be non-negative")
    if t < 0:
        raise ValueError("elapsed_time must be non-negative")
    if t_half <= 0:
        raise ValueError("half_life must be positive")
    return Quantity(magnitude=a0 * 2.0 ** (-t / t_half), unit="Bq")


def time_for_activity_decay(
    *, initial_activity: Quantity, final_activity: Quantity, half_life: Quantity
) -> Quantity:
    """The time to decay to a target activity, t = T_half * log2(A0 / A).

    The wait for a source to fall from an ``initial_activity`` A0 to a lower ``final_activity`` A,
    given the ``half_life`` T_half: t = T_half * log2(A0 / A). It is how long hot material must be
    stored before it is weak enough to handle, ship, or dispose of. Returns the time in s.
    """
    _check(initial_activity, "1/[time]", "initial_activity")
    _check(final_activity, "1/[time]", "final_activity")
    _check(half_life, "[time]", "half_life")
    a0 = initial_activity.to("Bq").magnitude
    a = final_activity.to("Bq").magnitude
    t_half = half_life.to("s").magnitude
    if a0 <= 0:
        raise ValueError("initial_activity must be positive")
    if a <= 0:
        raise ValueError("final_activity must be positive")
    if a > a0:
        raise ValueError(
            "final_activity must not exceed initial_activity (decay only decreases it)"
        )
    if t_half <= 0:
        raise ValueError("half_life must be positive")
    return Quantity(magnitude=t_half * log2(a0 / a), unit="s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
